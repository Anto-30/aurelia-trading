from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor

# AURELIA is the deterministic capital-plane authority, not an advisory
# provider worker. The connector supervisor intentionally skips it.
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
KNOWN_PROVIDER_SESSIONS = {
    "NOT_CONFIGURED",
    "COMMAND_CONFIGURED_PROTOCOL_UNVERIFIED",
}


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
            # Allow local supervisor coroutines to publish connector status.
            await asyncio.sleep(0.25)
            active_leases = set(federation.active_agents())
            missing_status: list[str] = []
            connector_required: list[str] = []
            command_configured: list[str] = []
            command_missing: list[str] = []

            for agent in ADVISORY_WORKERS:
                messages = federation.messages_for(agent, limit=100)
                status = next(
                    (item for item in messages if item.get("message_type") == "CONNECTOR_STATUS"),
                    None,
                )
                required = next(
                    (item for item in messages if item.get("message_type") == "CONNECTOR_REQUIRED"),
                    None,
                )
                payload = status.get("payload", {}) if isinstance(status, dict) else {}
                session = payload.get("provider_session") if isinstance(payload, dict) else None

                if (
                    not isinstance(payload, dict)
                    or session not in KNOWN_PROVIDER_SESSIONS
                    or payload.get("provider_authentication") != "NOT_VERIFIED"
                    or payload.get("provider_process") != "NOT_STARTED"
                    or payload.get("worker_protocol") != "NOT_IMPLEMENTED"
                    or required is None
                ):
                    missing_status.append(agent)
                    continue

                if required is not None:
                    connector_required.append(agent)
                if session == "COMMAND_CONFIGURED_PROTOCOL_UNVERIFIED":
                    command_configured.append(agent)
                else:
                    command_missing.append(agent)

            print("AGENT_PROVIDER_CONNECTOR_STATUS_REPORTED=" + ",".join(sorted(set(ADVISORY_WORKERS) - set(missing_status))))
            print("AGENT_PROVIDER_CONNECTOR_STATUS_MISSING=" + ",".join(sorted(missing_status)))
            print("AGENT_LOCAL_WORKER_LEASES_ACTIVE=" + ",".join(sorted(active_leases)))
            print("AGENT_CONNECTOR_REQUIRED=" + ",".join(sorted(connector_required)))
            print("AGENT_PROVIDER_COMMAND_CONFIGURED_UNVERIFIED=" + ",".join(sorted(command_configured)))
            print("AGENT_PROVIDER_COMMAND_MISSING=" + ",".join(sorted(command_missing)))
            print("AGENT_PROVIDER_PROCESS=NOT_STARTED")
            print("AGENT_PROVIDER_AUTHENTICATION=NOT_VERIFIED")
            print("AGENT_PROVIDER_READINESS=BLOCKED_PROTOCOL_AND_AUTH_HANDSHAKE_MISSING")
            print("CAPITAL_AUTHORITY_WORKER=INTENTIONALLY_DISABLED")
            print("CAPITAL_AUTHORITY_RUNTIME=DETERMINISTIC_CONTROL_PLANE")
            print("CAPITAL_AUTHORITY_HEARTBEAT=" + (
                "UNEXPECTED" if CAPITAL_AUTHORITY in active_leases else "NOT_A_WORKER"
            ))

            # A successful probe means the unavailable state is explicit and
            # accurately represented. It does not mean provider connectivity passed.
            return 1 if missing_status or active_leases else 0
        finally:
            await workers.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
