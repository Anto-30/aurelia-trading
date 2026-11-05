from __future__ import annotations

import asyncio
import shlex
import sys
from pathlib import Path

import pytest

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor


def _protocol_worker_command(tmp_path: Path, mode: str = "success") -> str:
    script = tmp_path / "protocol-worker.py"
    script.write_text(
        f"""
import json
import os
import sys
from pathlib import Path

MODE = {mode!r}

for line in sys.stdin:
    message = json.loads(line)
    if message.get("type") == "HELLO":
        ready = {key: message[key] for key in ("protocol", "agent", "worker_id", "session_nonce")}
        ready["type"] = "READY"
        if MODE == "bad_handshake":
            ready["session_nonce"] = "wrong"
        print(json.dumps(ready), flush=True)
    elif message.get("type") == "TASK":
        root = Path(os.environ["AURELIA_EVIDENCE_ROOT"])
        root.mkdir(parents=True, exist_ok=True)
        (root / "worker-evidence.json").write_text("evidence", encoding="utf-8")
        result = {key: message[key] for key in ("protocol", "agent", "worker_id", "session_nonce")}
        result["task_id"] = message["task"]["task_id"]
        result["claim_token"] = message.get("claim_token", "")
        result["correlation_id"] = message["task"]["correlation_id"]
        result["type"] = "TASK_RESULT"
        result["status"] = "COMPLETED"
        result["evidence_ref"] = {
            "traversal": "../outside.json",
            "missing_evidence": "",
            "symlink": "symlink-evidence.json",
        }.get(MODE, "worker-evidence.json")
        result["result"] = {"summary": "fixture completed", "artifact_type": "test/evidence"}
        if MODE == "bad_task":
            result["task_id"] = "task:wrong"
        if MODE == "wrong_claim_token":
            result["claim_token"] = "not-the-claim-capability"
        if MODE == "bad_correlation":
            result["correlation_id"] = "wrong-correlation"
        if MODE == "authority_field":
            result["capital_authority"] = False
        if MODE == "bad_status_type":
            result["status"] = []
        if MODE == "oversized_response":
            print("x" * 70000, flush=True)
        else:
            print(json.dumps(result), flush=True)
""",
        encoding="utf-8",
    )
    return f"{shlex.quote(sys.executable)} -u {shlex.quote(str(script))}"


def _federation(tmp_path: Path) -> PersistentAgentFederation:
    return PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=tmp_path / "tasks.json",
        config_hash="cfg",
        source_hash="src",
        lease_seconds=2,
    )


async def _wait_for_status(
    federation: PersistentAgentFederation, task_id: str, status: str
) -> bool:
    for _ in range(100):
        row = next(x for x in federation._load_tasks() if x["task_id"] == task_id)
        if row["status"] == status:
            return True
        await asyncio.sleep(0.02)
    return False


async def _wait_for_requeue(
    federation: PersistentAgentFederation, task_id: str
) -> bool:
    for _ in range(100):
        for event in federation.journal.read_all():
            if (
                event.get("event_type") == "AGENT_TASK_REQUEUED"
                and event.get("payload", {}).get("task_id") == task_id
            ):
                row = next(x for x in federation._load_tasks() if x["task_id"] == task_id)
                return row["status"] == "PENDING"
        await asyncio.sleep(0.02)
    return False


async def _wait_for_protocol_error(
    federation: PersistentAgentFederation, error_code: str
) -> bool:
    for _ in range(100):
        for event in federation.journal.read_all():
            message = event.get("payload", {})
            if (
                event.get("event_type") == "AGENT_MESSAGE"
                and message.get("message_type") == "WORKER_PROTOCOL_ERROR"
                and message.get("payload", {}).get("error_code") == error_code
            ):
                return True
        await asyncio.sleep(0.02)
    return False


