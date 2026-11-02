from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor

# AURELIA is the deterministic capital-plane authority, not an advisory
# provider worker. The worker supervisor intentionally skips it.
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
        for agent in ADVISORY_WORKERS:
            await federation.enqueue_task(
                task_type="PROVIDER_CONNECTIVITY_PROBE",
                payload={
                    "read_only": True,
                    "capital_authority": False,
                    "description": "Verify provider connector only; no broker or trading actions",
                },
                correlation_id=f"provider-probe:{agent}",
                priority=95,
                assigned_agent=agent,
            )

        workers = AgentWorkerSupervisor(
            federation, agents=(*ADVISORY_WORKERS, CAPITAL_AUTHORITY), interval_seconds=2
        )
        workers.start()
        try:
            await asyncio.sleep(2.5)
            active = set(federation.active_agents())
            missing = sorted(set(ADVISORY_WORKERS) - active)
            unexpected = sorted(active - set(ADVISORY_WORKERS))
            capital_heartbeat = CAPITAL_AUTHORITY in active

            command_configured: list[str] = []
            command_missing: list[str] = []
            connector_required: list[str] = []
            for agent in ADVISORY_WORKERS:
                messages = federation.messages_for(agent, limit=100)
                status = next(
                    (item for item in messages if item.get("message_type") == "CONNECTOR_STATUS"),
                    None,
                )
                session = (
                    status.get("payload", {}).get("provider_session")
                    if isinstance(status, dict)
                    else None
                )
                if session == "NOT_CONFIGURED":
                    command_missing.append(agent)
                elif session == "COMMAND_CONFIGURED_PROTOCOL_UNVERIFIED":
                    command_configured.append(agent)
                if any(item.get("message_type") == "CONNECTOR_REQUIRED" for item in messages):
                    connector_required.append(agent)

            print("AGENT_LOCAL_WORKER_LEASES_ACTIVE=" + ",".join(sorted(active)))
            # Retain the legacy field, but make its local-lease meaning explicit above.
            print("AGENT_WORKER_ACTIVE=" + ",".join(sorted(active)))
            print("AGENT_WORKER_MISSING=" + ",".join(missing))
            print("AGENT_WORKER_UNEXPECTED=" + ",".join(unexpected))
            print("AGENT_PROVIDER_COMMAND_CONFIGURED=" + ",".join(sorted(command_configured)))
            print("AGENT_PROVIDER_COMMAND_MISSING=" + ",".join(sorted(command_missing)))
            print("AGENT_CONNECTOR_REQUIRED=" + ",".join(sorted(connector_required)))
            print("AGENT_PROVIDER_AUTHENTICATION=NOT_VERIFIED")
            print("AGENT_PROVIDER_TASK_EXECUTION=BLOCKED_UNTIL_PROTOCOL_AND_HANDSHAKE")
            print("CAPITAL_AUTHORITY_WORKER=INTENTIONALLY_DISABLED")
            print("CAPITAL_AUTHORITY_RUNTIME=DETERMINISTIC_CONTROL_PLANE")
            print("CAPITAL_AUTHORITY_HEARTBEAT=" + ("UNEXPECTED" if capital_heartbeat else "NOT_A_WORKER"))
            if command_missing or command_configured:
                print("::warning::Local worker leases are not authenticated provider sessions; provider tasks remain blocked.")
            return 1 if missing or unexpected or capital_heartbeat else 0
        finally:
            await workers.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
