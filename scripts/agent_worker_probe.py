from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor

# Keep this inventory identical to config/agent_capability_matrix.json.
# The probe must fail closed if any registered agent lacks a live worker.
AGENTS = (
    "ClaudeCode",
    "KimiK3",
    "GrokBot",
    "GoogleAgentSkills",
    "GLM",
    "PlaywrightCLI",
    "JEV",
    "AURELIA",
)


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
            federation, agents=AGENTS, interval_seconds=2
        )
        workers.start()
        try:
            await asyncio.sleep(2.5)
            active = set(federation.active_agents())
            missing = sorted(set(AGENTS) - active)
            unexpected = sorted(active - set(AGENTS))
            print("AGENT_WORKER_ACTIVE=" + ",".join(sorted(active)))
            print("AGENT_WORKER_MISSING=" + ",".join(missing))
            print("AGENT_WORKER_UNEXPECTED=" + ",".join(unexpected))
            return 1 if missing or unexpected else 0
        finally:
            await workers.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
