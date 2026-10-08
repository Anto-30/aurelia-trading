from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor

# AURELIA is the deterministic capital-plane authority, not an advisory
# provider worker. The worker supervisor intentionally skips it. All other
# registered agents are advisory/engineering workers and must obtain leases.
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
            await asyncio.sleep(2.5)
            active = set(federation.active_agents())
            missing = sorted(set(ADVISORY_WORKERS) - active)
            unexpected = sorted(active - set(ADVISORY_WORKERS))
            capital_heartbeat = CAPITAL_AUTHORITY in active
            print("AGENT_WORKER_ACTIVE=" + ",".join(sorted(active)))
            print("AGENT_WORKER_MISSING=" + ",".join(missing))
            print("AGENT_WORKER_UNEXPECTED=" + ",".join(unexpected))
            print("CAPITAL_AUTHORITY_WORKER=INTENTIONALLY_DISABLED")
            print("CAPITAL_AUTHORITY_RUNTIME=DETERMINISTIC_CONTROL_PLANE")
            print("CAPITAL_AUTHORITY_HEARTBEAT=" + ("UNEXPECTED" if capital_heartbeat else "NOT_A_WORKER"))
            return 1 if missing or unexpected or capital_heartbeat else 0
        finally:
            await workers.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
