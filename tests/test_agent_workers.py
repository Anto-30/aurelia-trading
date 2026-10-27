from __future__ import annotations

import asyncio

import pytest

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor


def make_federation(tmp_path):
    return PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=tmp_path / "tasks.json",
        config_hash="cfg",
        source_hash="src",
        lease_seconds=2,
    )


@pytest.mark.asyncio
async def test_missing_worker_command_never_creates_fake_heartbeat(tmp_path, monkeypatch):
    monkeypatch.delenv("AURELIA_AGENT_CLAUDECODE_COMMAND", raising=False)
    monkeypatch.delenv("AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND", raising=False)
    federation = make_federation(tmp_path)
    supervisor = AgentWorkerSupervisor(federation, agents=("ClaudeCode",), interval_seconds=0.05)
    supervisor.start()
    try:
        await asyncio.sleep(0.15)
        assert "ClaudeCode" not in federation.active_agents()
        assert any(
            item.get("message_type") == "CONNECTOR_REQUIRED"
            and item.get("payload", {}).get("reason") == "WORKER_COMMAND_MISSING"
            for item in federation.messages_for("ClaudeCode")
        )
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
async def test_worker_command_without_healthcheck_never_creates_lease(tmp_path, monkeypatch):
    monkeypatch.setenv("AURELIA_AGENT_CLAUDECODE_COMMAND", "python -c 'import time; time.sleep(2)'")
    monkeypatch.delenv("AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND", raising=False)
    federation = make_federation(tmp_path)
    supervisor = AgentWorkerSupervisor(federation, agents=("ClaudeCode",), interval_seconds=0.05)
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
async def test_configured_worker_with_successful_readiness_probe_emits_lease(tmp_path, monkeypatch):
    monkeypatch.setenv("AURELIA_AGENT_CLAUDECODE_COMMAND", "python -c 'import time; time.sleep(2)'")
    monkeypatch.setenv("AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND", "python -c 'pass'")
    federation = make_federation(tmp_path)
    supervisor = AgentWorkerSupervisor(federation, agents=("ClaudeCode",), interval_seconds=0.05)
    supervisor.start()
    try:
        await asyncio.sleep(0.15)
        assert "ClaudeCode" in federation.active_agents()
        status = [
            item for item in federation.messages_for("ClaudeCode")
            if item.get("message_type") == "CONNECTOR_STATUS"
        ]
        assert status
        assert status[0]["payload"]["readiness_probe"] == "PASS"
        assert status[0]["payload"]["provider_session"] == "NOT_INDEPENDENTLY_VERIFIED"
    finally:
        await supervisor.stop()



@pytest.mark.asyncio
async def test_supervisor_uses_injected_environment_without_global_mutation(tmp_path):
    import os
    env = dict(os.environ)
    env["AURELIA_AGENT_CLAUDECODE_COMMAND"] = "python -c 'import time; time.sleep(2)'"
    env["AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND"] = "python -c 'pass'"
    env.pop("AURELIA_AGENT_CLAUDECODE_COMMAND_FROM_GLOBAL", None)
    federation = make_federation(tmp_path)
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05, env=env
    )
    supervisor.start()
    try:
        await asyncio.sleep(0.15)
        assert "ClaudeCode" in federation.active_agents()
        assert os.environ.get("AURELIA_AGENT_CLAUDECODE_COMMAND") is None
    finally:
        await supervisor.stop()

@pytest.mark.asyncio
async def test_failed_readiness_probe_revokes_agent_lease(tmp_path, monkeypatch):
    monkeypatch.setenv("AURELIA_AGENT_CLAUDECODE_COMMAND", "python -c 'import time; time.sleep(2)'")
    monkeypatch.setenv("AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND", "python -c 'raise SystemExit(7)'")
    federation = make_federation(tmp_path)
    supervisor = AgentWorkerSupervisor(federation, agents=("ClaudeCode",), interval_seconds=0.05)
    supervisor.start()
    try:
        await asyncio.sleep(0.2)
        assert "ClaudeCode" not in federation.active_agents()
        assert any(
            item.get("message_type") == "CONNECTOR_UNHEALTHY"
            and item.get("payload", {}).get("reason") == "HEALTHCHECK_FAILED"
            for item in federation.messages_for("ClaudeCode")
        )
    finally:
        await supervisor.stop()
