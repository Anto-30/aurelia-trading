from __future__ import annotations

import hashlib
import json

import pytest

from runtime.agents.task_protocol import (
    ProtocolError,
    decode_message,
    persist_evidence,
    validate_hello,
    validate_task_result,
)


def test_decode_message_requires_a_json_object():
    with pytest.raises(ProtocolError, match="MESSAGE_NOT_OBJECT"):
        decode_message(b'["not", "an", "object"]\n')


def test_decode_message_rejects_oversized_input():
    with pytest.raises(ProtocolError, match="MESSAGE_TOO_LARGE"):
        decode_message(b'{"x":"' + b"a" * 128 + b'"}\n', max_bytes=64)


def test_validate_hello_requires_protocol_and_exact_agent_identity():
    good = {"type": "HELLO", "protocol_version": 1, "agent": "ClaudeCode"}
    validate_hello(good, expected_agent="ClaudeCode")

    with pytest.raises(ProtocolError, match="WORKER_IDENTITY_MISMATCH"):
        validate_hello(good, expected_agent="DeepSeekHarness")


def test_task_result_requires_exact_task_and_claim_token():
    result = {
        "type": "TASK_RESULT",
        "protocol_version": 1,
        "agent": "ClaudeCode",
        "task_id": "task:123",
        "claim_token": "one-time-secret",
        "status": "COMPLETED",
        "result": {"summary": "review complete"},
        "evidence": {"kind": "review", "findings": []},
    }
    accepted = validate_task_result(
        result,
        expected_agent="ClaudeCode",
        expected_task_id="task:123",
        expected_claim_token="one-time-secret",
    )
    assert accepted.status == "COMPLETED"
    assert accepted.result == {"summary": "review complete"}

    with pytest.raises(ProtocolError, match="TASK_ID_MISMATCH"):
        validate_task_result(
            result,
            expected_agent="ClaudeCode",
            expected_task_id="task:other",
            expected_claim_token="one-time-secret",
        )

    with pytest.raises(ProtocolError, match="CLAIM_TOKEN_MISMATCH"):
        validate_task_result(
            result,
            expected_agent="ClaudeCode",
            expected_task_id="task:123",
            expected_claim_token="wrong-token",
        )


def test_task_result_rejects_claims_of_capital_authority():
    result = {
        "type": "TASK_RESULT",
        "protocol_version": 1,
        "agent": "ClaudeCode",
        "task_id": "task:123",
        "claim_token": "one-time-secret",
        "status": "COMPLETED",
        "result": {"capital_authority": True},
        "evidence": {"kind": "review", "findings": []},
    }
    with pytest.raises(ProtocolError, match="CAPITAL_AUTHORITY_CLAIM_FORBIDDEN"):
        validate_task_result(
            result,
            expected_agent="ClaudeCode",
            expected_task_id="task:123",
            expected_claim_token="one-time-secret",
        )


def test_completed_task_requires_nonempty_evidence():
    result = {
        "type": "TASK_RESULT",
        "protocol_version": 1,
        "agent": "ClaudeCode",
        "task_id": "task:123",
        "claim_token": "one-time-secret",
        "status": "COMPLETED",
        "result": {"summary": "done"},
        "evidence": {},
    }
    with pytest.raises(ProtocolError, match="TASK_EVIDENCE_REQUIRED"):
        validate_task_result(
            result,
            expected_agent="ClaudeCode",
            expected_task_id="task:123",
            expected_claim_token="one-time-secret",
        )


def test_persisted_evidence_is_content_addressed_and_verifiable(tmp_path):
    record = {"schema": "aurelia.agent_task_evidence.v1", "task_id": "task:123"}
    artifact = persist_evidence(tmp_path, record)
    raw = (tmp_path / artifact.relative_ref).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == artifact.sha256
    assert json.loads(raw) == record
    assert artifact.relative_ref.startswith("agent-tasks/")


