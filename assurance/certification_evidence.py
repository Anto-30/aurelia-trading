"""Strict evidence-bundle validation for AURELIA certification.

Evidence artifacts must be produced by approved runtime/CI/research operations.
The validator never creates passing evidence and never treats repository-tracked
placeholders as proof.
"""
from __future__ import annotations

import json
import subprocess
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
ALLOWED_EVIDENCE_ENVIRONMENTS = {"ci", "research", "staging", "production"}
ALLOWED_EVIDENCE_ORIGINS = {"ci", "research", "runtime"}


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
    historical_missing = [
        p for p in HISTORICAL_RUNTIME_MARKERS if not (root / p).exists()
    ]
    baseline_missing = [
        p for p in NEW_BASELINE_RUNTIME_MARKERS if not (root / p).exists()
    ]
    if not historical_missing:
        return "HISTORICAL", []
    if not baseline_missing:
        return "NEW_BASELINE", []
    return "BLOCKED", baseline_missing


def _is_git_tracked(root: Path, relative: str) -> bool:
    """Reject versioned evidence so source-controlled assertions cannot certify themselves."""
    if not (root / ".git").exists():
        return False
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    return result.returncode == 0


def _provenance_valid(record: dict[str, Any]) -> tuple[bool, str]:
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        return False, "missing provenance envelope"

    for key in ("origin", "issuer", "source_commit", "generated_at_utc"):
        value = provenance.get(key)
        if not isinstance(value, str) or not value.strip():
            return False, f"missing/blank provenance.{key}"

    origin = provenance["origin"].strip().lower()
    if origin not in ALLOWED_EVIDENCE_ORIGINS:
        return False, f"invalid provenance.origin {origin!r}"

    try:
        generated = _parse_utc(provenance["generated_at_utc"])
    except (TypeError, ValueError) as exc:
        return False, f"invalid provenance.generated_at_utc: {exc}"

    now = datetime.now(timezone.utc)
    if generated > now:
        return False, "provenance.generated_at_utc is in the future"

    environment = str(record.get("environment", "")).strip().lower()
    if environment not in ALLOWED_EVIDENCE_ENVIRONMENTS:
        return False, f"invalid evidence environment {environment!r}"

    if environment == "production":
        if origin != "runtime":
            return False, "production evidence must originate from runtime"
        if not str(provenance.get("deployment_id", "")).strip():
            return False, "production evidence requires provenance.deployment_id"

    return True, "valid"


def _base_valid(record: dict[str, Any], now: datetime) -> tuple[bool, str]:
    required = (
        "evidence_id",
        "source_hash",
        "artifact_hash",
        "config_hash",
        "data_hash",
        "environment",
        "started_at_utc",
        "ended_at_utc",
        "status",
        "result",
        "record_hash",
    )
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

    provenance_ok, provenance_detail = _provenance_valid(record)
    if not provenance_ok:
        return False, provenance_detail

    unsigned = {k: v for k, v in record.items() if k != "record_hash"}
    if record["record_hash"] != payload_sha256(unsigned):
        return False, "record_hash mismatch"

    return True, "valid"


def _non_empty_string(record: dict[str, Any], key: str) -> bool:
    return isinstance(record.get(key), str) and bool(record[key].strip())


