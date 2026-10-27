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


async def wait_for_task_status(federation, task_id, status, *, attempts=40):
    for _ in range(attempts):
        rows = federation._load_tasks()
        task = next((row for row in rows if row.get("task_id") == task_id), None)
        if task and task.get("status") == status:
            return task
        await asyncio.sleep(0.05)
    raise AssertionError(f"Task {task_id} did not reach {status}: {federation._load_tasks()}")


@pytest.mark.asyncio
async def test_configured_worker_processes_task_and_records_structured_result(tmp_path):
    code = "import json,sys; t=json.load(sys.stdin); print(json.dumps({'status':'COMPLETED','result':{'task_id':t['task_id'],'answer':'ok'}}))"
    env = dict(os.environ)
    env["AURELIA_AGENT_CLAUDECODE_COMMAND"] = shlex.join([sys.executable, "-c", code])
    env["AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND"] = shlex.join([sys.executable, "-c", "pass"])
    federation = make_federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING",
        payload={"instruction":"return a structured result"},
        correlation_id="worker-result-test",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05, env=env,
        task_timeout_seconds=1.0,
    )
    supervisor.start()
    try:
        row = await wait_for_task_status(federation, task.task_id, "COMPLETED")
        assert row["result"] == {"task_id": task.task_id, "answer": "ok"}
        assert "ClaudeCode" in federation.active_agents()
        assert any(
            item.get("message_type") == "WORKER_ACK"
            and item.get("payload", {}).get("task_id") == task.task_id
            for item in federation.messages_for("AURELIA")
        )
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
async def test_worker_nonzero_exit_marks_task_failed_not_claimed(tmp_path):
    env = dict(os.environ)
    env["AURELIA_AGENT_CLAUDECODE_COMMAND"] = shlex.join([sys.executable, "-c", "import sys; sys.exit(7)"])
    env["AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND"] = shlex.join([sys.executable, "-c", "pass"])
    federation = make_federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING", payload={}, correlation_id="worker-fail-test",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05, env=env,
        task_timeout_seconds=1.0,
    )
    supervisor.start()
    try:
        row = await wait_for_task_status(federation, task.task_id, "FAILED")
        assert row["result"]["error_code"] == "WORKER_COMMAND_EXITED_NONZERO"
        assert row["result"]["return_code"] == 7
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
async def test_worker_timeout_marks_task_failed_and_kills_child(tmp_path):
    env = dict(os.environ)
    env["AURELIA_AGENT_CLAUDECODE_COMMAND"] = shlex.join([sys.executable, "-c", "import time; time.sleep(5)"])
    env["AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND"] = shlex.join([sys.executable, "-c", "pass"])
    federation = make_federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING", payload={}, correlation_id="worker-timeout-test",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05, env=env,
        task_timeout_seconds=0.1,
    )
    supervisor.start()
    try:
        row = await wait_for_task_status(federation, task.task_id, "FAILED")
        assert row["result"]["error_code"] == "WORKER_COMMAND_TIMEOUT"
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
async def test_worker_redacts_configured_secret_values_from_task_results(tmp_path):
    secret = "sentinel-secret-value-9382"
    response_json = json.dumps({"status": "COMPLETED", "result": {"note": secret}})
    code = f"print({response_json!r})"
    env = dict(os.environ)
    env["AURELIA_AGENT_CLAUDECODE_COMMAND"] = shlex.join([sys.executable, "-c", code])
    env["AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND"] = shlex.join([sys.executable, "-c", "pass"])
    env["DEEPSEEK_API_KEY"] = secret
    federation = make_federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING", payload={}, correlation_id="worker-redaction-test",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05, env=env,
        task_timeout_seconds=1.0,
    )
    supervisor.start()
    try:
        row = await wait_for_task_status(federation, task.task_id, "COMPLETED")
        assert secret not in json.dumps(row)
        assert row["result"]["note"] == "[REDACTED]"
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
