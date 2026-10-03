"""Strict evidence-bundle validation for AURELIA certification.

Evidence artifacts must be produced by genuine runtime/research operations.
The validator never creates passing evidence and never treats placeholders as
proof. Every evidence envelope hash is recomputed before it can pass.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence_writer import payload_sha256

REQUIRED_RUNTIME_MARKERS = (
    "services/adapters/deriv_adapter.py",
    "services/validation/walk_forward.py",
    "config/LIVE_LOCK.yaml",
)

REQUIRED_EVIDENCE_FILES = (
    "evidence/broker_lifecycle.json",
    "evidence/recovery_matrix.json",
    "evidence/soak_3600s.json",
    "evidence/prospective_oos.json",
    "evidence/calibration.json",
    "evidence/execution_economics.json",
    "evidence/security_audit.json",
    "evidence/deployment.json",
)

PASS_RESULTS = {"PASS", "PROVEN", "VALIDATED"}


def _parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _load(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("evidence root must be an object")
    return raw


def _base_valid(record: dict[str, Any], now: datetime) -> tuple[bool, str]:
    for key in (
        "evidence_id", "source_hash", "artifact_hash", "config_hash",
        "data_hash", "environment", "started_at_utc", "ended_at_utc",
        "status", "result", "record_hash",
    ):
        if not isinstance(record.get(key), str) or not record[key].strip():
            return False, f"missing/blank {key}"

    if record["status"] not in {"CURRENT", "EXPIRING"}:
        return False, f"invalid status {record['status']!r}"
    if record["result"] not in PASS_RESULTS:
        return False, f"result {record['result']!r} is not passing evidence"

    try:
        started = _parse_utc(record["started_at_utc"])
        ended = _parse_utc(record["ended_at_utc"])
    except (TypeError, ValueError) as exc:
        return False, f"invalid timestamp: {exc}"
    if ended < started or ended > now:
        return False, "invalid evidence time interval"

    if record.get("valid_until_utc"):
        try:
            if now >= _parse_utc(record["valid_until_utc"]):
                return False, "evidence expired"
        except (TypeError, ValueError) as exc:
            return False, f"invalid valid_until_utc: {exc}"

    if record.get("invariants_failed"):
        return False, "invariants_failed is non-empty"

    supplied_hash = record["record_hash"]
    unsigned = {k: v for k, v in record.items() if k != "record_hash"}
    if supplied_hash != payload_sha256(unsigned):
        return False, "record_hash mismatch"
    return True, "valid"


def _domain_valid(name: str, record: dict[str, Any]) -> tuple[bool, str]:
    if name == "broker_lifecycle.json":
        return (
            record.get("transaction_trace_complete") is True
            and record.get("broker_unknown_recovery_proven") is True
            and record.get("reconciliation_proven") is True,
            "broker lifecycle/recovery/reconciliation evidence incomplete",
        )
    if name == "recovery_matrix.json":
        return (
            record.get("critical_scenarios_passed") is True
            and record.get("blind_resubmissions") == 0
            and record.get("duplicate_economic_effects") == 0,
            "recovery matrix evidence incomplete",
        )
    if name == "soak_3600s.json":
        return (
            isinstance(record.get("duration_seconds"), int)
            and record["duration_seconds"] >= 3600
            and record.get("invariant_violations") == 0
            and record.get("silent_degradations") == 0
            and record.get("capital_authority_escapes") == 0
            and record.get("unresolved_unknown_states") == 0,
            "genuine 3600-second soak evidence incomplete",
        )
    if name == "prospective_oos.json":
        return (
            record.get("sealed_prospective_data") is True
            and record.get("retuning_after_seal") is False
            and isinstance(record.get("min_trades_per_strategy_symbol_regime"), int)
            and record["min_trades_per_strategy_symbol_regime"] >= 100,
            "prospective OOS evidence incomplete",
        )
    if name == "calibration.json":
        return (
            record.get("calibration_validated") is True
            and record.get("drift_monitoring") is True
            and isinstance(record.get("brier_score"), (int, float))
            and isinstance(record.get("log_loss"), (int, float)),
            "probability calibration evidence incomplete",
        )
    if name == "execution_economics.json":
        return (
            record.get("net_expectancy_status") == "KNOWN"
            and record.get("stress_passed") is True,
            "net execution economics are not fully established",
        )
    if name == "security_audit.json":
        return (
            record.get("credential_isolation_passed") is True
            and record.get("capital_bypass_audit_passed") is True,
            "security/bypass audit incomplete",
        )
    if name == "deployment.json":
        return (
            bool(record.get("source_commit"))
            and bool(record.get("build_hash"))
            and bool(record.get("artifact_hash"))
            and bool(record.get("deployment_id"))
            and bool(record.get("runtime_hash"))
            and bool(record.get("config_hash"))
            and record.get("runtime_matches_artifact") is True,
            "deployment lineage incomplete",
        )
    return False, "unknown evidence type"


def validate_evidence_bundle(root: Path) -> tuple[str, str]:
    missing = [p for p in REQUIRED_EVIDENCE_FILES if not (root / p).exists()]
    if missing:
        return "BLOCKED", f"Missing evidence artifacts: {', '.join(missing)}"

    now = datetime.now(timezone.utc)
    errors: list[str] = []
    for relative in REQUIRED_EVIDENCE_FILES:
        path = root / relative
        try:
            record = _load(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{relative}: cannot parse ({exc})")
            continue
        ok, detail = _base_valid(record, now)
        if not ok:
            errors.append(f"{relative}: {detail}")
            continue
        ok, detail = _domain_valid(path.name, record)
        if not ok:
            errors.append(f"{relative}: {detail}")

    if errors:
        return "BLOCKED", "Evidence validation failed: " + "; ".join(errors)
    return "PASS", "All required evidence artifacts are current, passing, and schema-valid."
