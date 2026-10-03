"""Strict evidence-bundle validation for AURELIA certification.

Evidence artifacts must be produced by genuine runtime/research operations.
The validator never creates passing evidence and never treats placeholders as
proof.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence_writer import payload_sha256

HISTORICAL_RUNTIME_MARKERS = (
    "services/adapters/deriv_adapter.py",
    "services/validation/walk_forward.py",
    "config/LIVE_LOCK.yaml",
)

NEW_BASELINE_RUNTIME_MARKERS = (
    "runtime/main.py",
    "runtime/adapters/deriv_adapter.py",
    "runtime/broker/executor.py",
    "runtime/core/authority.py",
    "runtime/core/models.py",
    "config/LIVE_LOCK.yaml",
    "railway.toml",
)

REQUIRED_RUNTIME_MARKERS = NEW_BASELINE_RUNTIME_MARKERS

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

def runtime_source_status(root: Path) -> tuple[str, list[str]]:
    historical_missing = [p for p in HISTORICAL_RUNTIME_MARKERS if not (root / p).exists()]
    baseline_missing = [p for p in NEW_BASELINE_RUNTIME_MARKERS if not (root / p).exists()]
    if not historical_missing:
        return "HISTORICAL", []
    if not baseline_missing:
        return "NEW_BASELINE", []
    return "BLOCKED", baseline_missing

def _base_valid(record: dict[str, Any], now: datetime) -> tuple[bool, str]:
    required = ("evidence_id", "source_hash", "artifact_hash", "config_hash", "data_hash", "environment", "started_at_utc", "ended_at_utc", "status", "result", "record_hash")
    for key in required:
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
    unsigned = {k: v for k, v in record.items() if k != "record_hash"}
    if record["record_hash"] != payload_sha256(unsigned):
        return False, "record_hash mismatch"
    return True, "valid"

def _domain_valid(name: str, record: dict[str, Any]) -> tuple[bool, str]:
    if name == "broker_lifecycle.json":
        ok = record.get("transaction_trace_complete") is True and record.get("broker_unknown_recovery_proven") is True and record.get("reconciliation_proven") is True
        return ok, "valid" if ok else "broker lifecycle/recovery/reconciliation evidence incomplete"
    if name == "recovery_matrix.json":
        ok = record.get("critical_scenarios_passed") is True and record.get("blind_resubmissions") == 0 and record.get("duplicate_economic_effects") == 0
        return ok, "valid" if ok else "recovery matrix evidence incomplete"
    if name == "soak_3600s.json":
        ok = isinstance(record.get("duration_seconds"), int) and record["duration_seconds"] >= 3600 and record.get("invariant_violations") == 0 and record.get("silent_degradations") == 0 and record.get("capital_authority_escapes") == 0 and record.get("unresolved_unknown_states") == 0
        return ok, "valid" if ok else "genuine 3600-second soak evidence incomplete"
    if name == "prospective_oos.json":
        ok = record.get("sealed_prospective_data") is True and record.get("retuning_after_seal") is False and isinstance(record.get("min_trades_per_strategy_symbol_regime"), int) and record["min_trades_per_strategy_symbol_regime"] >= 100
        return ok, "valid" if ok else "prospective OOS evidence incomplete"
    if name == "calibration.json":
        ok = record.get("calibration_validated") is True and record.get("drift_monitoring") is True and isinstance(record.get("brier_score"), (int, float)) and isinstance(record.get("log_loss"), (int, float))
        return ok, "valid" if ok else "probability calibration evidence incomplete"
    if name == "execution_economics.json":
        ok = record.get("net_expectancy_status") == "KNOWN" and record.get("stress_passed") is True
        return ok, "valid" if ok else "net execution economics are not fully established"
    if name == "security_audit.json":
        ok = record.get("credential_isolation_passed") is True and record.get("capital_bypass_audit_passed") is True
        return ok, "valid" if ok else "security/bypass audit incomplete"
    if name == "deployment.json":
        ok = all(bool(record.get(k)) for k in ("source_commit", "build_hash", "artifact_hash", "deployment_id", "runtime_hash", "config_hash")) and record.get("runtime_matches_artifact") is True
        return ok, "valid" if ok else "deployment lineage incomplete"
    return False, "unknown evidence type"

def validate_evidence_bundle(root: Path) -> tuple[str, str]:
    missing = [p for p in REQUIRED_EVIDENCE_FILES if not (root / p).exists()]
    if missing:
        return "BLOCKED", f"Missing evidence artifacts: {', '.join(missing)}"
    now = datetime.now(timezone.utc)
    errors: list[str] = []
    for relative in REQUIRED_EVIDENCE_FILES:
        try:
            record = _load(root / relative)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{relative}: cannot parse ({exc})")
            continue
        ok, detail = _base_valid(record, now)
        if not ok:
            errors.append(f"{relative}: {detail}")
            continue
        ok, detail = _domain_valid(Path(relative).name, record)
        if not ok:
            errors.append(f"{relative}: {detail}")
    if errors:
        return "BLOCKED", "Evidence validation failed: " + "; ".join(errors)
    return "PASS", "All required evidence artifacts are current, passing, and schema-valid."