@pytest.mark.asyncio
async def test_federation_claim_requires_bound_worker_capability(tmp_path):
    from runtime.agent_federation import PersistentAgentFederation

    federation = PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=tmp_path / "tasks.json",
        config_hash="cfg",
        source_hash="src",
        lease_seconds=5,
    )
    enqueued = await federation.enqueue_task(
        task_type="ENGINEERING_REVIEW",
        payload={"scope": "safe"},
        correlation_id="claim-capability",
        assigned_agent="ClaudeCode",
    )
    claim = await federation.claim_task("ClaudeCode", worker_id="worker-1")
    assert claim is not None
    assert claim.task_id == enqueued.task_id
    assert claim.claim_token

    assert not await federation.complete_task(
        claim.task_id,
        agent="ClaudeCode",
        worker_id="worker-1",
        claim_token="incorrect-capability",
        status="COMPLETED",
    )
    assert await federation.renew_task_claim(
        claim.task_id,
        agent="ClaudeCode",
        worker_id="worker-1",
        claim_token=claim.claim_token,
    )
    assert await federation.complete_task(
        claim.task_id,
        agent="ClaudeCode",
        worker_id="worker-1",
        claim_token=claim.claim_token,
        status="COMPLETED",
        evidence_ref="agent-tasks/test.json",
        result={"verified": False},
    )


@pytest.mark.asyncio
async def test_supervisor_executes_and_records_attributable_jsonl_result(tmp_path, monkeypatch):
    import shlex
    import sys
    import time

    from runtime.agent_federation import PersistentAgentFederation
    from runtime.agent_workers import AgentWorkerSupervisor

    worker_script = r'''
import json
import sys

print(json.dumps({
    "type": "HELLO",
    "protocol_version": 1,
    "agent": "ClaudeCode"
}), flush=True)

for raw in sys.stdin:
    message = json.loads(raw)
    if message.get("type") != "TASK":
        continue
    response = {
        "type": "TASK_RESULT",
        "protocol_version": 1,
        "agent": "ClaudeCode",
        "task_id": message["task_id"],
        "claim_token": message["claim_token"],
        "status": "COMPLETED",
        "result": {"summary": "worker completed task", "verified": True},
        "evidence": {"kind": "test-report", "checks": ["one", "two"]}
    }
    print(json.dumps(response, separators=(",", ":")), flush=True)
'''
    command = f"{shlex.quote(sys.executable)} -u -c {shlex.quote(worker_script)}"
    monkeypatch.setenv("AURELIA_AGENT_CLAUDECODE_COMMAND", command)

    federation = PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=tmp_path / "tasks.json",
        config_hash="cfg",
        source_hash="src",
        lease_seconds=5,
    )
    await federation.enqueue_task(
        task_type="ENGINEERING_REVIEW",
        payload={"scope": "protocol integration test"},
        correlation_id="worker-protocol-integration",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation,
        agents=("ClaudeCode",),
        interval_seconds=0.05,
        startup_timeout_seconds=2,
        task_timeout_seconds=2,
        evidence_root=tmp_path,
    )
    supervisor.start()
    deadline = time.monotonic() + 4
    stored = []
    try:
        while time.monotonic() < deadline:
            stored = federation._load_tasks()
            if stored and stored[0].get("status") in {"COMPLETED", "FAILED", "BLOCKED"}:
                break
            await asyncio.sleep(0.05)
    finally:
        await supervisor.stop()

    assert stored[0]["status"] == "COMPLETED"
    assert stored[0]["completed_by_worker_id"].startswith("agent-worker:ClaudeCode:")
    evidence_path = tmp_path / stored[0]["evidence_ref"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["attribution"]["claim_capability_validated"] is True
    assert evidence["attribution"]["provider_authentication"] is False
    assert evidence["worker_result"]["verified"] is True
    assert stored[0]["result"]["verified"] is False
