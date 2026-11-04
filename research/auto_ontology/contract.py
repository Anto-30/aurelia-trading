"""Research-only evidence and query policy for an isolated Auto Ontology service.

Security posture:
- no network/database/MCP client is implemented here;
- generated SQL is never executed by AURELIA;
- only exact, pre-certified query templates may be accepted by a future adapter;
- missing, stale, future-dated, unprovenanced or non-research evidence fails closed;
- this module has no capital or broker authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Mapping


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class EvidenceValidationError(ValueError):
    """Raised when evidence is incomplete or violates the research boundary."""


@dataclass(frozen=True)
class EvidenceEnvelope:
    evidence_id: str
    source_system: str
    source_ref: str
    source_commit: str
    dataset_sha256: str
    payload_sha256: str
    strategy_id: str
    strategy_version: str
    timeframe: str
    units: str
    grain: str
    decision_time: datetime
    available_at: datetime
    observed_at: datetime
    evidence_status: str
    data_scope: str = "RESEARCH"
    capital_authority: bool = False
    live_order_submission: bool = False


def _require_token(name: str, value: str) -> None:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise EvidenceValidationError(f"{name} must be a non-empty bounded token")


def _require_aware_utc(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise EvidenceValidationError(f"{name} must be timezone-aware")
    if value.utcoffset() is None:
        raise EvidenceValidationError(f"{name} must have a defined UTC offset")


def validate_evidence(envelope: EvidenceEnvelope) -> None:
    """Validate immutable lineage and no-lookahead properties.

    UNKNOWN is a valid recorded status, but it is never equivalent to PASS.
    Callers must explicitly require PASS before using evidence for qualification.
    """
    if not isinstance(envelope, EvidenceEnvelope):
        raise EvidenceValidationError("EvidenceEnvelope required")

    for name in (
        "evidence_id", "source_system", "source_ref", "strategy_id",
        "strategy_version", "timeframe", "units", "grain",
    ):
        _require_token(name, getattr(envelope, name))

    if not _GIT_SHA_RE.fullmatch(envelope.source_commit or ""):
        raise EvidenceValidationError("source_commit must be a 40-character Git SHA")
    if not _SHA256_RE.fullmatch(envelope.dataset_sha256 or ""):
        raise EvidenceValidationError("dataset_sha256 must be a lowercase SHA-256")
    if not _SHA256_RE.fullmatch(envelope.payload_sha256 or ""):
        raise EvidenceValidationError("payload_sha256 must be a lowercase SHA-256")

    for name in ("decision_time", "available_at", "observed_at"):
        _require_aware_utc(name, getattr(envelope, name))

    decision = envelope.decision_time.astimezone(timezone.utc)
    available = envelope.available_at.astimezone(timezone.utc)
    observed = envelope.observed_at.astimezone(timezone.utc)

    if available > decision:
        raise EvidenceValidationError("look-ahead evidence: available_at exceeds decision_time")
    if observed < available:
        raise EvidenceValidationError("observed_at cannot precede available_at")
    if envelope.evidence_status not in {"PASS", "FAIL", "UNKNOWN"}:
        raise EvidenceValidationError("evidence_status must be PASS, FAIL, or UNKNOWN")
    if envelope.data_scope != "RESEARCH":
        raise EvidenceValidationError("only RESEARCH-scoped data is accepted")
    if envelope.capital_authority is not False:
        raise EvidenceValidationError("capital_authority must remain false")
    if envelope.live_order_submission is not False:
        raise EvidenceValidationError("live_order_submission must remain false")


def sha256_hex(payload: bytes) -> str:
    """Return a deterministic SHA-256 digest for caller-supplied evidence bytes."""
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class QueryPolicy:
    """Exact-template allowlist; this class does not execute SQL.

    A future isolated adapter may compare generated query output with the
    registered template. Arbitrary LLM-generated SQL is rejected by default.
    """
    templates: Mapping[str, str]

    def validate(self, query_id: str, sql: str) -> str:
        _require_token("query_id", query_id)
        if not isinstance(sql, str) or not sql.strip():
            raise EvidenceValidationError("SQL text is required")
        approved = self.templates.get(query_id)
        if approved is None:
            raise EvidenceValidationError("query_id is not allowlisted")
        if sql != approved:
            raise EvidenceValidationError("SQL must exactly match the certified template")
        if ";" in sql.rstrip().rstrip(";"):
            raise EvidenceValidationError("multiple SQL statements are forbidden")
        # Templates are authored and reviewed by maintainers, never generated at runtime.
        if not re.match(r"^\s*SELECT\b", sql, flags=re.IGNORECASE):
            raise EvidenceValidationError("certified templates must be SELECT statements")
        if re.search(
            r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY|CALL|DO)\b",
            sql,
            flags=re.IGNORECASE,
        ):
            raise EvidenceValidationError("mutating or procedural SQL is forbidden")
        return approved
