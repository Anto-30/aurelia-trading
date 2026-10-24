from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys

import pytest

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor


@pytest.mark.asyncio
async def test_unconfigured_provider_does_not_emit_agent_liveness(tmp_path):
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
        assert any(x["message_type"] == "CONNECTOR_REQUIRED" for x in messages)
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


@pytest.mark.asyncio
async def test_provider_jsonl_protocol_records_attributable_task_result(tmp_path, monkeypatch):
    task_path = tmp_path / "tasks.json"
    federation = PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=task_path,
        config_hash="cfg",
        source_hash="src",
        lease_seconds=2,
    )
    task = await federation.enqueue_task(
        task_type="TEST_TASK",
        payload={"instruction": "return a test result"},
        correlation_id="test-correlation",
        assigned_agent="ClaudeCode",
    )
    provider_code = (
        "import json,sys\n"
        "for line in sys.stdin:\n"
        " request=json.loads(line)\n"
        " print(json.dumps({'schema':'aurelia.agent_task_result.v1','task_id':request['task_id'],'status':'COMPLETED','evidence_ref':'test://provider-result','result':{'verified':True}}),flush=True)\n"
    )
    monkeypatch.setenv(
        "AURELIA_AGENT_CLAUDECODE_COMMAND",
        shlex.join([sys.executable, "-u", "-c", provider_code]),
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05, task_timeout_seconds=1
    )
    supervisor.start()
    try:
        for _ in range(40):
            await asyncio.sleep(0.05)
            saved = json.loads(task_path.read_text(encoding="utf-8"))
            record = next(x for x in saved["tasks"] if x["task_id"] == task.task_id)
            if record["status"] != "PENDING" and record["status"] != "CLAIMED":
                break
        assert record["status"] == "COMPLETED"
        assert record["evidence_ref"] == "test://provider-result"
        assert record["result"] == {"verified": True}
    finally:
        await supervisor.stop()


@pytest.mark.parametrize(
    ("provider_result", "expected_reason"),
    [
        (
            {
                "schema": "aurelia.agent_task_result.v1",
                "status": "COMPLETED",
                "result": {"verified": True},
            },
            "PROVIDER_EVIDENCE_REF_REQUIRED",
        ),
        (
            {
                "schema": "aurelia.agent_task_result.v1",
                "task_id": "placeholder",
                "status": "COMPLETED",
                "evidence_ref": "   ",
                "result": {},
            },
            "PROVIDER_EVIDENCE_REF_REQUIRED",
        ),
        (
            {
                "schema": "aurelia.agent_task_result.v1",
                "status": ["COMPLETED"],
                "evidence_ref": "test://provider-result",
                "result": {},
            },
            "PROVIDER_RESULT_STATUS_INVALID",
        ),
    ],
)
@pytest.mark.asyncio
async def test_provider_completion_requires_nonempty_evidence_and_string_status(
    tmp_path, monkeypatch, provider_result, expected_reason
):
    task_path = tmp_path / "tasks.json"
    federation = PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=task_path,
        config_hash="cfg",
        source_hash="src",
        lease_seconds=2,
    )
    task = await federation.enqueue_task(
        task_type="TEST_TASK",
        payload={"instruction": "return a malformed test result"},
        correlation_id="test-malformed-result",
        assigned_agent="ClaudeCode",
    )
    encoded_template = repr(json.dumps(provider_result))
    provider_code = (
        "import json,sys\n"
        f"template=json.loads({encoded_template})\n"
        "for line in sys.stdin:\n"
        " request=json.loads(line)\n"
        " result=dict(template)\n"
        " result['task_id']=request['task_id']\n"
        " print(json.dumps(result),flush=True)\n"
    )
    monkeypatch.setenv(
        "AURELIA_AGENT_CLAUDECODE_COMMAND",
        shlex.join([sys.executable, "-u", "-c", provider_code]),
    )
    supervisor = AgentWorkerSupervisor(
        federation, agents=("ClaudeCode",), interval_seconds=0.05, task_timeout_seconds=1
    )
    supervisor.start()
    try:
        record = None
        for _ in range(60):
            await asyncio.sleep(0.05)
            saved = json.loads(task_path.read_text(encoding="utf-8"))
            record = next(x for x in saved["tasks"] if x["task_id"] == task.task_id)
            if record["status"] not in {"PENDING", "CLAIMED"}:
                break
        assert record is not None
        assert record["status"] == "FAILED"
        assert record["result"]["reason"] == expected_reason
        assert not record.get("evidence_ref")
    finally:
        await supervisor.stop()
