from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.core.events import event_envelope
from runtime.core.health import HealthSnapshot
from runtime.core.journal import AppendOnlyJournal
from runtime.core.models import RuntimeState
from runtime.core.release_gate import read_live_release
from runtime.core.runtime_config import load_config_hash
from runtime.core.state import RuntimeStateMachine
from runtime.core.supervisor import RuntimeSupervisor

ROOT = Path(__file__).resolve().parents[1]


class HealthHandler(BaseHTTPRequestHandler):
    health: HealthSnapshot | None = None
    state: RuntimeState = RuntimeState.BOOT

    def log_message(self, format, *args):
        return

    def do_GET(self):
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
        ledger_healthy=True,
        reconciliation_healthy=False,
        kill_switch_off=False,
    )
    HealthHandler.health = health
    HealthHandler.state = machine.state

    startup = event_envelope(
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
    journal.append(startup)

    print(
        json.dumps(
            {
                "component": "AURELIA",
                "runtime_version": "0.1.0-baseline-2026-10-03",
                "config_hash": config_hash,
                "FINAL_EXECUTION_AUTHORIZATION": False,
                "LIVE_EXECUTION": "BLOCKED",
                "capital_plane_mode": "VERIFY_ONLY",
            },
            sort_keys=True,
        )
    )

    async def public_probe() -> None:
        adapter = DerivAdapter()
        try:
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
        except Exception as exc:
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

    if os.getenv("AURELIA_VERIFY_DERIV_PUBLIC", "false").lower() == "true":
        await public_probe()

    supervisor = RuntimeSupervisor(interval_seconds=5)

    def heartbeat() -> bool:
        health.process_heartbeat = datetime.now(timezone.utc)
        return health.liveness() and health.dependencies_ok

    def protect(reason: str) -> None:
        health.kill_switch_off = False
        health.critical_unknowns.add(reason)
        HealthHandler.state = RuntimeState.CAPITAL_PROTECTED
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

    try:
        while True:
            health.process_heartbeat = datetime.now(timezone.utc)
            # This baseline intentionally stays capital-protected. Future live
            # releases must change the reviewed LIVE_LOCK and evidence state;
            # runtime code does not self-authorize.
            health.kill_switch_off = False
            health.broker_session = False
            health.market_data_fresh = False
            health.capital_fresh = False
            health.reconciliation_healthy = False
            HealthHandler.state = RuntimeState.CAPITAL_PROTECTED
            await asyncio.sleep(5)
    finally:
        supervisor.stop()
        server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