def _domain_valid(name: str, record: dict[str, Any]) -> tuple[bool, str]:
    if name == "broker_lifecycle.json":
        ok = (
            record.get("transaction_trace_complete") is True
            and record.get("broker_unknown_recovery_proven") is True
            and record.get("reconciliation_proven") is True
            and _non_empty_string(record, "broker_transaction_id")
            and isinstance(record.get("lifecycle_events"), list)
            and len(record["lifecycle_events"]) >= 6
        )
        return ok, "valid" if ok else "broker lifecycle/recovery/reconciliation evidence incomplete"

    if name == "recovery_matrix.json":
        scenarios = record.get("scenario_results")
        ok = (
            record.get("critical_scenarios_passed") is True
            and isinstance(scenarios, list)
            and len(scenarios) >= 3
            and all(
                isinstance(x, dict) and x.get("passed") is True
                for x in scenarios
            )
            and record.get("blind_resubmissions") == 0
            and record.get("duplicate_economic_effects") == 0
        )
        return ok, "valid" if ok else "recovery matrix evidence incomplete"

    if name == "soak_3600s.json":
        ok = (
            isinstance(record.get("duration_seconds"), int)
            and record["duration_seconds"] >= 3600
            and isinstance(record.get("actual_elapsed_seconds"), (int, float))
            and record["actual_elapsed_seconds"] >= 3600
            and record.get("continuous") is True
            and record.get("execution_mode") == "VERIFY_ONLY"
            and _non_empty_string(record, "deployment_id")
            and _non_empty_string(record, "runtime_instance_id")
            and record.get("invariant_violations") == 0
            and record.get("silent_degradations") == 0
            and record.get("capital_authority_escapes") == 0
            and record.get("unresolved_unknown_states") == 0
        )
        return ok, "valid" if ok else "genuine 3600-second soak evidence incomplete"

    if name == "prospective_oos.json":
        ok = (
            record.get("sealed_prospective_data") is True
            and record.get("retuning_after_seal") is False
            and record.get("multiple_testing_accounted") is True
            and _non_empty_string(record, "archive_hash")
            and _non_empty_string(record, "strategy_version")
            and _non_empty_string(record, "oos_window")
            and isinstance(
                record.get("min_trades_per_strategy_symbol_regime"), int
            )
            and record["min_trades_per_strategy_symbol_regime"] >= 100
        )
        return ok, "valid" if ok else "prospective OOS evidence incomplete"

    if name == "calibration.json":
        buckets = record.get("reliability_buckets")
        ok = (
            record.get("calibration_validated") is True
            and record.get("drift_monitoring") is True
            and isinstance(record.get("sample_count"), int)
            and record["sample_count"] > 0
            and isinstance(buckets, list)
            and len(buckets) >= 3
            and isinstance(record.get("brier_score"), (int, float))
            and isinstance(record.get("log_loss"), (int, float))
            and record["brier_score"] >= 0
            and record["log_loss"] >= 0
        )
        return ok, "valid" if ok else "probability calibration evidence incomplete"

    if name == "execution_economics.json":
        costs = record.get("cost_components")
        ok = (
            record.get("net_expectancy_status") == "KNOWN"
            and record.get("stress_passed") is True
            and isinstance(record.get("sample_count"), int)
            and record["sample_count"] > 0
            and isinstance(costs, dict)
            and bool(costs)
            and _non_empty_string(record, "execution_model")
        )
        return ok, "valid" if ok else "net execution economics are not fully established"

    if name == "security_audit.json":
        findings = record.get("findings")
        ok = (
            record.get("credential_isolation_passed") is True
            and record.get("capital_bypass_audit_passed") is True
            and _non_empty_string(record, "audit_id")
            and _non_empty_string(record, "auditor")
            and _non_empty_string(record, "scope")
            and isinstance(findings, list)
            and len(findings) > 0
            and record.get("critical_findings", 1) == 0
        )
        return ok, "valid" if ok else "security/bypass audit incomplete"

    if name == "deployment.json":
        ok = (
            all(
                _non_empty_string(record, key)
                for key in (
                    "source_commit",
                    "build_hash",
                    "artifact_hash",
                    "deployment_id",
                    "runtime_hash",
                    "config_hash",
                )
            )
            and record.get("runtime_matches_artifact") is True
        )
        return ok, "valid" if ok else "deployment lineage incomplete"

    return False, "unknown evidence type"


def validate_evidence_file(
    root: Path,
    relative: str,
    *,
    now: datetime | None = None,
) -> tuple[str, str]:
    path = root / relative
    if not path.exists():
        return "BLOCKED", f"missing evidence artifact: {relative}"

    if _is_git_tracked(root, relative):
        return "BLOCKED", f"evidence artifact is repository-tracked: {relative}"

    try:
        record = _load(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return "BLOCKED", f"{relative}: cannot parse ({exc})"

    observed_now = now or datetime.now(timezone.utc)
    ok, detail = _base_valid(record, observed_now)
    if not ok:
        return "BLOCKED", f"{relative}: {detail}"

    ok, detail = _domain_valid(Path(relative).name, record)
    if not ok:
        return "BLOCKED", f"{relative}: {detail}"

    return "PASS", "valid"


def validate_evidence_bundle(root: Path) -> tuple[str, str]:
    results = [
        (relative, validate_evidence_file(root, relative))
        for relative in REQUIRED_EVIDENCE_FILES
    ]
    errors = [
        f"{relative}: {detail}"
        for relative, (status, detail) in results
        if status != "PASS"
    ]
    if errors:
        return "BLOCKED", "Evidence validation failed: " + "; ".join(errors)
    return "PASS", (
        "All required evidence artifacts are current, passing, "
        "provenance-valid, and untracked."
    )
