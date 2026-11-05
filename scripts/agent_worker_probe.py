from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor

# AURELIA is the deterministic capital-plane authority, not an advisory
# provider worker. The worker supervisor intentionally skips it. All other
# registered agents are advisory/engineering workers and require a real
# configured process before they can emit a lease.
ADVISORY_WORKERS = (
    "ClaudeCode",
    "KimiK3",
    "GrokBot",
    "GoogleAgentSkills",
    "GLM",
    "PlaywrightCLI",
    "JEV",
    "DeepSeekHarness",
    "Hermes",
    "Dev",
)
CAPITAL_AUTHORITY = "AURELIA"


def probe_worker_state(
    *,
    active: set[str],
    advisory_workers: tuple[str, ...] = ADVISORY_WORKERS,
) -> tuple[set[str], set[str], set[str]]:
    """Return configured workers, configured-but-missing, and unexpected leases.

    An unconfigured provider is a reported integration blocker, not a CI
    assertion failure. A provider explicitly configured but not running is a
    runtime failure. This keeps CI honest without treating absent credentials
    or absent provider runtimes as if they were connected.
    """
    configured = {
        agent
        for agent in advisory_workers
        if os.getenv(AgentWorkerSupervisor._env_name(agent), "").strip()
    }
    missing = configured - active
    unexpected = active - set(advisory_workers)
    return configured, missing, unexpected


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
            configured, missing, unexpected = probe_worker_state(active=active)
            unconfigured = sorted(set(ADVISORY_WORKERS) - configured)
            capital_heartbeat = CAPITAL_AUTHORITY in active
            print("AGENT_WORKER_ACTIVE=" + ",".join(sorted(active)))
            print("AGENT_WORKER_CONFIGURED=" + ",".join(sorted(configured)))
            print("AGENT_WORKER_MISSING_CONFIGURED=" + ",".join(sorted(missing)))
            print("AGENT_WORKER_UNCONFIGURED=" + ",".join(unconfigured))
            print("AGENT_WORKER_UNEXPECTED=" + ",".join(sorted(unexpected)))
            print("CAPITAL_AUTHORITY_WORKER=INTENTIONALLY_DISABLED")
            print("CAPITAL_AUTHORITY_RUNTIME=DETERMINISTIC_CONTROL_PLANE")
            print("CAPITAL_AUTHORITY_HEARTBEAT=" + ("UNEXPECTED" if capital_heartbeat else "NOT_A_WORKER"))
            # Missing provider runtimes remain visible and keep operational
            # readiness blocked; they are not misreported as connected.
            return 1 if missing or unexpected or capital_heartbeat else 0
        finally:
            await workers.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
