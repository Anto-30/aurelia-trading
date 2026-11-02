from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Iterable

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor

# AURELIA is the deterministic capital-plane authority, not an advisory
# provider worker. The supervisor intentionally skips it.
ADVISORY_WORKERS = (
    "ClaudeCode",
    "KimiK3",
    "GrokBot",
    "GoogleAgentSkills",
    "GLM",
    "PlaywrightCLI",
    "JEV",
)
CAPITAL_AUTHORITY = "AURELIA"


def connector_status_snapshot(federation: PersistentAgentFederation, agents: Iterable[str]) -> dict[str, str]:
    """Return the latest supervisor-observed command state, never provider authentication."""
    snapshot: dict[str, str] = {}
    for agent in agents:
        messages = federation.messages_for(agent, limit=1000)
        statuses = [
            message for message in messages
            if message.get("message_type") == "CONNECTOR_STATUS"
        ]
        if not statuses:
            snapshot[agent] = "UNKNOWN"
            continue
        latest = max(statuses, key=lambda message: str(message.get("created_at", "")))
        payload = latest.get("payload", {})
        snapshot[agent] = (
            str(payload.get("provider_session", "UNKNOWN"))
            if isinstance(payload, dict)
            else "UNKNOWN"
        )
    return snapshot


async def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aurelia-agent-probe-") as tmp:
        root = Path(tmp)
        federation = PersistentAgentFederation(
            journal_path=root / "journal.ndjson",
            lease_path=root / "leases.json",
            task_path=root / "tasks.json",
            config_hash="probe",
            source_hash="probe",
            lease_seconds=45,
        )
        workers = AgentWorkerSupervisor(
            federation, agents=(*ADVISORY_WORKERS, CAPITAL_AUTHORITY), interval_seconds=2
        )
        workers.start()
        try:
            await asyncio.sleep(0.25)
            active = set(federation.active_agents())
            connector_status = connector_status_snapshot(federation, ADVISORY_WORKERS)
            configured = {
                agent for agent, state in connector_status.items()
                if state == "CONFIGURED_COMMAND"
            }
            unconfigured = {
                agent for agent, state in connector_status.items()
                if state == "NOT_CONFIGURED"
            }
            unknown = {
                agent for agent, state in connector_status.items()
                if state == "UNKNOWN"
            }
            missing_process = sorted(configured - active)
            unexpected = sorted(active - configured)
            capital_heartbeat = CAPITAL_AUTHORITY in active

            print("AGENT_WORKER_ACTIVE=" + ",".join(sorted(active)))
            print("AGENT_WORKER_MISSING_PROCESS=" + ",".join(missing_process))
            print("AGENT_CONNECTOR_CONFIGURED=" + ",".join(sorted(configured)))
            print("AGENT_CONNECTOR_REQUIRED=" + ",".join(sorted(unconfigured)))
            print("AGENT_CONNECTOR_STATUS_UNKNOWN=" + ",".join(sorted(unknown)))
            print("AGENT_PROVIDER_AUTHENTICATION=NOT_VERIFIED")
            print("AGENT_PROVIDER_READINESS=BLOCKED_AUTHENTICATION_PROOF_MISSING")
            print("AGENT_WORKER_LIVENESS=" + (
                "FAIL" if missing_process or unexpected or unknown or capital_heartbeat
                else "PASS" if configured
                else "NO_CONFIGURED_WORKERS"
            ))
            print("CAPITAL_AUTHORITY_WORKER=INTENTIONALLY_DISABLED")
            print("CAPITAL_AUTHORITY_RUNTIME=DETERMINISTIC_CONTROL_PLANE")
            print("CAPITAL_AUTHORITY_HEARTBEAT=" + ("UNEXPECTED" if capital_heartbeat else "NOT_A_WORKER"))
            return 1 if missing_process or unexpected or unknown or capital_heartbeat else 0
        finally:
            await workers.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
