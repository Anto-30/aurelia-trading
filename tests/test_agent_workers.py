from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys

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
    code = "import json,sys; t=json.load(sys.stdin); print(json.dumps({'schema':'aurelia.agent_task_response.v1','task_id':t['task']['task_id'],'status':'COMPLETED','result':{'task_id':t['task']['task_id'],'answer':'ok'}}))"
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
            for item in federation.messages_for("ClaudeCode")
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
async def test_worker_environment_excludes_broker_tokens_but_passes_own_provider_key(tmp_path):
    broker_token = "broker-token-never-to-be-inherited-4827"
    provider_key = "claude-provider-key-marker-93725"
    code = (
        "import json,sys,os; t=json.load(sys.stdin); "
        "print(json.dumps({'schema':'aurelia.agent_task_response.v1',"
        "'task_id':t['task']['task_id'],'status':'COMPLETED',"
        "'result':{'broker_token_present':'DERIV_AUTH_TOKEN' in os.environ,"
        "'provider_key_present':bool(os.getenv('ANTHROPIC_API_KEY'))}}))"
    )
    env = dict(os.environ)
    env["AURELIA_AGENT_CLAUDECODE_COMMAND"] = shlex.join([sys.executable, "-c", code])
    env["AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND"] = shlex.join([sys.executable, "-c", "pass"])
    env["DERIV_AUTH_TOKEN"] = broker_token
    env["ANTHROPIC_API_KEY"] = provider_key
    federation = make_federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING", payload={}, correlation_id="worker-env-boundary-test",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05, env=env,
        task_timeout_seconds=1.0,
    )
    supervisor.start()
    try:
        row = await wait_for_task_status(federation, task.task_id, "COMPLETED")
        assert row["result"]["broker_token_present"] is False
        assert row["result"]["provider_key_present"] is True
        assert broker_token not in json.dumps(row)
        assert provider_key not in json.dumps(row)
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
    code = (
        "import json,sys,os; t=json.load(sys.stdin); "
        "print(json.dumps({'schema':'aurelia.agent_task_response.v1',"
        "'task_id':t['task']['task_id'],'status':'COMPLETED',"
        "'result':{'note':os.getenv('ANTHROPIC_API_KEY')}}))"
    )
    env = dict(os.environ)
    env["AURELIA_AGENT_CLAUDECODE_COMMAND"] = shlex.join([sys.executable, "-c", code])
    env["AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND"] = shlex.join([sys.executable, "-c", "pass"])
    env["ANTHROPIC_API_KEY"] = secret
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
async def test_failed_readiness_probe_revokes_an_existing_active_lease(tmp_path):
    marker = tmp_path / "provider-ready"
    marker.write_text("ready", encoding="utf-8")
    health_code = (
        "import pathlib,sys; "
        "sys.exit(0 if pathlib.Path(" + repr(str(marker)) + ").exists() else 9)"
    )
    env = dict(os.environ)
    env["AURELIA_AGENT_CLAUDECODE_COMMAND"] = shlex.join([sys.executable, "-c", "pass"])
    env["AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND"] = shlex.join([sys.executable, "-c", health_code])
    federation = make_federation(tmp_path)
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05, env=env,
        healthcheck_timeout_seconds=1.0,
    )
    supervisor.start()
    try:
        for _ in range(40):
            if "ClaudeCode" in federation.active_agents():
                break
            await asyncio.sleep(0.025)
        assert "ClaudeCode" in federation.active_agents()
        marker.unlink()
        for _ in range(40):
            if "ClaudeCode" not in federation.active_agents() and any(
                row.get("message_type") == "CONNECTOR_UNHEALTHY"
                for row in federation.messages_for("ClaudeCode")
            ):
                break
            await asyncio.sleep(0.05)
        assert "ClaudeCode" not in federation.active_agents()
        assert any(
            row.get("message_type") == "AGENT_LEASE_REVOKED"
            and row.get("payload", {}).get("reason") == "HEALTHCHECK_FAILED"
            for row in federation.journal.read_all()
        )
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
async def test_stopping_supervisor_kills_inflight_task_adapter(tmp_path):
    marker = tmp_path / "adapter-finished"
    code = (
        "import json,sys,time,pathlib; t=json.load(sys.stdin); time.sleep(0.8); "
        "pathlib.Path(" + repr(str(marker)) + ").write_text('done'); "
        "print(json.dumps({'schema':'aurelia.agent_task_response.v1',"
        "'task_id':t['task']['task_id'],'status':'COMPLETED','result':{}}))"
    )
    env = dict(os.environ)
    env["AURELIA_AGENT_CLAUDECODE_COMMAND"] = shlex.join([sys.executable, "-c", code])
    env["AURELIA_AGENT_CLAUDECODE_HEALTHCHECK_COMMAND"] = shlex.join([sys.executable, "-c", "pass"])
    federation = make_federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING", payload={}, correlation_id="cancel-inflight-adapter",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.025, env=env,
        task_timeout_seconds=3.0,
    )
    supervisor.start()
    try:
        claimed = False
        for _ in range(40):
            rows = federation._load_tasks()
            task_row = next(row for row in rows if row["task_id"] == task.task_id)
            if task_row["status"] == "CLAIMED":
                claimed = True
                break
            await asyncio.sleep(0.025)
        assert claimed
        await asyncio.sleep(0.05)
    finally:
        await supervisor.stop()
    await asyncio.sleep(0.9)
    assert not marker.exists(), "Cancelled adapter process continued running after supervisor stop"
    assert next(row for row in federation._load_tasks() if row["task_id"] == task.task_id)["status"] == "CLAIMED"

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