@pytest.mark.asyncio
async def test_unconfigured_worker_does_not_emit_a_phantom_lease_or_claim_work(
    tmp_path, monkeypatch
):
    federation = _federation(tmp_path)
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
async def test_worker_jsonl_protocol_completes_only_correlated_task_with_evidence(
    tmp_path, monkeypatch
):
    evidence_root = tmp_path / "evidence"
    monkeypatch.setenv("AURELIA_EVIDENCE_ROOT", str(evidence_root))
    monkeypatch.setenv(
        "AURELIA_AGENT_CLAUDECODE_COMMAND", _protocol_worker_command(tmp_path)
    )
    federation = _federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING_REVIEW",
        payload={"scope": "test"},
        correlation_id="worker-jsonl-success",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation,
        agents=("ClaudeCode",),
        interval_seconds=0.05,
        handshake_timeout_seconds=1,
        response_timeout_seconds=1,
    )
    supervisor.start()
    try:
        assert await _wait_for_status(federation, task.task_id, "COMPLETED")
        stored = next(x for x in federation._load_tasks() if x["task_id"] == task.task_id)
        assert stored["evidence_ref"] == "worker-evidence.json"
        assert stored["result"]["artifact_type"] == "test/evidence"
        assert "ClaudeCode" in federation.active_agents()
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
async def test_worker_handshake_mismatch_never_creates_worker_lease_or_claims_task(
    tmp_path, monkeypatch
):
    evidence_root = tmp_path / "evidence"
    monkeypatch.setenv("AURELIA_EVIDENCE_ROOT", str(evidence_root))
    monkeypatch.setenv(
        "AURELIA_AGENT_CLAUDECODE_COMMAND", _protocol_worker_command(tmp_path, mode="bad_handshake")
    )
    federation = _federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING_REVIEW",
        payload={},
        correlation_id="worker-jsonl-bad-handshake",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation,
        agents=("ClaudeCode",),
        interval_seconds=0.05,
        handshake_timeout_seconds=0.2,
        response_timeout_seconds=0.2,
    )
    supervisor.start()
    try:
        assert await _wait_for_protocol_error(
            federation, "WORKER_HANDSHAKE_MISMATCH"
        )
        stored = next(x for x in federation._load_tasks() if x["task_id"] == task.task_id)
        assert stored["status"] == "PENDING"
        assert "ClaudeCode" not in federation.active_agents()
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["traversal", "missing_evidence", "symlink"])
async def test_worker_cannot_complete_task_without_evidence_inside_evidence_root(
    tmp_path, monkeypatch, mode
):
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    (tmp_path / "outside.json").write_text("outside", encoding="utf-8")
    if mode == "symlink":
        (evidence_root / "symlink-evidence.json").symlink_to(tmp_path / "outside.json")
    monkeypatch.setenv("AURELIA_EVIDENCE_ROOT", str(evidence_root))
    monkeypatch.setenv(
        "AURELIA_AGENT_CLAUDECODE_COMMAND",
        _protocol_worker_command(tmp_path, mode=mode),
    )
    federation = _federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING_REVIEW",
        payload={},
        correlation_id=f"worker-jsonl-{mode}",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation,
        agents=("ClaudeCode",),
        interval_seconds=0.05,
        handshake_timeout_seconds=1,
        response_timeout_seconds=1,
    )
    supervisor.start()
    try:
        assert await _wait_for_requeue(federation, task.task_id)
        stored = next(x for x in federation._load_tasks() if x["task_id"] == task.task_id)
        assert stored["status"] == "PENDING"
        assert stored.get("evidence_ref") is None
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    [
        "bad_task",
        "bad_correlation",
        "wrong_claim_token",
        "authority_field",
        "oversized_response",
        "bad_status_type",
    ],
)
async def test_worker_cannot_complete_an_unmatched_task(
    tmp_path, monkeypatch, mode
):
    evidence_root = tmp_path / "evidence"
    monkeypatch.setenv("AURELIA_EVIDENCE_ROOT", str(evidence_root))
    monkeypatch.setenv(
        "AURELIA_AGENT_CLAUDECODE_COMMAND",
        _protocol_worker_command(tmp_path, mode=mode),
    )
    federation = _federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING_REVIEW",
        payload={},
        correlation_id=f"worker-jsonl-{mode}",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation,
        agents=("ClaudeCode",),
        interval_seconds=0.05,
        handshake_timeout_seconds=1,
        response_timeout_seconds=1,
    )
    supervisor.start()
    expected_error = {
        "bad_task": "WORKER_TASK_CORRELATION_MISMATCH",
        "bad_correlation": "WORKER_TASK_CORRELATION_MISMATCH",
        "wrong_claim_token": "WORKER_CLAIM_CAPABILITY_MISMATCH",
        "authority_field": "WORKER_AUTHORITY_FIELD_FORBIDDEN",
        "oversized_response": "WORKER_RESPONSE_FRAME_TOO_LARGE",
        "bad_status_type": "WORKER_TASK_STATUS_INVALID",
    }[mode]
    try:
        assert await _wait_for_protocol_error(federation, expected_error)
        assert await _wait_for_requeue(federation, task.task_id)
        stored = next(x for x in federation._load_tasks() if x["task_id"] == task.task_id)
        assert stored["status"] == "PENDING"
        assert stored.get("evidence_ref") is None
    finally:
        await supervisor.stop()


