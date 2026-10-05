from __future__ import annotations

import asyncio
import json
import os
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path

from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.adapters.session_manager import DerivSessionManager
from runtime.agent_federation import AgentFederationSupervisor, PersistentAgentFederation
from runtime.autonomous_loop import AutonomousExecutionLoop, FederatedDecisionProvider
from runtime.broker.executor import CapitalPlaneExecutor
from runtime.core.persistent import PersistentIdempotencyStore
from runtime.core.journal import AppendOnlyJournal
from runtime.core.persistent import PersistentExecutionFence, PersistentLedger
from runtime.core.reconcile import Reconciler
from runtime.core.runtime_config import load_config_hash
from runtime.core.models import RuntimeState
from runtime.core.state import RuntimeStateMachine

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENTS = (
    "ClaudeCode", "KimiK3", "GrokBot", "GoogleAgentSkills",
    "GLM", "PlaywrightCLI", "AURELIA",
)

@dataclass
class ContinuousRuntime:
    federation: PersistentAgentFederation
    federation_supervisor: AgentFederationSupervisor
    adapter: DerivAdapter | None = None
    execution_loop: AutonomousExecutionLoop | None = None
    execution_task: asyncio.Task[None] | None = None
    heartbeat_task: asyncio.Task[None] | None = None

    async def stop(self) -> None:
        if self.execution_loop is not None:
            self.execution_loop.stop()
        if self.heartbeat_task is not None:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            self.heartbeat_task = None
        if self.federation_supervisor is not None:
            await self.federation_supervisor.stop()
        if self.adapter is not None:
            await self.adapter.close()


