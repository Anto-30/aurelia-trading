from __future__ import annotations

import asyncio
import shlex

import pytest

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor


@pytest.mark.asyncio
async def test_unconfigured_provider_is_reported_without_creating_agent_lease(tmp_path, monkeypatch):
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
    try:
        assert "ClaudeCode" not in federation.active_agents()
        messages = federation.messages_for("ClaudeCode")
        status = next(x for x in messages if x["message_type"] == "CONNECTOR_STATUS")
        required = next(x for x in messages if x["message_type"] == "CONNECTOR_REQUIRED")
        assert status["payload"]["provider_session"] == "NOT_CONFIGURED"
        assert status["payload"]["provider_authentication"] == "NOT_VERIFIED"
        assert status["payload"]["provider_process"] == "NOT_STARTED"
        assert required["payload"]["reason"] == "NO_AUTHENTICATED_PROVIDER_COMMAND"
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
async def test_configured_command_is_not_executed_or_leased_without_verified_protocol(tmp_path, monkeypatch):
    sentinel = tmp_path / "untrusted-command-executed.txt"
    command = shlex.join([
        "python",
        "-c",
        f"from pathlib import Path; Path({str(sentinel)!r}).write_text('executed')",
    ])
    monkeypatch.setenv("AURELIA_AGENT_CLAUDECODE_COMMAND", command)
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
    try:
        assert "ClaudeCode" not in federation.active_agents()
        assert not sentinel.exists(), "unverified commands must never be executed"
        messages = federation.messages_for("ClaudeCode")
        status = next(x for x in messages if x["message_type"] == "CONNECTOR_STATUS")
        required = next(x for x in messages if x["message_type"] == "CONNECTOR_REQUIRED")
        assert status["payload"]["provider_session"] == "COMMAND_CONFIGURED_PROTOCOL_UNVERIFIED"
        assert status["payload"]["provider_authentication"] == "NOT_VERIFIED"
        assert status["payload"]["provider_process"] == "NOT_STARTED"
        assert required["payload"]["reason"] == "PROVIDER_WORKER_PROTOCOL_NOT_IMPLEMENTED"
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
async def test_worker_probe_reports_unavailable_providers_without_fake_leases(monkeypatch, capsys):
    from scripts.agent_worker_probe import ADVISORY_WORKERS, main
    from runtime.agent_workers import AgentWorkerSupervisor

    for agent in ADVISORY_WORKERS:
        monkeypatch.delenv(AgentWorkerSupervisor._env_name(agent), raising=False)

    result = await main()
    output = capsys.readouterr().out

    assert result == 0
    assert "AGENT_PROVIDER_CONNECTOR_STATUS_REPORTED=" in output
    assert "AGENT_PROVIDER_CONNECTOR_STATUS_MISSING=" in output
    assert "AGENT_LOCAL_WORKER_LEASES_ACTIVE=" in output
    assert "AGENT_PROVIDER_PROCESS=NOT_STARTED" in output
    assert "AGENT_PROVIDER_AUTHENTICATION=NOT_VERIFIED" in output
    assert "AGENT_PROVIDER_READINESS=BLOCKED_PROTOCOL_AND_AUTH_HANDSHAKE_MISSING" in output
