from __future__ import annotations

import asyncio

import pytest

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor


@pytest.mark.asyncio
async def test_worker_without_command_is_connector_required_not_active(tmp_path, monkeypatch):
    monkeypatch.delenv("AURELIA_AGENT_CLAUDECODE_COMMAND", raising=False)
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
    assert "ClaudeCode" not in federation.active_agents()
    messages = federation.messages_for("ClaudeCode")
    assert any(
        message.get("message_type") == "CONNECTOR_STATUS"
        and message.get("payload", {}).get("provider_session") == "NOT_CONFIGURED"
        and message.get("payload", {}).get("provider_authentication") == "NOT_VERIFIED"
        for message in messages
    )
    assert any(
        message.get("message_type") == "CONNECTOR_REQUIRED"
        and message.get("payload", {}).get("reason") == "NO_AUTHENTICATED_PROVIDER_COMMAND"
        for message in messages
    )
    await supervisor.stop()


@pytest.mark.asyncio
async def test_configured_process_emits_liveness_lease_not_provider_authentication(tmp_path, monkeypatch):
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
        "python -c 'import time; time.sleep(2)'",
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05
    )
    supervisor.start()
    await asyncio.sleep(0.15)
    assert "ClaudeCode" in federation.active_agents()
    messages = federation.messages_for("ClaudeCode")
    assert any(
        message.get("message_type") == "CONNECTOR_STATUS"
        and message.get("payload", {}).get("provider_session") == "CONFIGURED_COMMAND"
        and message.get("payload", {}).get("provider_authentication") == "NOT_VERIFIED"
        for message in messages
    )
    assert not any(
        message.get("message_type") == "PROVIDER_AUTHENTICATED"
        for message in messages
    )
    await supervisor.stop()
