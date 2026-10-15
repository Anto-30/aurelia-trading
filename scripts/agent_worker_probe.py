from __future__ import annotations

import asyncio
import os
import shlex
import sys
import tempfile
from pathlib import Path

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor

# This is an isolated, ephemeral simulation of federation lease mechanics.
# It does NOT connect to registered external agents or prove that a persistent
# production agent runtime is deployed. A separate runtime attestation is
# required for those claims.
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
        # Configure harmless disposable child processes explicitly so this simulation
        # tests lease mechanics after unconfigured providers were made fail-closed.
        # The child processes do no provider work and confer no capital authority.
        for agent in ADVISORY_WORKERS:
            env_name = AgentWorkerSupervisor._env_name(agent)
            os.environ[env_name] = shlex.join(
                [sys.executable, "-c", "import time; time.sleep(30)"]
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
            print("AGENT_WORKER_PROBE_MODE=EPHEMERAL_SIMULATION")
            print("AGENT_WORKER_SIMULATION_ACTIVE=" + ",".join(sorted(active)))
            print("AGENT_WORKER_SIMULATION_MISSING=" + ",".join(missing))
            print("AGENT_WORKER_SIMULATION_UNEXPECTED=" + ",".join(unexpected))
            print("PERSISTENT_AGENT_RUNTIME_PROOF=NOT_VERIFIED")
            print("CAPITAL_AUTHORITY_WORKER=INTENTIONALLY_DISABLED")
            print("CAPITAL_AUTHORITY_RUNTIME=DETERMINISTIC_CONTROL_PLANE")
            print("CAPITAL_AUTHORITY_HEARTBEAT=" + ("UNEXPECTED" if capital_heartbeat else "NOT_A_WORKER"))
            return 1 if missing or unexpected or capital_heartbeat else 0
        finally:
            await workers.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
