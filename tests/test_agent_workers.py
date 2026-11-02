from __future__ import annotations

import asyncio
import os

import pytest

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor


@pytest.mark.asyncio
async def test_worker_heartbeat_requires_real_configured_command(tmp_path):
    federation = PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=tmp_path / "tasks.json",
        config_hash="cfg",
        source_hash="src",
        lease_seconds=2,
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05
    )
    supervisor.start()
    await asyncio.sleep(0.15)
    assert "ClaudeCode" in federation.active_agents()
    await supervisor.stop()


@pytest.mark.asyncio
async def test_configured_worker_emits_live_worker_lease(tmp_path, monkeypatch):
    federation = PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=tmp_path / "tasks.json",
        config_hash="cfg",
        source_hash="src",
        lease_seconds=2,
    )
    monkeypatch.setenv("AURELIA_AGENT_CLAUDECODE_COMMAND", "python -c 'import time; time.sleep(2)'")
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05
    )
    supervisor.start()
    await asyncio.sleep(0.15)
    assert "ClaudeCode" in federation.active_agents()
    await supervisor.stop()

@pytest.mark.asyncio
async def test_worker_probe_distinguishes_local_leases_from_provider_authentication(monkeypatch, capsys):
    from scripts.agent_worker_probe import ADVISORY_WORKERS, main
    from runtime.agent_workers import AgentWorkerSupervisor

    for agent in ADVISORY_WORKERS:
        monkeypatch.delenv(AgentWorkerSupervisor._env_name(agent), raising=False)

    result = await main()
    output = capsys.readouterr().out

    assert result == 0
    assert "AGENT_LOCAL_WORKER_LEASES_ACTIVE=" in output
    assert "AGENT_PROVIDER_COMMAND_MISSING=" in output
    assert "AGENT_CONNECTOR_REQUIRED=" in output
    assert "AGENT_PROVIDER_AUTHENTICATION=NOT_VERIFIED" in output