@pytest.mark.asyncio
async def test_complete_task_rejects_missing_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("AURELIA_EVIDENCE_ROOT", str(tmp_path / "evidence"))
    federation = _federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING_REVIEW",
        payload={},
        correlation_id="missing-evidence-direct",
        assigned_agent="ClaudeCode",
    )
    claimed = await federation.claim_task(
        "ClaudeCode",
        worker_id="claude-no-evidence-test-worker",
    )
    assert claimed is not None
    with pytest.raises(
        ValueError, match="COMPLETED_TASK_REQUIRES_VERIFIABLE_EVIDENCE"
    ):
        await federation.complete_task(
            task.task_id,
            agent="ClaudeCode",
            status="COMPLETED",
            worker_id=claimed.worker_id,
            claim_token=claimed.claim_token,
        )


@pytest.mark.asyncio
async def test_worker_input_with_nested_access_token_is_blocked_before_dispatch(
    tmp_path, monkeypatch
):
    evidence_root = tmp_path / "evidence"
    monkeypatch.setenv("AURELIA_EVIDENCE_ROOT", str(evidence_root))
    monkeypatch.setenv(
        "AURELIA_AGENT_CLAUDECODE_COMMAND", _protocol_worker_command(tmp_path)
    )
    federation = _federation(tmp_path)
    task = await federation.enqueue_task(
        task_type="ENGINEERING_REVIEW",
        payload={"request": {"access_token": "must-not-be-dispatched"}},
        correlation_id="worker-sensitive-input",
        assigned_agent="ClaudeCode",
    )
    supervisor = AgentWorkerSupervisor(
        federation,
        agents=("ClaudeCode",),
        interval_seconds=0.05,
        handshake_timeout_seconds=1,
        response_timeout_seconds=1,
    )
    supervisor.start()
    try:
        assert await _wait_for_status(federation, task.task_id, "BLOCKED")
        stored = next(x for x in federation._load_tasks() if x["task_id"] == task.task_id)
        assert stored["result"]["reason"] == "WORKER_INPUT_CONTAINS_SENSITIVE_FIELD"
    finally:
        await supervisor.stop()


def test_worker_environment_is_deny_by_default_and_uses_private_home(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path / "developer-home"))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("CUSTOM_PROVIDER_ACCESS_TOKEN", "must-not-leak")
    monkeypatch.setenv("UNRECOGNIZED_SECRET", "must-not-leak")
    supervisor = AgentWorkerSupervisor(
        _federation(tmp_path), agents=("ClaudeCode",)
    )
    private_home = tmp_path / "private-worker-home"
    private_home.mkdir(mode=0o700)
    env = supervisor._worker_environment(
        supervisor_worker_spec := __import__(
            "runtime.agent_workers", fromlist=["AgentWorkerSpec"]
        ).AgentWorkerSpec(
            agent="ClaudeCode",
            command_env="AURELIA_AGENT_CLAUDECODE_COMMAND",
        ),
        worker_id="worker-test",
        session_nonce="nonce-test",
        home_dir=str(private_home),
    )

    assert env["PATH"] == "/usr/bin:/bin"
    assert env["HOME"] == str(private_home)
    assert env["USERPROFILE"] == str(private_home)
    assert "CUSTOM_PROVIDER_ACCESS_TOKEN" not in env
    assert "UNRECOGNIZED_SECRET" not in env
    assert env["AURELIA_WORKER_AGENT"] == "ClaudeCode"
