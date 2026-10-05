from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Attestation:
    issuer: str
    subject: str
    capability: str
    status: str
    issued_at_utc: str
    expires_at_utc: str
    source_sha: str
    runtime_id: str
    config_hash: str
    evidence_hash: str
    provenance: str
    signature: str


class AttestationError(ValueError):
    pass


def canonical_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k != "signature"}


def payload_hash(record: dict[str, Any]) -> str:
    encoded = json.dumps(
        canonical_payload(record),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sign_attestation(record: dict[str, Any], signing_key: str) -> dict[str, Any]:
    if not signing_key:
        raise AttestationError("signing key is required")
    signed = dict(record)
    # HMAC-style keyed digest. The secret never belongs in the artifact.
    material = signing_key.encode("utf-8") + b":" + payload_hash(signed).encode("ascii")
    signed["signature"] = hashlib.sha256(material).hexdigest()
    return signed


def verify_attestation(
    record: dict[str, Any],
    *,
    signing_key: str,
    expected_source_sha: str,
    expected_runtime_id: str,
    expected_config_hash: str,
    now: datetime | None = None,
) -> Attestation:
    required = (
        "issuer", "subject", "capability", "status", "issued_at_utc",
        "expires_at_utc", "source_sha", "runtime_id", "config_hash",
        "evidence_hash", "provenance", "signature",
    )
    if not isinstance(record, dict):
        raise AttestationError("attestation must be an object")
    if any(not isinstance(record.get(k), str) or not record[k].strip() for k in required):
        raise AttestationError("attestation contains missing required fields")
    if record["status"] != "PASS":
        raise AttestationError("only PASS attestations can satisfy readiness")
    if record["source_sha"] != expected_source_sha:
        raise AttestationError("source SHA mismatch")
    if record["runtime_id"] != expected_runtime_id:
        raise AttestationError("runtime identity mismatch")
    if record["config_hash"] != expected_config_hash:
        raise AttestationError("configuration hash mismatch")
    if record["provenance"] not in {"runtime", "ci", "broker", "control_plane"}:
        raise AttestationError("invalid provenance")

    now = now or datetime.now(timezone.utc)
    issued = datetime.fromisoformat(record["issued_at_utc"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(record["expires_at_utc"].replace("Z", "+00:00"))
    if issued.tzinfo is None or expires.tzinfo is None:
        raise AttestationError("attestation timestamps must be timezone-aware")
    if issued > now or expires <= now or expires <= issued:
        raise AttestationError("attestation is expired or temporally invalid")

    if not signing_key:
        raise AttestationError("verification key unavailable")
    material = signing_key.encode("utf-8") + b":" + payload_hash(record).encode("ascii")
    expected = hashlib.sha256(material).hexdigest()
    if record["signature"] != expected:
        raise AttestationError("invalid attestation signature")

    return Attestation(**{k: record[k] for k in required})


def write_attestation(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
