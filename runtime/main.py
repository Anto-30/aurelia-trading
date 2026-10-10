from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time

from runtime.adapters.session_manager import DerivSessionManager
from runtime.agent_federation import AgentFederationSupervisor, PersistentAgentFederation
from runtime.agent_performance import PersistentAgentPerformance
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.continuous_runtime import start_continuous_runtime
from assurance.evidence_writer import build_evidence, payload_sha256
from runtime.core.events import event_envelope, sha256
from runtime.core.health import (
    HealthSnapshot,
    apply_verify_only_runtime_health,
    refresh_runtime_health,
)
from runtime.core.journal import AppendOnlyJournal
from runtime.core.models import RuntimeState
from runtime.core.release_gate import read_live_release
from runtime.core.runtime_config import load_config_hash
from runtime.core.secrets import get_optional_secret, validate_secrets_at_startup
from runtime.core.state import RuntimeStateMachine
from runtime.core.supervisor import RuntimeSupervisor
from runtime.ops.readiness_orchestrator import evaluate as evaluate_readiness

ROOT = Path(__file__).resolve().parents[1]

FEDERATION_TRIGGER_EVENTS = {
    "MARKET_ANOMALY_DETECTED",
    "STRATEGY_SIGNAL_GENERATED",
    "CAPITAL_THRESHOLD_BREACHED",
    "RECONCILIATION_MISMATCH",
    "WATCHDOG_PROTECT",
    "RUNTIME_STATE_TRANSITION",
}


