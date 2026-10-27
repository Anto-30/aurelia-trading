from __future__ import annotations

import asyncio
import os

import pytest

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor


@pytest.mark.asyncio
async def test_missing_worker_command_never_creates_fake_heartbeat(tmp_path, monkeypatch):
    monkeypatch.delenv("AURELIA_AGENT_CLAUDECODE_COMMAND", raising=False)
    monkeypatch.delenv("AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND", raising=False)
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
    try:
        await asyncio.sleep(0.15)
        assert "ClaudeCode" not in federation.active_agents()
        messages = federation.messages_for("ClaudeCode")
        assert any(
            item.get("message_type") == "CONNECTOR_REQUIRED"
            and item.get("payload", {}).get("reason") == "WORKER_COMMAND_MISSING"
            for item in messages
        )
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
async def test_worker_command_without_healthcheck_never_creates_lease(tmp_path, monkeypatch):
    monkeypatch.setenv("AURELIA_AGENT_CLAUDECODE_COMMAND", "python -c 'import time; time.sleep(2)'")
    monkeypatch.setenv("AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND", "python -c 'pass'")
    monkeypatch.delenv("AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND", raising=False)
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
    try:
        await asyncio.sleep(0.15)
        assert "ClaudeCode" not in federation.active_agents()
        assert any(
            item.get("message_type") == "CONNECTOR_REQUIRED"
            and item.get("payload", {}).get("reason") == "WORKER_HEALTHCHECK_COMMAND_MISSING"
            for item in federation.messages_for("ClaudeCode")
        )
    finally:
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
