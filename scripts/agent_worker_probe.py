from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor

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
        workers = AgentWorkerSupervisor(
            federation, agents=(*ADVISORY_WORKERS, CAPITAL_AUTHORITY), interval_seconds=2
        )
        workers.start()
        try:
            await asyncio.sleep(0.1)
            active = set(federation.active_agents())
            connector_required = sorted(
                agent
                for agent in ADVISORY_WORKERS
                if any(
                    row["message_type"] == "CONNECTOR_REQUIRED"
                    for row in federation.messages_for(agent)
                )
            )
            unexpected = sorted(active - set(ADVISORY_WORKERS))
            capital_heartbeat = CAPITAL_AUTHORITY in active
            print("AGENT_WORKER_ACTIVE=" + ",".join(sorted(active)))
            print("AGENT_CONNECTOR_REQUIRED=" + ",".join(connector_required))
            print("AGENT_PROVIDER_READY=0")
            print("AGENT_WORKER_PROBE=PASS_NO_AUTHENTICATED_PROVIDERS" if (
                not active
                and connector_required == sorted(ADVISORY_WORKERS)
                and not unexpected
                and not capital_heartbeat
            ) else "AGENT_WORKER_PROBE=FAIL")
            print("CAPITAL_AUTHORITY_WORKER=INTENTIONALLY_DISABLED")
            print("CAPITAL_AUTHORITY_HEARTBEAT=" + (
                "UNEXPECTED" if capital_heartbeat else "NOT_A_WORKER"
            ))
            return 0 if (
                not active
                and connector_required == sorted(ADVISORY_WORKERS)
                and not unexpected
                and not capital_heartbeat
            ) else 1
        finally:
            await workers.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
