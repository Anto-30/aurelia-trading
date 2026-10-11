from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA = "aurelia.operator_kill_switch_reset.v1"
MAX_RESET_TTL_SECONDS = 300


def _canonical(record: dict[str, Any]) -> bytes:
    return json.dumps(
        {key: value for key, value in record.items() if key != "signature"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _signature(record: dict[str, Any], signing_key: str) -> str:
    if not isinstance(signing_key, str) or len(signing_key) < 32:
        raise ValueError("OPERATOR_RESET_SIGNING_KEY_TOO_SHORT")
    return hmac.new(
        signing_key.encode("utf-8"),
        hashlib.sha256(_canonical(record)).digest(),
        hashlib.sha256,
    ).hexdigest()


def create_operator_reset_record(
    *,
    signing_key: str,
    operator_id: str,
    reason: str,
    source_sha: str,
    fault_source_sha: str | None = None,
    account_loginid: str,
    kill_switch_generation: int,
    issued_at: datetime | None = None,
    ttl_seconds: int = MAX_RESET_TTL_SECONDS,
    nonce: str | None = None,
) -> dict[str, Any]:
    """Create an explicit, short-lived operator reset proof; never clears a switch."""
    now = issued_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("OPERATOR_RESET_TIMEZONE_REQUIRED")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
        raise ValueError("OPERATOR_RESET_TTL_INVALID")
    if not 1 <= ttl_seconds <= MAX_RESET_TTL_SECONDS:
        raise ValueError("OPERATOR_RESET_TTL_OUT_OF_RANGE")
    if isinstance(kill_switch_generation, bool) or not isinstance(kill_switch_generation, int) or kill_switch_generation < 1:
        raise ValueError("OPERATOR_RESET_GENERATION_INVALID")
    fault_source = source_sha if fault_source_sha is None else fault_source_sha
    required = (operator_id, reason, source_sha, fault_source, account_loginid)
    if any(not isinstance(value, str) or not value.strip() for value in required):
        raise ValueError("OPERATOR_RESET_BINDING_FIELDS_REQUIRED")
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "nonce": nonce or secrets.token_hex(24),
        "operator_id": operator_id.strip(),
        "reason": reason.strip(),
        "source_sha": source_sha.strip(),
        "fault_source_sha": fault_source.strip(),
        "account_loginid": account_loginid.strip(),
        "kill_switch_generation": kill_switch_generation,
        "issued_at_utc": now.astimezone(timezone.utc).isoformat(),
        "expires_at_utc": (now.astimezone(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat(),
    }
    record["signature"] = _signature(record, signing_key)
    return record


def verify_operator_reset_record(
    record: dict[str, Any],
    *,
    signing_key: str,
    expected_reason: str,
    expected_source_sha: str,
    expected_fault_source_sha: str | None = None,
    expected_account_loginid: str,
    expected_generation: int,
    last_consumed_nonce: str | None = None,
    now: datetime | None = None,
) -> tuple[bool, str, str | None]:
    """Validate a one-use reset proof bound to this kill event and account."""
    if not isinstance(record, dict):
        return False, "OPERATOR_RESET_RECORD_INVALID", None
    required = (
        "schema", "nonce", "operator_id", "reason", "source_sha",
        "fault_source_sha", "account_loginid", "kill_switch_generation", "issued_at_utc",
        "expires_at_utc", "signature",
    )
    if any(not isinstance(record.get(key), str) or not record[key].strip()
           for key in required if key != "kill_switch_generation"):
        return False, "OPERATOR_RESET_FIELDS_MISSING", None
    if record.get("schema") != SCHEMA:
        return False, "OPERATOR_RESET_SCHEMA_INVALID", None
    nonce = record.get("nonce", "")
    if len(nonce) < 24:
        return False, "OPERATOR_RESET_NONCE_INVALID", None
    if nonce == last_consumed_nonce:
        return False, "OPERATOR_RESET_REPLAYED", None
    generation = record.get("kill_switch_generation")
    if isinstance(generation, bool) or not isinstance(generation, int):
        return False, "OPERATOR_RESET_GENERATION_INVALID", None
    if generation != expected_generation:
        return False, "OPERATOR_RESET_GENERATION_MISMATCH", None
    if record.get("reason") != expected_reason:
        return False, "OPERATOR_RESET_REASON_MISMATCH", None
    if record.get("source_sha") != expected_source_sha or not expected_source_sha.strip():
        return False, "OPERATOR_RESET_SOURCE_MISMATCH", None
    expected_fault_source = expected_source_sha if expected_fault_source_sha is None else expected_fault_source_sha
    if (
        record.get("fault_source_sha") != expected_fault_source
        or not isinstance(expected_fault_source, str)
        or not expected_fault_source.strip()
    ):
        return False, "OPERATOR_RESET_FAULT_SOURCE_MISMATCH", None
    if record.get("account_loginid") != expected_account_loginid or not expected_account_loginid.strip():
        return False, "OPERATOR_RESET_ACCOUNT_MISMATCH", None
    try:
        issued = datetime.fromisoformat(record["issued_at_utc"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(record["expires_at_utc"].replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False, "OPERATOR_RESET_TIME_INVALID", None
    current = now or datetime.now(timezone.utc)
    if issued.tzinfo is None or expires.tzinfo is None or current.tzinfo is None:
        return False, "OPERATOR_RESET_TIMEZONE_REQUIRED", None
    ttl = (expires - issued).total_seconds()
    if issued > current or expires <= current or ttl <= 0 or ttl > MAX_RESET_TTL_SECONDS:
        return False, "OPERATOR_RESET_EXPIRED_OR_TEMPORALLY_INVALID", None
    try:
        expected_signature = _signature(record, signing_key)
    except (TypeError, ValueError, OverflowError):
        return False, "OPERATOR_RESET_SIGNING_KEY_INVALID", None
    supplied_signature = record.get("signature", "")
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return False, "OPERATOR_RESET_SIGNATURE_INVALID", None
    return True, "OPERATOR_RESET_VERIFIED", nonce


def read_operator_reset_record(path: Path) -> dict[str, Any] | None:
    """Read only a regular non-symlink JSON file, with all parse errors denied."""
    try:
        if path.is_symlink() or not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
