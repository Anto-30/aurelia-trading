from __future__ import annotations

import asyncio
import json
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.adapters.session_manager import DerivSessionManager
from runtime.agent_federation import AgentFederationSupervisor, PersistentAgentFederation
from runtime.agent_performance import AgentPerformanceLedger
from runtime.agent_workers import AgentWorkerSupervisor
from runtime.autonomous_loop import AutonomousExecutionLoop, FederatedDecisionProvider
from runtime.broker.executor import CapitalPlaneExecutor
from runtime.core.persistent import PersistentIdempotencyStore
from runtime.core.journal import AppendOnlyJournal
from runtime.core.persistent import PersistentExecutionFence, PersistentLedger
from runtime.core.daily_risk import PersistentDailyRiskGuard, derive_utc_day_start_balance
from runtime.core.reconcile import Reconciler
from runtime.core.runtime_config import load_config_hash
from runtime.core.release_gate import read_live_release
from runtime.core.secrets import get_optional_secret
from runtime.core.state import RuntimeStateMachine
from runtime.strategy.research_supervisor import build_research_signal_supervisor

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENTS = (
    "ClaudeCode", "KimiK3", "GrokBot", "GoogleAgentSkills",
    "GLM", "PlaywrightCLI", "JEV", "DeepSeekHarness", "HermesAgent", "AURELIA",
)