async def start_continuous_runtime(
    machine: RuntimeStateMachine,
    *,
    federation: PersistentAgentFederation | None = None,
    federation_supervisor: AgentFederationSupervisor | None = None,
) -> ContinuousRuntime:
    config_hash = load_config_hash(ROOT)
    source_hash = os.getenv("GITHUB_SHA", "RUNTIME_UNPINNED")
    if federation is None:
        federation = federation or PersistentAgentFederation(
        journal_path=os.getenv("AURELIA_FEDERATION_JOURNAL_PATH", "/tmp/aurelia/federation-events.ndjson"),
        lease_path=os.getenv("AURELIA_FEDERATION_LEASE_PATH", "/tmp/aurelia/federation-leases.json"),
        config_hash=config_hash,
        source_hash=source_hash,
        lease_seconds=float(os.getenv("AURELIA_AGENT_LEASE_SECONDS", "45")),
    )
    agents = DEFAULT_AGENTS
    matrix_path = ROOT / "config" / "agent_capability_matrix.json"
    if matrix_path.exists():
        try:
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            configured = tuple(sorted((matrix.get("agents") or {}).keys()))
            if configured:
                agents = tuple(sorted(set(configured) | {"AURELIA"}))
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    if federation_supervisor is None:
        federation_supervisor = AgentFederationSupervisor(
            federation,
            agents=agents,
            interval_seconds=float(os.getenv("AURELIA_AGENT_HEARTBEAT_SECONDS", "15")),
            roundtable_seconds=float(os.getenv("AURELIA_AGENT_ROUNDTABLE_SECONDS", "60")),
        )
        federation_supervisor.start()
    runtime = ContinuousRuntime(federation, federation_supervisor)

    # AURELIA worker liveness is owned by this actual runtime process.
    # The federation supervisor deliberately cannot manufacture this lease.
    worker_id = os.getenv("AURELIA_WORKER_ID", "").strip() or (
        f"AURELIA:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"
    )

    async def worker_heartbeat() -> None:
        interval = max(1.0, min(federation.lease_seconds / 3.0, 15.0))
        while True:
            await federation.heartbeat(
                "AURELIA",
                worker_id=worker_id,
                origin="WORKER",
            )
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise

    runtime.heartbeat_task = asyncio.create_task(
        worker_heartbeat(),
        name=f"aurelia-worker-heartbeat:{worker_id}",
    )

    if os.getenv("AURELIA_AUTONOMOUS_LOOP", "false").strip().lower() != "true":
        await federation.publish(
            sender="AURELIA", recipients=agents, message_type="RUNTIME_MODE",
            payload={"mode": "FEDERATED_BACKGROUND_RESEARCH", "capital_authority": False},
            correlation_id="runtime-mode", priority=70, requires_response=True,
        )
        return runtime

    token = os.getenv("DERIV_AUTH_TOKEN") or os.getenv("DERIV_PAT", "")
    loginid = os.getenv("DERIV_EXPECTED_LOGINID") or os.getenv("DERIV_AUTHORIZED_ACCOUNT_ID", "")
    auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower()
    app_id = os.getenv("DERIV_APP_ID", "")
    if not token or not loginid:
        await federation.publish(
            sender="AURELIA", recipients=agents, message_type="BLOCKER",
            payload={"reason": "DERIV_AUTH_CONFIGURATION_MISSING", "capital_authority": False},
            correlation_id="deriv-auth", priority=95, requires_response=True,
        )
        return runtime
    if auth_mode not in {"pat", "oauth"}:
        await federation.publish(
            sender="AURELIA", recipients=agents, message_type="BLOCKER",
            payload={"reason": "DERIV_AUTH_MODE_INVALID", "capital_authority": False},
            correlation_id="deriv-auth-mode", priority=95, requires_response=True,
        )
        return runtime
    if auth_mode == "pat" and not app_id:
        await federation.publish(
            sender="AURELIA", recipients=agents, message_type="BLOCKER",
            payload={"reason": "DERIV_APP_ID_REQUIRED_FOR_PAT", "capital_authority": False},
            correlation_id="deriv-app-id", priority=95, requires_response=True,
        )
        return runtime

    manager = DerivSessionManager(
        expected_loginid=loginid,
        expected_environment=os.getenv("DERIV_ENVIRONMENT", "real"),
        expected_currency=os.getenv("DERIV_EXPECTED_CURRENCY", "USD"),
    )
    bootstrap = manager.bootstrap(
        bearer_token=token,
        app_id=app_id or None,
    )
    adapter = DerivAdapter(
        ws_url=bootstrap.websocket.url,
        expected_loginid=bootstrap.binding.loginid,
        expected_currency=bootstrap.binding.currency,
        environment=bootstrap.binding.environment,
        auth_token="",
    )
    account = await adapter.connect()
    capital = await adapter.get_balance()
    machine.transition(__import__("runtime.core.models", fromlist=["RuntimeState"]).RuntimeState.BROKER_CONNECTING)
    machine.transition(__import__("runtime.core.models", fromlist=["RuntimeState"]).RuntimeState.BROKER_VERIFIED)

    ledger = PersistentLedger(os.getenv("AURELIA_LEDGER_PATH", "/tmp/aurelia/ledger.json"))
    idempotency = PersistentIdempotencyStore(os.getenv("AURELIA_IDEMPOTENCY_PATH", "/tmp/aurelia/idempotency.json"))
    fence = PersistentExecutionFence(os.getenv("AURELIA_FENCE_PATH", "/tmp/aurelia/executor-fence.txt"))
    journal = AppendOnlyJournal(os.getenv("AURELIA_EXECUTION_JOURNAL_PATH", "/tmp/aurelia/execution-events.ndjson"))
    executor = CapitalPlaneExecutor(
        adapter, journal=journal, ledger=ledger, idempotency=idempotency, fence=fence,
        state=machine, reconciler=Reconciler(), source_hash=source_hash,
        config_hash=config_hash, live_lock_path=ROOT / "config" / "LIVE_LOCK.yaml",
    )
    symbols_raw = os.getenv("AURELIA_SYMBOLS", "")
    symbols = tuple(x.strip() for x in symbols_raw.split(",") if x.strip())
    if not symbols:
        active = await adapter.active_symbols()
        limit = max(1, int(os.getenv("AURELIA_MAX_SYMBOLS", "20")))
        symbols = tuple(str(x.get("symbol")) for x in active if x.get("symbol"))[:limit]
    runtime.execution_loop = AutonomousExecutionLoop(
        adapter=adapter, executor=executor, decision_provider=FederatedDecisionProvider(federation),
        runtime_config_hash=config_hash, symbols=symbols,
        lifecycle_timeout_seconds=float(os.getenv("AURELIA_LIFECYCLE_TIMEOUT_SECONDS", "600")),
    )
    runtime.adapter = adapter
    runtime.execution_task = asyncio.create_task(
        runtime.execution_loop.run(), name="aurelia-autonomous-execution-loop"
    )
    await federation.publish(
        sender="AURELIA", recipients=agents, message_type="AUTONOMOUS_RUNTIME_STARTED",
        payload={"account_loginid": account.loginid, "environment": account.environment,
                 "currency": account.currency, "symbol_count": len(symbols),
                 "capital_authority_holder": "CapitalPlaneExecutor",
                 "external_agents_capital_authority": False,
                 "verified_balance": capital.available_balance},
        correlation_id="autonomous-runtime", priority=90, requires_response=True,
    )
    return runtime