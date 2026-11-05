from __future__ import annotations

"""Versioned JSONL protocol for attributable, advisory AURELIA workers.

The protocol binds a response to a supervisor-launched process, agent identity,
task ID, and one-time claim capability. It does not authenticate a model
provider, sandbox the process, prove that worker assertions are true, or grant
capital/order authority.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 64 * 1024
ALLOWED_TASK_STATUSES = frozenset({"COMPLETED", "FAILED", "BLOCKED"})
SENSITIVE_KEYS = frozenset({
    "token",
    "api_token",
    "access_token",
    "refresh_token",
    "auth_token",
    "password",
    "secret",
    "client_secret",
    "api_key",
    "authorization",
    "otp",
    "loginid",
    "account_loginid",
})
AUTHORITY_KEYS = frozenset({
    "capital_authority",
    "final_execution_authorization",
    "live_trading_enabled",
    "order_submission_permitted",
})


class ProtocolError(ValueError):
    """A malformed, unauthorized, or non-attributable worker message."""


@dataclass(frozen=True)
class AgentTaskResult:
    agent: str
    task_id: str
    status: str
    result: dict[str, Any]
    evidence: dict[str, Any]


@dataclass(frozen=True)
class EvidenceArtifact:
    relative_ref: str
    sha256: str
    size_bytes: int


def _json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProtocolError("MESSAGE_NOT_CANONICAL_JSON") from exc


def encode_message(message: dict[str, Any], *, max_bytes: int = MAX_MESSAGE_BYTES) -> bytes:
    if not isinstance(message, dict):
        raise ProtocolError("MESSAGE_NOT_OBJECT")
    raw = _json_bytes(message)
    if len(raw) + 1 > max_bytes:
        raise ProtocolError("MESSAGE_TOO_LARGE")
    return raw + b"\n"


def decode_message(line: bytes | str, *, max_bytes: int = MAX_MESSAGE_BYTES) -> dict[str, Any]:
    if isinstance(line, str):
        raw = line.encode("utf-8")
    elif isinstance(line, bytes):
        raw = line
    else:
        raise ProtocolError("MESSAGE_INVALID_TYPE")
    if len(raw) > max_bytes:
        raise ProtocolError("MESSAGE_TOO_LARGE")
    if not raw.strip():
        raise ProtocolError("MESSAGE_EMPTY")
    try:
        message = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("MESSAGE_INVALID_JSON") from exc
    if not isinstance(message, dict):
        raise ProtocolError("MESSAGE_NOT_OBJECT")
    if "protocol_version" in message and message["protocol_version"] != PROTOCOL_VERSION:
        raise ProtocolError("PROTOCOL_VERSION_UNSUPPORTED")
    return message


def _reject_sensitive_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS:
                raise ProtocolError("SECRET_FIELD_FORBIDDEN")
            _reject_sensitive_keys(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_sensitive_keys(nested)


def _reject_authority_claims(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in AUTHORITY_KEYS and (
                nested is True or str(nested).strip().lower() in {"true", "enabled", "allow"}
            ):
                raise ProtocolError("CAPITAL_AUTHORITY_CLAIM_FORBIDDEN")
            _reject_authority_claims(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_authority_claims(nested)


def validate_hello(message: dict[str, Any], *, expected_agent: str) -> dict[str, Any]:
    if not isinstance(message, dict) or message.get("type") != "HELLO":
        raise ProtocolError("WORKER_HELLO_REQUIRED")
    if message.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError("PROTOCOL_VERSION_UNSUPPORTED")
    if message.get("agent") != expected_agent:
        raise ProtocolError("WORKER_IDENTITY_MISMATCH")
    _reject_authority_claims(message)
    return message


def validate_task_result(
    message: dict[str, Any],
    *,
    expected_agent: str,
    expected_task_id: str,
    expected_claim_token: str,
) -> AgentTaskResult:
    if not isinstance(message, dict) or message.get("type") != "TASK_RESULT":
        raise ProtocolError("TASK_RESULT_REQUIRED")
    if message.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError("PROTOCOL_VERSION_UNSUPPORTED")
    if message.get("agent") != expected_agent:
        raise ProtocolError("WORKER_IDENTITY_MISMATCH")
    if message.get("task_id") != expected_task_id:
        raise ProtocolError("TASK_ID_MISMATCH")
    supplied_token = message.get("claim_token")
    if not isinstance(supplied_token, str) or not expected_claim_token or not (
        __import__("hmac").compare_digest(supplied_token, expected_claim_token)
    ):
        raise ProtocolError("CLAIM_TOKEN_MISMATCH")
    status = message.get("status")
    if status not in ALLOWED_TASK_STATUSES:
        raise ProtocolError("TASK_STATUS_INVALID")
    result = message.get("result")
    evidence = message.get("evidence")
    if not isinstance(result, dict) or not isinstance(evidence, dict):
        raise ProtocolError("TASK_RESULT_AND_EVIDENCE_OBJECTS_REQUIRED")
    if status == "COMPLETED" and not evidence:
        raise ProtocolError("TASK_EVIDENCE_REQUIRED")
    _reject_sensitive_keys(result)
    _reject_sensitive_keys(evidence)
    _reject_authority_claims(result)
    _reject_authority_claims(evidence)
    if len(_json_bytes({"result": result, "evidence": evidence})) > MAX_MESSAGE_BYTES:
        raise ProtocolError("TASK_RESULT_TOO_LARGE")
    return AgentTaskResult(
        agent=expected_agent,
        task_id=expected_task_id,
        status=status,
        result=result,
        evidence=evidence,
    )


def assert_safe_task_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ProtocolError("TASK_PAYLOAD_NOT_OBJECT")
    _reject_sensitive_keys(payload)
    _reject_authority_claims(payload)
    if len(_json_bytes(payload)) > MAX_MESSAGE_BYTES // 2:
        raise ProtocolError("TASK_PAYLOAD_TOO_LARGE")


def build_task_message(task: Any, *, worker_id: str) -> dict[str, Any]:
    if not getattr(task, "claim_token", None):
        raise ProtocolError("TASK_CLAIM_CAPABILITY_MISSING")
    if not worker_id.strip():
        raise ProtocolError("WORKER_ID_REQUIRED")
    assert_safe_task_payload(task.payload)
    return {
        "type": "TASK",
        "protocol_version": PROTOCOL_VERSION,
        "agent": task.assigned_agent,
        "worker_id": worker_id,
        "task_id": task.task_id,
        "task_type": task.task_type,
        "priority": task.priority,
        "correlation_id": task.correlation_id,
        "created_at": task.created_at.isoformat(),
        "payload": task.payload,
        "claim_token": task.claim_token,
        "capital_authority": False,
        "order_submission_permitted": False,
    }


def persist_evidence(root: str | Path, record: dict[str, Any]) -> EvidenceArtifact:
    if not isinstance(record, dict):
        raise ProtocolError("EVIDENCE_RECORD_NOT_OBJECT")
    _reject_sensitive_keys(record)
    _reject_authority_claims(record)
    raw = _json_bytes(record)
    digest = hashlib.sha256(raw).hexdigest()
    root_path = Path(root).resolve()
    artifact_dir = root_path / "agent-tasks"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{digest}.json"
    resolved_dir = artifact_dir.resolve()
    try:
        resolved_dir.relative_to(root_path)
    except ValueError as exc:
        raise ProtocolError("EVIDENCE_PATH_ESCAPES_ROOT") from exc
    if artifact_path.exists():
        if artifact_path.read_bytes() != raw:
            raise ProtocolError("EVIDENCE_CONTENT_ADDRESS_CONFLICT")
    else:
        temp_path = artifact_path.with_name(f".{digest}.{os.getpid()}.tmp")
        temp_path.write_bytes(raw)
        os.replace(temp_path, artifact_path)
    return EvidenceArtifact(
        relative_ref=f"agent-tasks/{digest}.json",
        sha256=digest,
        size_bytes=len(raw),
    )