def load_runtime_agent_roster(root: Path = ROOT) -> tuple[str, ...]:
    """Load the single canonical process-managed worker roster.

    ChatGPT is a current-conversation supervisor, Dev requires an authorized
    connected host, and AURELIA is the deterministic control plane rather than
    a model subprocess. The first two must never be spawned as local workers;
    AURELIA is included only for federation routing/heartbeats.
    """
    provider_path = root / "config" / "agent_runtime_provider_matrix.json"
    capability_path = root / "config" / "agent_capability_matrix.json"
    try:
        provider_matrix = json.loads(provider_path.read_text(encoding="utf-8"))
        capability_matrix = json.loads(capability_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("AGENT_RUNTIME_ROSTER_CONFIG_UNREADABLE") from exc

    if provider_matrix.get("schema") != "aurelia.agent_runtime_provider_matrix.v1":
        raise RuntimeError("AGENT_RUNTIME_PROVIDER_MATRIX_SCHEMA_INVALID")
    roster = provider_matrix.get("runtime_managed_agent_roster")
    runtime_specs = provider_matrix.get("runtimes")
    non_worker_roles = provider_matrix.get("non_worker_roles", {})
    if not isinstance(roster, list) or not roster or not isinstance(runtime_specs, list):
        raise RuntimeError("AGENT_RUNTIME_ROSTER_MISSING")
    if any(not isinstance(name, str) or not name.strip() for name in roster):
        raise RuntimeError("AGENT_RUNTIME_ROSTER_INVALID")
    if len(set(roster)) != len(roster):
        raise RuntimeError("AGENT_RUNTIME_ROSTER_DUPLICATE")
    if set(roster) & {"AURELIA", "ChatGPT", "Dev"}:
        raise RuntimeError("NON_WORKER_ROLE_INCLUDED_IN_RUNTIME_ROSTER")
    spec_names = [str(spec.get("name", "")) for spec in runtime_specs if isinstance(spec, dict)]
    if len(spec_names) != len(runtime_specs) or set(spec_names) != set(roster) or len(spec_names) != len(set(spec_names)):
        raise RuntimeError("AGENT_RUNTIME_ROSTER_PROFILE_MISMATCH")
    if not isinstance(non_worker_roles, dict) or not {"AURELIA", "ChatGPT", "Dev"}.issubset(non_worker_roles):
        raise RuntimeError("AGENT_NON_WORKER_ROLE_BOUNDARY_MISSING")
    registered_agents = capability_matrix.get("agents", {})
    if not isinstance(registered_agents, dict) or not set(roster).issubset(registered_agents):
        raise RuntimeError("AGENT_RUNTIME_ROSTER_NOT_REGISTERED_IN_CAPABILITY_MATRIX")
    return tuple(sorted(set(roster) | {"AURELIA"}))


def resolve_runtime_symbols(
    configured_raw: str,
    active_symbol_rows: list[dict],
    *,
    live_release_enabled: bool,
    max_symbols: int = 20,
) -> tuple[str, ...]:
    """Resolve symbols from broker metadata and explicit live allowlisting."""
    active: list[str] = []
    for row in active_symbol_rows:
        if not isinstance(row, dict):
            continue
        value = str(row.get("symbol") or row.get("underlying_symbol") or "").strip()
        if value and value not in active:
            active.append(value)
    available = set(active)
    if not available:
        raise RuntimeError("NO_DERIV_SYMBOLS_AVAILABLE")

    raw = str(configured_raw or "")
    if raw.strip():
        parts = [item.strip() for item in raw.split(",")]
        if not parts or any(not item for item in parts):
            raise RuntimeError("AURELIA_SYMBOL_ALLOWLIST_INVALID")
        if len(set(parts)) != len(parts):
            raise RuntimeError("AURELIA_SYMBOL_ALLOWLIST_HAS_DUPLICATES")
        unknown = [item for item in parts if item not in available]
        if unknown:
            raise RuntimeError("AURELIA_CONFIGURED_SYMBOL_NOT_ACTIVE")
        return tuple(parts)

    if live_release_enabled:
        raise RuntimeError("AURELIA_LIVE_SYMBOL_ALLOWLIST_REQUIRED")
    try:
        limit = int(max_symbols)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("AURELIA_MAX_SYMBOLS_INVALID") from exc
    if limit < 1:
        raise RuntimeError("AURELIA_MAX_SYMBOLS_INVALID")
    return tuple(active[:limit])


@dataclass
class ContinuousRuntime:
    federation: PersistentAgentFederation
    federation_supervisor: AgentFederationSupervisor
    performance_ledger: AgentPerformanceLedger | None = None
    agent_worker_supervisor: AgentWorkerSupervisor | None = None
    adapter: DerivAdapter | None = None
    execution_loop: AutonomousExecutionLoop | None = None
    execution_task: asyncio.Task[None] | None = None
    execution_restart_attempts: int = 0
    heartbeat_task: asyncio.Task[None] | None = None
    research_signal_task: asyncio.Task[None] | None = None

    async def stop(self) -> None:
        if self.execution_loop is not None:
            self.execution_loop.stop()
        if self.research_signal_task is not None:
            self.research_signal_task.cancel()
            try:
                await self.research_signal_task
            except asyncio.CancelledError:
                pass
            self.research_signal_task = None
        if self.heartbeat_task is not None:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            self.heartbeat_task = None
        if self.agent_worker_supervisor is not None:
            await self.agent_worker_supervisor.stop()
            self.agent_worker_supervisor = None
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
    source_hash = (
        os.getenv("GITHUB_SHA", "").strip()
        or os.getenv("AURELIA_SOURCE_SHA", "").strip()
        or "RUNTIME_UNPINNED"
    )
    if federation is None:
        federation = PersistentAgentFederation(
            journal_path=os.getenv("AURELIA_FEDERATION_JOURNAL_PATH", "/tmp/aurelia/federation-events.ndjson"),
            lease_path=os.getenv("AURELIA_FEDERATION_LEASE_PATH", "/tmp/aurelia/federation-leases.json"),
            config_hash=config_hash,
            source_hash=source_hash,
            lease_seconds=float(os.getenv("AURELIA_AGENT_LEASE_SECONDS", "45")),
            performance_path=os.getenv("AURELIA_AGENT_PERFORMANCE_PATH", "/var/lib/aurelia/agent-performance.json"),
        )
    agents = load_runtime_agent_roster(ROOT)
    if federation_supervisor is None:
        federation_supervisor = AgentFederationSupervisor(
            federation,
            agents=agents,
            interval_seconds=float(os.getenv("AURELIA_AGENT_HEARTBEAT_SECONDS", "15")),
            roundtable_seconds=float(os.getenv("AURELIA_AGENT_ROUNDTABLE_SECONDS", "60")),
        )
        federation_supervisor.start()
    performance_ledger = AgentPerformanceLedger(
        os.getenv("AURELIA_AGENT_PERFORMANCE_PATH", "/var/lib/aurelia/agent-performance.json"),
        decay_days=float(os.getenv("AURELIA_AGENT_SCORE_DECAY_DAYS", "90")),
    )
    runtime = ContinuousRuntime(federation, federation_supervisor, performance_ledger=performance_ledger)

    if os.getenv("AURELIA_AGENT_WORKERS", "true").strip().lower() == "true":
        runtime.agent_worker_supervisor = AgentWorkerSupervisor(
            federation,
            agents=tuple(agent for agent in agents if agent != "AURELIA"),
            interval_seconds=float(os.getenv("AURELIA_AGENT_WORKER_HEARTBEAT_SECONDS", "10")),
        )
        runtime.agent_worker_supervisor.start()

    worker_id = os.getenv("AURELIA_WORKER_ID", "").strip() or (
        f"AURELIA:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"
    )

    async def worker_heartbeat() -> None:
        interval = max(1.0, min(federation.lease_seconds / 3.0, 15.0))
        while True:
            await federation.heartbeat("AURELIA", worker_id=worker_id, origin="WORKER")
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise

    runtime.heartbeat_task = asyncio.create_task(worker_heartbeat(), name=f"aurelia-worker-heartbeat:{worker_id}")

    if os.getenv("AURELIA_AUTONOMOUS_LOOP", "false").strip().lower() != "true":
        await federation.publish(
            sender="AURELIA", recipients=agents, message_type="RUNTIME_MODE",
            payload={"mode": "FEDERATED_BACKGROUND_RESEARCH", "capital_authority": False},
            correlation_id="runtime-mode", priority=70, requires_response=True,
        )
        return runtime

    token = get_optional_secret("DERIV_AUTH_TOKEN") or get_optional_secret("DERIV_PAT")
    loginid = os.getenv("DERIV_EXPECTED_LOGINID") or os.getenv("DERIV_AUTHORIZED_ACCOUNT_ID", "")
    auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower()
    app_id = get_optional_secret("DERIV_APP_ID")
    if not token or not loginid:
        await federation.publish(sender="AURELIA", recipients=agents, message_type="BLOCKER",
            payload={"reason": "DERIV_AUTH_CONFIGURATION_MISSING", "capital_authority": False},
            correlation_id="deriv-auth", priority=95, requires_response=True)
        return runtime
    if auth_mode not in {"pat", "oauth"}:
        await federation.publish(sender="AURELIA", recipients=agents, message_type="BLOCKER",
            payload={"reason": "DERIV_AUTH_MODE_INVALID", "capital_authority": False},
            correlation_id="deriv-auth-mode", priority=95, requires_response=True)
        return runtime
    if auth_mode == "pat" and not app_id:
        await federation.publish(sender="AURELIA", recipients=agents, message_type="BLOCKER",
            payload={"reason": "DERIV_APP_ID_REQUIRED_FOR_PAT", "capital_authority": False},
            correlation_id="deriv-app-id", priority=95, requires_response=True)
        return runtime

    expected_currency = os.getenv("DERIV_EXPECTED_CURRENCY", "").strip().upper()
    if not expected_currency:
        await federation.publish(sender="AURELIA", recipients=agents, message_type="BLOCKER",
            payload={"reason": "DERIV_EXPECTED_CURRENCY_MISSING", "capital_authority": False},
            correlation_id="deriv-currency", priority=95, requires_response=True)
        return runtime

    manager = DerivSessionManager(
        expected_loginid=loginid,
        expected_environment=os.getenv("DERIV_ENVIRONMENT", "real"),
        expected_currency=expected_currency,
    )
    bootstrap = manager.bootstrap(bearer_token=token, app_id=app_id or None)
    adapter = DerivAdapter(
        ws_url=bootstrap.websocket.url,
        expected_loginid=bootstrap.binding.loginid,
        expected_currency=bootstrap.binding.currency,
        environment=bootstrap.binding.environment,
        auth_token="",
    )
    account = await adapter.connect()
    capital = await adapter.get_balance()

    # Capture today's risk baseline from the authenticated broker statement.
    # Incomplete, truncated or inconsistent statement data blocks startup.
    observed_at = datetime.now(timezone.utc)
    day_start = datetime(observed_at.year, observed_at.month, observed_at.day, tzinfo=timezone.utc)
    open_contracts = await adapter.portfolio()
    if open_contracts:
        raise RuntimeError("DAILY_RISK_OPEN_CONTRACTS_REQUIRE_RECONCILIATION")
    statement = await adapter.statement(
        limit=999,
        date_from=int(day_start.timestamp()),
        date_to=int(observed_at.timestamp()),
    )
    capital = await adapter.get_balance()
    if capital.account != account or capital.currency != account.currency or not capital.is_valid():
        raise RuntimeError("DAILY_RISK_BROKER_CAPITAL_UNVERIFIED")
    reference_balance, baseline_source = derive_utc_day_start_balance(
        current_balance=capital.balance,
        transactions=statement,
        day_start_epoch=int(day_start.timestamp()),
        day_end_epoch=int(observed_at.timestamp()),
        currency=account.currency,
        maximum_transactions=999,
    )
    daily_risk_guard = PersistentDailyRiskGuard(
        os.getenv("AURELIA_DAILY_RISK_PATH", "/var/lib/aurelia/daily-risk.json"),
        max_daily_drawdown_pct=float(os.getenv("AURELIA_MAX_DAILY_DRAWDOWN_PCT", "0.03")),
        max_consecutive_losses=int(os.getenv("AURELIA_MAX_CONSECUTIVE_LOSSES", "3")),
        max_balance_age_seconds=float(os.getenv("AURELIA_MAX_BALANCE_AGE_SECONDS", "15")),
    )
    daily_risk_guard.initialize_day(
        account_loginid=account.loginid,
        currency=account.currency,
        utc_day=observed_at.date().isoformat(),
        reference_balance=reference_balance,
        baseline_source=baseline_source,
        now=observed_at,
    )

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
        daily_risk_guard=daily_risk_guard,
        max_trade_risk_pct=float(os.getenv("AURELIA_MAX_TRADE_RISK_PCT", "0.01")),
        kill_switch_state_path=os.getenv(
            "AURELIA_KILL_SWITCH_STATE_PATH",
            "/var/lib/aurelia/kill-switch-state.json",
        ),
        operator_reset_path=os.getenv(
            "AURELIA_OPERATOR_RESET_PATH",
            "/run/aurelia/operator-kill-switch-reset.json",
        ),
        operator_reset_signing_key=get_optional_secret("AURELIA_OPERATOR_RESET_SIGNING_KEY"),
    )
    symbols_raw = os.getenv("AURELIA_SYMBOLS", "")
    active = await adapter.active_symbols()
    symbols = resolve_runtime_symbols(
        symbols_raw,
        active,
        live_release_enabled=read_live_release(ROOT / "config" / "LIVE_LOCK.yaml").may_move_capital,
        max_symbols=os.getenv("AURELIA_MAX_SYMBOLS", "20"),
    )
    if os.getenv("AURELIA_RESEARCH_SIGNAL_HUNT", "true").strip().lower() == "true":
        research_supervisor = build_research_signal_supervisor(adapter, federation, symbols)
        runtime.research_signal_task = research_supervisor.start_task()
        await federation.publish(
            sender="AURELIA", recipients=agents, message_type="RESEARCH_HUNT_STARTED",
            payload={"symbol_count": len(symbols), "capital_authority": False, "order_submission_permitted": False},
            correlation_id="research-hunt", priority=70, requires_response=False,
        )

    runtime.execution_loop = AutonomousExecutionLoop(
        adapter=adapter, executor=executor, decision_provider=FederatedDecisionProvider(federation),
        runtime_config_hash=config_hash, symbols=symbols,
        lifecycle_timeout_seconds=float(os.getenv("AURELIA_LIFECYCLE_TIMEOUT_SECONDS", "600")),
        daily_risk_guard=daily_risk_guard,
    )
    runtime.adapter = adapter
    runtime.execution_task = asyncio.create_task(runtime.execution_loop.run(), name="aurelia-autonomous-execution-loop")
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