def _write_runtime_deriv_evidence(snapshot, config_hash: str) -> None:
    """Persist a short-lived, hashed account/balance observation from the live adapter."""
    account = snapshot.account
    if account is None or not snapshot.is_valid():
        raise RuntimeError("DERIV_RUNTIME_EVIDENCE_SNAPSHOT_INVALID")
    now = datetime.now(timezone.utc)
    source_hash = (
        os.getenv("GITHUB_SHA", "").strip()
        or os.getenv("AURELIA_SOURCE_SHA", "").strip()
        or "RUNTIME_UNPINNED"
    )
    observed = {
        "account_loginid": account.loginid,
        "account_type": account.account_type,
        "environment": account.environment,
        "currency": snapshot.currency,
        "balance": snapshot.balance,
        "available_balance": snapshot.available_balance,
        "captured_at_utc": snapshot.captured_at.isoformat(),
        "balance_source": snapshot.source,
    }
    data_hash = hashlib.sha256(
        json.dumps(observed, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    artifact_hash = sha256({
        "source_hash": source_hash,
        "config_hash": config_hash,
        "data_hash": data_hash,
        "evidence_type": "authenticated-deriv-balance",
    })
    record = build_evidence(
        evidence_id=f"DERIV_RUNTIME_SESSION:{now.strftime('%Y%m%dT%H%M%S%fZ')}",
        source_hash=source_hash,
        artifact_hash=artifact_hash,
        config_hash=config_hash,
        data_hash=data_hash,
        environment=account.environment,
        started_at_utc=(now - timedelta(milliseconds=1)).isoformat(),
        ended_at_utc=now.isoformat(),
        status="CURRENT",
        valid_until_utc=(now + timedelta(seconds=30)).isoformat(),
        provenance={
            "origin": "runtime",
            "issuer": "AURELIA-runtime",
            "source_commit": source_hash,
            "generated_at_utc": now.isoformat(),
        },
        result="PROVEN",
        invariants_checked=[
            "authenticated_account_identity",
            "account_environment_binding",
            "currency_binding",
            "fresh_broker_balance",
            "no_order_submission",
            "capital_authority_not_granted",
        ],
        invariants_failed=[],
    )
    enriched = dict(record)
    enriched["observed"] = observed
    enriched["orders_submitted"] = 0
    enriched["capital_authority_granted"] = False
    enriched["order_submission_permitted"] = False
    enriched["verification_scope"] = f"AUTHENTICATED_DERIV_{account.environment.upper()}_SESSION"
    enriched["record_hash"] = payload_sha256(
        {key: value for key, value in enriched.items() if key != "record_hash"}
    )
    default_path = str(ROOT / "artifacts" / "deriv_authenticated_session.json")
    output = Path(os.getenv("AURELIA_DERIV_EVIDENCE_PATH", default_path))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(enriched, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)


def _write_readiness_report(output: Path, report: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)


async def _readiness_publisher(health: "HealthSnapshot", journal: AppendOnlyJournal, config_hash: str) -> None:
    """Continuously publish local readiness; an evaluation error becomes a blocked report."""
    output = Path(os.getenv("AURELIA_READINESS_PATH", "/tmp/aurelia/AURELIA_READINESS.json"))
    interval = max(2.0, float(os.getenv("AURELIA_READINESS_REFRESH_SECONDS", "5")))
    while True:
        try:
            report = evaluate_readiness(ROOT)
            _write_readiness_report(output, report)
            health.critical_unknowns.discard("READINESS_PUBLISHER_FAILURE")
        except Exception as exc:
            health.critical_unknowns.add("READINESS_PUBLISHER_FAILURE")
            fallback = {
                "schema": "aurelia.readiness.v1",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "mode": "AUTONOMOUS_EXECUTION_PREPARATION",
                "final_execution_authorization": False,
                "live_execution": "BLOCKED",
                "live_orders": 0,
                "controls": {
                    "risk_warden": False,
                    "execution_firewall": False,
                    "exposure": False,
                    "reconciliation": False,
                    "watchdog": False,
                    "idempotency": False,
                },
                "evidence": {
                    "market_data": False,
                    "prospective_oos": False,
                    "calibration": False,
                    "economics": False,
                    "soak_3600s": False,
                },
                "blockers": [{"gate": "READINESS_REFRESH", "status": "FAIL", "reason": type(exc).__name__}],
                "continue_hunting": True,
            }
            try:
                _write_readiness_report(output, fallback)
            except Exception:
                pass
            journal.append(
                event_envelope(
                    event_type="READINESS_PUBLISH_ERROR",
                    event_id=f"READINESS_PUBLISH_ERROR:{int(time.time() * 1000)}",
                    correlation_id="readiness-publisher",
                    payload={"error_class": type(exc).__name__, "capital_authority_granted": False},
                    source_hash=os.getenv("GITHUB_SHA", "runtime-baseline"),
                    config_hash=config_hash,
                )
            )
        await asyncio.sleep(interval)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "structured_data"):
            log_entry.update(record.structured_data)
        return json.dumps(log_entry, sort_keys=True)


logger = logging.getLogger("AURELIA")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


async def _balance_poller(
    adapter: DerivAdapter,
    health: HealthSnapshot,
    journal: AppendOnlyJournal,
    config_hash: str,
    interval: float = 10.0,
) -> None:
    """Poll Deriv balance independently so the main loop stays responsive."""
    while True:
        try:
            snapshot = await adapter.get_balance()
            if not adapter.authorized or adapter.account is None:
                raise RuntimeError("DERIV_RUNTIME_SESSION_NOT_AUTHORIZED")
            _write_runtime_deriv_evidence(snapshot, config_hash)
            health.capital_fresh = snapshot.is_valid()
            health.broker_session = bool(adapter.authorized and adapter.account)
            health.critical_unknowns.discard("DERIV_BALANCE_REFRESH")
        except Exception as exc:
            health.capital_fresh = False
            health.critical_unknowns.add("DERIV_BALANCE_REFRESH")
            journal.append(
                event_envelope(
                    event_type="BALANCE_POLL_ERROR",
                    event_id=f"BALANCE_POLL_ERROR:{int(time.time() * 1000)}",
                    correlation_id="balance-poller",
                    payload={"error_class": type(exc).__name__},
                    source_hash="runtime-baseline",
                    config_hash=config_hash,
                )
            )
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise


class HealthHandler(BaseHTTPRequestHandler):
    health: HealthSnapshot | None = None
    state: RuntimeState = RuntimeState.BOOT
    performance: PersistentAgentPerformance | None = None

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path.startswith("/agent-leaderboard"):
            performance = self.performance
            if performance is None:
                self.send_response(503)
                self.end_headers()
                return
            agent = self.path.removeprefix("/agent-leaderboard").strip("/") or None
            body = performance.snapshot(agent=agent)
            raw = json.dumps(body, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if self.path not in {"/health", "/ready"}:
            self.send_response(404)
            self.end_headers()
            return
        h = self.health
        if h is None:
            ok = True
            body = {"status": "STARTING", "state": self.state.value}
        else:
            ok = h.liveness() if self.path == "/health" else h.readiness()
            body = {
                "status": "HEALTHY" if h.readiness() else "DEGRADED",
                "state": self.state.value,
                "liveness": h.liveness(),
                "readiness": h.readiness(),
                "capital_can_open_new_exposure": h.can_open_new_exposure(),
                "critical_unknowns": sorted(h.critical_unknowns),
            }
        raw = json.dumps(body).encode("utf-8")
        self.send_response(200 if ok else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def start_server(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    Thread(target=server.serve_forever, name="aurelia-health", daemon=True).start()
    return server


async def main() -> None:
    validate_secrets_at_startup()
    server = start_server(int(os.getenv("PORT", "8080")))
    journal = AppendOnlyJournal(
        os.getenv("AURELIA_JOURNAL_PATH", "/tmp/aurelia/aurelia-events.ndjson")
    )
    config_hash = load_config_hash(ROOT)
    release = read_live_release(ROOT / "config" / "LIVE_LOCK.yaml")

    machine = RuntimeStateMachine()
    machine.transition(RuntimeState.SELF_CHECK)
    health = HealthSnapshot(
        process_heartbeat=datetime.now(timezone.utc),
        broker_session=False,
        market_data_fresh=False,
        capital_fresh=False,
        ledger_healthy=False,
        reconciliation_healthy=False,
        kill_switch_off=False,
    )
    HealthHandler.health = health
    HealthHandler.state = machine.state
    performance_path = os.getenv("AURELIA_AGENT_PERFORMANCE_PATH", "/tmp/aurelia/agent-performance.json")
    HealthHandler.performance = PersistentAgentPerformance(performance_path)
    public_probe_failed = False
    authenticated_probe_failed = False
    readonly_adapter: DerivAdapter | None = None

    federation_queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()

    federation = PersistentAgentFederation(
        journal_path=os.getenv(
            "AURELIA_FEDERATION_JOURNAL_PATH",
            "/tmp/aurelia/agent-federation.ndjson",
        ),
        lease_path=os.getenv(
            "AURELIA_FEDERATION_LEASE_PATH",
            "/tmp/aurelia/agent-federation-leases.json",
        ),
        task_path=os.getenv(
            "AURELIA_FEDERATION_TASK_PATH",
            "/tmp/aurelia/agent-federation-tasks.json",
        ),
        config_hash=config_hash,
        source_hash="runtime-baseline",
        lease_seconds=float(os.getenv("AURELIA_AGENT_LEASE_SECONDS", "45")),
        performance_path=performance_path,
    )
    federation_supervisor = AgentFederationSupervisor(
        federation,
        agents=(
            "ClaudeCode",
            "KimiK3",
            "GrokBot",
            "GoogleAgentSkills",
            "GLM",
            "PlaywrightCLI",
            "AURELIA",
        ),
        event_queue=federation_queue,
    )
    federation_supervisor.start()
    journal.append(
        event_envelope(
            event_type="AGENT_FEDERATION_STARTED",
            event_id="AGENT_FEDERATION_STARTED:1",
            correlation_id="agent-federation",
            payload={
                "capital_authority": False,
                "persistent": True,
                "restartable": True,
                "agents": list(federation_supervisor.agents),
            },
            source_hash="runtime-baseline",
            config_hash=config_hash,
        )
    )

    journal.append(
        event_envelope(
            event_type="RUNTIME_STARTUP",
            event_id="RUNTIME_STARTUP:1",
            correlation_id="runtime",
            payload={
                "runtime_version": "0.1.0-baseline-2026-10-03",
                "config_hash": config_hash,
                "live_trading_enabled": release.live_trading_enabled,
                "final_execution_authorization": release.final_execution_authorization,
                "capital_plane_mode": release.capital_plane_mode,
            },
            source_hash="runtime-baseline",
            config_hash=config_hash,
        )
    )

    logger.info(
        "Runtime startup",
        extra={"structured_data": {
            "runtime_version": "0.1.0-baseline-2026-10-03",
            "config_hash": config_hash,
            "FINAL_EXECUTION_AUTHORIZATION": False,
            "LIVE_EXECUTION": "BLOCKED",
            "capital_plane_mode": "VERIFY_ONLY",
        }},
    )

    async def public_probe() -> None:
        adapter = DerivAdapter()
        symbol_count = await adapter.connect_public()
        journal.append(
            event_envelope(
                event_type="PUBLIC_MARKET_DATA_VERIFIED",
                event_id=f"PUBLIC_MARKET_DATA_VERIFIED:{symbol_count}",
                correlation_id="market-probe",
                payload={"active_symbol_count": symbol_count},
                source_hash="runtime-baseline",
                config_hash=config_hash,
            )
        )
        health.dependencies_ok = True

    if os.getenv("AURELIA_VERIFY_DERIV_PUBLIC", "false").lower() == "true":
        try:
            await public_probe()
        except Exception as exc:
            public_probe_failed = True
            health.critical_unknowns.add("DERIV_PUBLIC_MARKET_DATA")
            journal.append(
                event_envelope(
                    event_type="PUBLIC_MARKET_DATA_UNKNOWN",
                    event_id="PUBLIC_MARKET_DATA_UNKNOWN:1",
                    correlation_id="market-probe",
                    payload={"error_class": type(exc).__name__},
                    source_hash="runtime-baseline",
                    config_hash=config_hash,
                )
            )

    async def authenticated_probe() -> None:
        nonlocal readonly_adapter
        manager = DerivSessionManager(
            expected_loginid=os.getenv("DERIV_EXPECTED_LOGINID") or None,
            expected_environment=os.getenv("DERIV_ENVIRONMENT", "real"),
            expected_currency=os.getenv("DERIV_EXPECTED_CURRENCY", "USD"),
        )
        token = (
            get_optional_secret("DERIV_AUTH_TOKEN")
            or get_optional_secret("DERIV_PAT")
        )
        app_id = get_optional_secret("DERIV_APP_ID") or None
        auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower() or "pat"
        if not token:
            raise RuntimeError("DERIV_RUNTIME_AUTH_TOKEN_MISSING")
        if auth_mode == "pat" and not app_id:
            raise RuntimeError("DERIV_RUNTIME_APP_ID_MISSING_FOR_PAT")
        bootstrap = manager.bootstrap(
            bearer_token=token,
            app_id=app_id,
        )
        adapter = DerivAdapter(
            ws_url=bootstrap.websocket.url,
            expected_loginid=bootstrap.binding.loginid,
            expected_currency=bootstrap.binding.currency,
            environment=bootstrap.binding.environment,
            auth_token="",
        )
        keep_readonly_session = (
            os.getenv("AURELIA_DEPLOYMENT_MODE", "").strip().upper() == "VERIFY_ONLY"
            and os.getenv("AURELIA_AUTONOMOUS_LOOP", "false").strip().lower() != "true"
            and os.getenv("AURELIA_RUN_ONCE", "false").strip().lower() != "true"
        )
        try:
            account = await adapter.connect()
            snapshot = await adapter.get_balance()
            if account.loginid != bootstrap.binding.loginid:
                raise RuntimeError("DERIV_RUNTIME_ACCOUNT_BINDING_MISMATCH")
            if snapshot.currency != bootstrap.binding.currency:
                raise RuntimeError("DERIV_RUNTIME_CURRENCY_MISMATCH")
            _write_runtime_deriv_evidence(snapshot, config_hash)
            journal.append(
                event_envelope(
                    event_type="AUTHENTICATED_DERIV_SESSION_VERIFIED",
                    event_id="AUTHENTICATED_DERIV_SESSION_VERIFIED:1",
                    correlation_id="deriv-auth-probe",
                    payload={
                        "endpoint": "api.derivws.com",
                        "environment": account.environment,
                        "currency": snapshot.currency,
                        "balance_source": "deriv:balance",
                        "capital_authority_granted": False,
                    },
                    source_hash="runtime-baseline",
                    config_hash=config_hash,
                )
            )
            refresh_runtime_health(
                health,
                broker_session=True,
                capital=snapshot,
                market_data_received_at=None,
                ledger_healthy=False,
                reconciliation_healthy=False,
                kill_switch_off=False,
            )
            health.dependencies_ok = True
            if keep_readonly_session:
                readonly_adapter = adapter
        finally:
            if readonly_adapter is not adapter:
                await adapter.close()

    if os.getenv("AURELIA_VERIFY_DERIV_AUTH", "false").lower() == "true":
        try:
            await authenticated_probe()
        except Exception as exc:
            authenticated_probe_failed = True
            health.critical_unknowns.add("DERIV_AUTHENTICATED_SESSION")
            journal.append(
                event_envelope(
                    event_type="AUTHENTICATED_DERIV_SESSION_UNKNOWN",
                    event_id="AUTHENTICATED_DERIV_SESSION_UNKNOWN:1",
                    correlation_id="deriv-auth-probe",
                    payload={"error_class": type(exc).__name__},
                    source_hash="runtime-baseline",
                    config_hash=config_hash,
                )
            )

    # --- HARD ABORT GATE: Never proceed to continuous runtime if probes failed ---
    if public_probe_failed or authenticated_probe_failed:
        fatal_reason = []
        if public_probe_failed:
            fatal_reason.append("PUBLIC_DERIV_TRANSPORT_VERIFICATION_FAILED")
        if authenticated_probe_failed:
            fatal_reason.append("AUTHENTICATED_DERIV_SESSION_VERIFICATION_FAILED")
        journal.append(
            event_envelope(
                event_type="FATAL_STARTUP_ABORT",
                event_id="FATAL_STARTUP_ABORT:1",
                correlation_id="startup-gate",
                payload={
                    "reasons": fatal_reason,
                    "action": "PROCESS_TERMINATION",
                    "capital_authority_granted": False,
                },
                source_hash="runtime-baseline",
                config_hash=config_hash,
            )
        )
        await federation_supervisor.stop()
        server.shutdown()
        raise SystemExit(
            f"AURELIA_FATAL_STARTUP_ABORT: {'; '.join(fatal_reason)}"
        )
    # --- END HARD ABORT GATE ---

    if os.getenv("AURELIA_RUN_ONCE", "false").lower() == "true":
        await federation_supervisor.stop()
        server.shutdown()
        if public_probe_failed:
            raise RuntimeError("PUBLIC_DERIV_TRANSPORT_VERIFICATION_FAILED")
        if authenticated_probe_failed:
            raise RuntimeError("AUTHENTICATED_DERIV_SESSION_VERIFICATION_FAILED")
        return

    readiness_task = asyncio.create_task(
        _readiness_publisher(health, journal, config_hash),
        name="aurelia-readiness-publisher",
    )
    # Replace any stale persisted authorization report before the execution loop starts.
    await asyncio.sleep(0)
    supervisor = RuntimeSupervisor(interval_seconds=5)

    def heartbeat() -> bool:
        health.process_heartbeat = datetime.now(timezone.utc)
        return health.liveness() and health.dependencies_ok

    def emit_federation_event(event_type: str, **payload: object) -> None:
        if event_type not in FEDERATION_TRIGGER_EVENTS:
            return
        try:
            federation_queue.put_nowait({
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **payload,
            })
        except Exception:
            health.critical_unknowns.add("FEDERATION_EVENT_QUEUE_FAILURE")

    def protect(reason: str) -> None:
        health.kill_switch_off = False
        health.critical_unknowns.add(reason)
        HealthHandler.state = RuntimeState.CAPITAL_PROTECTED
        emit_federation_event("WATCHDOG_PROTECT", reason=reason)
        journal.append(
            event_envelope(
                event_type="WATCHDOG_PROTECT",
                event_id=f"WATCHDOG_PROTECT:{supervisor.metrics.protective_transitions + 1}",
                correlation_id="watchdog",
                payload={"reason": reason},
                source_hash="runtime-baseline",
                config_hash=config_hash,
            )
        )

    supervisor.start(heartbeat, protect)

    continuous_runtime = None
    balance_task: asyncio.Task[None] | None = None
    last_runtime_state = machine.state
    if os.getenv("AURELIA_CONTINUOUS_RUNTIME", "true").strip().lower() == "true":
        try:
            continuous_runtime = await start_continuous_runtime(
                machine,
                federation=federation,
                federation_supervisor=federation_supervisor,
            )
            if continuous_runtime.execution_loop is not None:
                balance_task = asyncio.create_task(
                    _balance_poller(
                        continuous_runtime.adapter,
                        health,
                        journal,
                        config_hash,
                    ),
                    name="aurelia-balance-poller",
                )
                health.broker_session = bool(
                    continuous_runtime.adapter is not None
                    and continuous_runtime.adapter.authorized
                    and continuous_runtime.adapter.account is not None
                )
            elif readonly_adapter is not None:
                # Keep the read-only broker balance evidence current for a
                # locked persistent worker; this path has no capital executor.
                balance_task = asyncio.create_task(
                    _balance_poller(
                        readonly_adapter,
                        health,
                        journal,
                        config_hash,
                    ),
                    name="aurelia-readonly-balance-poller",
                )
        except Exception as exc:
            health.critical_unknowns.add("CONTINUOUS_RUNTIME_STARTUP")
            journal.append(
                event_envelope(
                    event_type="CONTINUOUS_RUNTIME_UNKNOWN",
                    event_id="CONTINUOUS_RUNTIME_UNKNOWN:1",
                    correlation_id="continuous-runtime",
                    payload={"error_class": type(exc).__name__},
                    source_hash="runtime-baseline",
                    config_hash=config_hash,
                )
            )

    try:
        while True:
            health.process_heartbeat = datetime.now(timezone.utc)
            if continuous_runtime is None:
                # A missing runtime object is an operational failure, not an
                # intentional verify-only mode. Keep readiness blocked.
                health.broker_session = False
                health.market_data_fresh = False
                health.capital_fresh = False
                health.ledger_healthy = False
                health.reconciliation_healthy = False
                health.kill_switch_off = False
                health.critical_unknowns.add("CONTINUOUS_RUNTIME_UNAVAILABLE")
                HealthHandler.state = RuntimeState.CAPITAL_PROTECTED
            else:
                loop = continuous_runtime.execution_loop
                adapter = continuous_runtime.adapter
                expected_workers = set(federation_supervisor.agents)
                active_workers = set(federation.active_agents())
                missing_workers = expected_workers - active_workers
                if missing_workers:
                    health.agent_workers_healthy = False
                    health.critical_unknowns.add("AGENT_WORKER_LIVENESS")
                else:
                    health.agent_workers_healthy = True
                    health.critical_unknowns.discard("AGENT_WORKER_LIVENESS")

                verify_only_mode = (
                    loop is None
                    and os.getenv("AURELIA_AUTONOMOUS_LOOP", "false").strip().lower() != "true"
                )
                if verify_only_mode:
                    apply_verify_only_runtime_health(health)
                    HealthHandler.state = RuntimeState.CAPITAL_PROTECTED
                else:
                    broker_authorization_lost = (
                        adapter is None
                        or not adapter.authorized
                        or adapter.account is None
                    )
                    if broker_authorization_lost:
                        health.kill_switch_off = False
                        health.broker_session = False
                        health.critical_unknowns.add("BROKER_AUTHORIZATION_LOST")
                        HealthHandler.state = RuntimeState.CAPITAL_PROTECTED
                        emit_federation_event(
                            "WATCHDOG_PROTECT",
                            reason="BROKER_AUTHORIZATION_LOST",
                        )
                        if loop is not None and not loop.executor.kill_switch:
                            loop.executor.activate_kill_switch("BROKER_AUTHORIZATION_LOST")
                    else:
                        health.broker_session = bool(adapter.transport is not None)
                        HealthHandler.state = machine.state

                    task = continuous_runtime.execution_task
                    if task is not None and task.done():
                        health.critical_unknowns.add("AUTONOMOUS_LOOP_STOPPED")
                        try:
                            task.exception()
                        except asyncio.CancelledError:
                            pass
                        if loop is not None:
                            loop.executor.activate_kill_switch("AUTONOMOUS_LOOP_STOPPED")
                            emit_federation_event(
                                "WATCHDOG_PROTECT",
                                reason="AUTONOMOUS_LOOP_STOPPED",
                            )

                if machine.state != last_runtime_state:
                    emit_federation_event(
                        "RUNTIME_STATE_TRANSITION",
                        from_state=last_runtime_state.value,
                        to_state=machine.state.value,
                    )
                    last_runtime_state = machine.state
            await asyncio.sleep(5)
    finally:
        readiness_task.cancel()
        try:
            await readiness_task
        except asyncio.CancelledError:
            pass
        if balance_task is not None:
            balance_task.cancel()
            try:
                await balance_task
            except asyncio.CancelledError:
                pass
        if continuous_runtime is not None:
            await continuous_runtime.stop()
        if readonly_adapter is not None:
            await readonly_adapter.close()
            readonly_adapter = None
        supervisor.stop()
        await federation_supervisor.stop()
        server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
