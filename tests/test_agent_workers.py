from __future__ import annotations

import asyncio

import pytest

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor


@pytest.mark.asyncio
async def test_unconfigured_provider_emits_connector_required_without_lease(tmp_path):
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
    await asyncio.sleep(0.05)

    assert "ClaudeCode" not in federation.active_agents()
    messages = federation.messages_for("ClaudeCode")
    status = next(m for m in messages if m["message_type"] == "CONNECTOR_STATUS")
    required = next(m for m in messages if m["message_type"] == "CONNECTOR_REQUIRED")
    assert status["payload"]["provider_session"] == "NOT_CONFIGURED"
    assert status["payload"]["provider_authenticated"] is False
    assert status["payload"]["process_started"] is False
    assert status["payload"]["worker_lease_emitted"] is False
    assert required["payload"]["reason"] == "NO_AUTHENTICATED_PROVIDER_COMMAND"
    await supervisor.stop()


@pytest.mark.asyncio
async def test_configured_command_is_not_started_without_protocol_and_sandbox(
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
    monkeypatch.setenv(
        "AURELIA_AGENT_CLAUDECODE_COMMAND",
        "python -c 'raise SystemExit(99)'",
    )

    async def forbidden_process_start(*args, **kwargs):
        raise AssertionError("provider process must not start before protocol and sandbox")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden_process_start)
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05
    )
    supervisor.start()
    await asyncio.sleep(0.05)

    assert "ClaudeCode" not in federation.active_agents()
    messages = federation.messages_for("ClaudeCode")
    required = next(m for m in messages if m["message_type"] == "CONNECTOR_REQUIRED")
    assert required["payload"]["reason"] == "JSONL_PROTOCOL_AND_OS_SANDBOX_NOT_INTEGRATED"
    assert required["payload"]["process_started"] is False
    assert required["payload"]["worker_lease_emitted"] is False
    await supervisor.stop()


@pytest.mark.asyncio
async def test_capital_authority_is_never_started_as_a_provider_worker(tmp_path):
    federation = PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=tmp_path / "tasks.json",
        config_hash="cfg",
        source_hash="src",
        lease_seconds=2,
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("AURELIA", "ClaudeCode"), interval_seconds=0.05
    )
    supervisor.start()
    await asyncio.sleep(0.05)

    assert "AURELIA" not in federation.active_agents()
    assert "AURELIA" not in supervisor._tasks
    assert "ClaudeCode" not in federation.active_agents()
    await supervisor.stop()
