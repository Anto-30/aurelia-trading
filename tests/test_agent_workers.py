from __future__ import annotations

import asyncio
import pytest

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor


@pytest.mark.asyncio
async def test_unconfigured_worker_does_not_emit_a_phantom_lease_or_claim_work(
    tmp_path, monkeypatch
):
    federation = PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=tmp_path / "tasks.json",
        config_hash="cfg",
        source_hash="src",
        lease_seconds=2,
    )
    monkeypatch.delenv("AURELIA_AGENT_CLAUDECODE_COMMAND", raising=False)
    task = await federation.enqueue_task(
        task_type="ENGINEERING_REVIEW",
        payload={"target": "AURELIA"},
        correlation_id="unconfigured-agent-test",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05
    )
    supervisor.start()
    await asyncio.sleep(0.15)
    assert "ClaudeCode" not in federation.active_agents()
    stored = next(x for x in federation._load_tasks() if x["task_id"] == task.task_id)
    assert stored["status"] == "PENDING"
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


def test_agent_worker_probe_only_requires_configured_workers(monkeypatch):
    from scripts.agent_worker_probe import probe_worker_state

    monkeypatch.delenv("AURELIA_AGENT_CLAUDECODE_COMMAND", raising=False)
    configured, missing, unexpected = probe_worker_state(
        active=set(), advisory_workers=("ClaudeCode",)
    )
    assert configured == set()
    assert missing == set()
    assert unexpected == set()

    monkeypatch.setenv("AURELIA_AGENT_CLAUDECODE_COMMAND", "claude")
    configured, missing, unexpected = probe_worker_state(
        active=set(), advisory_workers=("ClaudeCode",)
    )
    assert configured == {"ClaudeCode"}
    assert missing == {"ClaudeCode"}
    assert unexpected == set()
