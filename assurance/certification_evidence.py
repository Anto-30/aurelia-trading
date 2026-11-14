"""Strict evidence-bundle validation for AURELIA certification.

Evidence artifacts must be produced by approved runtime/CI/research operations.
The validator never creates passing evidence and never treats repository-tracked
placeholders as proof.
"""
from __future__ import annotations

import json
import math
import os
import re
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
    "evidence/strategy_eligibility.json",
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


def current_source_sha(root: Path) -> str:
    """Resolve the reviewed candidate commit, not a pull-request merge commit."""
    explicit = os.getenv("AURELIA_SOURCE_SHA", "").strip()
    if explicit:
        return explicit if re.fullmatch(r"[0-9a-f]{40}", explicit) else ""

    if os.getenv("GITHUB_EVENT_NAME", "").strip() == "pull_request":
        event_path = os.getenv("GITHUB_EVENT_PATH", "").strip()
        if not event_path:
            return ""
        try:
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        head = event.get("pull_request", {}).get("head", {})
        value = head.get("sha", "") if isinstance(head, dict) else ""
        return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) else ""

    value = os.getenv("GITHUB_SHA", "").strip()
    if value:
        return value if re.fullmatch(r"[0-9a-f]{40}", value) else ""

    if not (root / ".git").exists():
        return ""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    value = result.stdout.strip()
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else ""


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

    source_hash = record.get("source_hash")
    if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{40}", source_hash):
        return False, "source_hash must be a full lowercase Git commit SHA"
    if provenance.get("source_commit") != source_hash:
        return False, "provenance.source_commit does not match source_hash"

    for key in ("artifact_hash", "config_hash", "data_hash"):
        value = record.get(key)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            return False, f"{key} must be a 64-character lowercase SHA-256 digest"

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

    if not isinstance(record.get("valid_until_utc"), str) or not record["valid_until_utc"].strip():
        return False, "missing/blank valid_until_utc"
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


def _source_matches(
    record: dict[str, Any],
    *,
    environments: set[str],
    origins: set[str],
) -> bool:
    provenance = record.get("provenance")
    return (
        isinstance(provenance, dict)
        and str(record.get("environment", "")).lower() in environments
        and str(provenance.get("origin", "")).lower() in origins
    )


def _domain_valid(name: str, record: dict[str, Any]) -> tuple[bool, str]:
    if name == "broker_lifecycle.json":
        source_ok = _source_matches(
            record,
            environments={"staging", "production"},
            origins={"runtime"},
        ) and record.get("broker_truth_observed") is True
        ok = (
            source_ok
            and record.get("transaction_trace_complete") is True
            and record.get("broker_unknown_recovery_proven") is True
            and record.get("reconciliation_proven") is True
            and _non_empty_string(record, "broker_transaction_id")
            and isinstance(record.get("lifecycle_events"), list)
            and len(record["lifecycle_events"]) >= 6
        )
        return ok, "valid" if ok else "broker lifecycle must contain runtime-origin broker truth and a complete reconciled transaction trace"

    if name == "recovery_matrix.json":
        scenarios = record.get("scenario_results")
        ci_simulation = (
            record.get("evidence_classification") == "CI_SIMULATION_ONLY"
            and record.get("execution_mode") == "DETERMINISTIC_BROKER_STUB"
            and record.get("broker_truth_observed") is False
            and record.get("capital_authority_granted") is False
            and record.get("order_submission_permitted") is False
            and record.get("live_execution") == "BLOCKED"
            and _source_matches(record, environments={"ci"}, origins={"ci"})
        )
        runtime_evidence = _source_matches(
            record,
            environments={"staging", "production"},
            origins={"runtime"},
        )
        ok = (
            (ci_simulation or runtime_evidence)
            and record.get("critical_scenarios_passed") is True
            and isinstance(scenarios, list)
            and len(scenarios) >= 3
            and all(
                isinstance(x, dict) and x.get("passed") is True
                for x in scenarios
            )
            and record.get("blind_resubmissions") == 0
            and record.get("duplicate_economic_effects") == 0
        )
        return ok, "valid" if ok else "recovery matrix evidence incomplete or simulation provenance is not explicitly segregated"

    if name == "soak_3600s.json":
        fault_matrix = record.get("fault_matrix")
        required_faults = {
            "stale_and_duplicate_market_data",
            "out_of_order_events",
            "websocket_interruption",
            "request_timeout",
            "response_loss_after_economic_effect",
            "unknown_broker_state",
            "duplicate_and_concurrent_intent",
            "crash_at_lifecycle_transitions",
            "restart_with_kill_switch",
            "stale_authorization",
            "configuration_and_account_mismatch",
            "ledger_reconciliation_mismatch",
            "backup_restore",
            "credential_boundary_violation",
            "shadow_path_divergence",
        }
        source_ok = _source_matches(
            record,
            environments={"staging", "production"},
            origins={"runtime"},
        )
        fault_matrix_ok = (
            isinstance(fault_matrix, dict)
            and all(fault_matrix.get(key) is True for key in required_faults)
        )
        ok = (
            source_ok
            and fault_matrix_ok
            and record.get("evidence_classification") == "ADVERSARIAL_RUNTIME_SOAK"
            and isinstance(record.get("duration_seconds"), int)
            and not isinstance(record.get("duration_seconds"), bool)
            and record["duration_seconds"] >= 3600
            and isinstance(record.get("actual_elapsed_seconds"), (int, float))
            and not isinstance(record.get("actual_elapsed_seconds"), bool)
            and math.isfinite(float(record["actual_elapsed_seconds"]))
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
        return ok, "valid" if ok else "full 3600-second adversarial runtime soak evidence incomplete"

    if name == "prospective_oos.json":
        source_ok = _source_matches(
            record,
            environments={"research"},
            origins={"research"},
        )
        ok = (
            source_ok
            and record.get("sealed_prospective_data") is True
            and record.get("retuning_after_seal") is False
            and record.get("multiple_testing_accounted") is True
            and _non_empty_string(record, "archive_hash")
            and _non_empty_string(record, "strategy_version")
            and _non_empty_string(record, "oos_window")
            and isinstance(
                record.get("min_trades_per_strategy_symbol_regime"), int
            )
            and not isinstance(record.get("min_trades_per_strategy_symbol_regime"), bool)
            and record["min_trades_per_strategy_symbol_regime"] >= 100
        )
        return ok, "valid" if ok else "prospective OOS evidence incomplete or not research-originated"

    if name == "calibration.json":
        source_ok = _source_matches(
            record,
            environments={"research"},
            origins={"research"},
        )
        buckets = record.get("reliability_buckets")
        sample_count = record.get("sample_count")
        brier = record.get("brier_score")
        log_loss = record.get("log_loss")
        max_gap = record.get("max_reliability_gap")
        finite_metrics = all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for value in (brier, log_loss, max_gap)
        )
        buckets_valid = (
            isinstance(buckets, list)
            and len(buckets) >= 3
            and all(
                isinstance(bucket, dict)
                and isinstance(bucket.get("count"), int)
                and not isinstance(bucket.get("count"), bool)
                and bucket["count"] >= 10
                and isinstance(bucket.get("mean_probability"), (int, float))
                and not isinstance(bucket.get("mean_probability"), bool)
                and math.isfinite(float(bucket["mean_probability"]))
                and 0 <= float(bucket["mean_probability"]) <= 1
                and isinstance(bucket.get("realized_rate"), (int, float))
                and not isinstance(bucket.get("realized_rate"), bool)
                and math.isfinite(float(bucket["realized_rate"]))
                and 0 <= float(bucket["realized_rate"]) <= 1
                and abs(float(bucket["mean_probability"]) - float(bucket["realized_rate"])) <= 0.05
                for bucket in buckets
            )
        )
        ok = (
            source_ok
            and record.get("calibration_validated") is True
            and record.get("drift_monitoring") is True
            and record.get("drift_detected") is False
            and isinstance(sample_count, int)
            and not isinstance(sample_count, bool)
            and sample_count >= 100
            and buckets_valid
            and finite_metrics
            and float(brier) >= 0
            and float(log_loss) >= 0
            and float(max_gap) <= 0.05
        )
        return ok, "valid" if ok else "probability calibration or drift evidence incomplete or not research-originated"

    if name == "execution_economics.json":
        costs = record.get("cost_components")
        expectancy = record.get("net_expectancy")
        costs_valid = (
            isinstance(costs, dict)
            and bool(costs)
            and all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                and float(value) >= 0
                for value in costs.values()
            )
        )
        source_ok = _source_matches(
            record,
            environments={"staging", "production"},
            origins={"runtime"},
        )
        expectancy_valid = (
            isinstance(expectancy, (int, float))
            and not isinstance(expectancy, bool)
            and math.isfinite(float(expectancy))
            and float(expectancy) > 0
        )
        ok = (
            source_ok
            and record.get("realized_execution_status") == "MEASURED"
            and expectancy_valid
            and record.get("net_expectancy_status") == "KNOWN"
            and record.get("stress_passed") is True
            and isinstance(record.get("sample_count"), int)
            and not isinstance(record.get("sample_count"), bool)
            and record["sample_count"] > 0
            and costs_valid
            and _non_empty_string(record, "execution_model")
        )
        return ok, "valid" if ok else "realized net execution economics are not fully measured and positive"

    if name == "security_audit.json":
        findings = record.get("findings")
        reviewer = record.get("independent_reviewer")
        auditor = record.get("auditor")
        review_reference = record.get("independent_review_reference")
        review_reference_valid = False
        if isinstance(review_reference, str) and review_reference.startswith(
            "https://github.com/"
        ):
            review_path, marker, review_id = review_reference.partition(
                "#pullrequestreview-"
            )
            path_parts = review_path.removeprefix("https://github.com/").split("/")
            review_reference_valid = (
                marker == "#pullrequestreview-"
                and len(path_parts) == 4
                and bool(path_parts[0])
                and bool(path_parts[1])
                and path_parts[2] == "pull"
                and path_parts[3].isdigit()
                and review_id.isdigit()
                and int(review_id) > 0
                and int(path_parts[3]) > 0
            )
        independent_review_ok = (
            review_reference_valid
            and _non_empty_string(record, "independent_review_approval")
            and record.get("independent_review_approval") == "APPROVED"
            and isinstance(reviewer, str)
            and reviewer.strip()
            and not reviewer.strip().lower().endswith("[bot]")
            and isinstance(auditor, str)
            and auditor.strip()
            and reviewer.strip().casefold() != auditor.strip().casefold()
            and record.get("reviewed_commit") == record.get("source_hash")
        )
        source_ok = _source_matches(
            record,
            environments={"staging", "production"},
            origins={"runtime"},
        )
        ok = (
            source_ok
            and independent_review_ok
            and record.get("credential_isolation_passed") is True
            and record.get("capital_bypass_audit_passed") is True
            and _non_empty_string(record, "audit_id")
            and _non_empty_string(record, "auditor")
            and _non_empty_string(record, "scope")
            and isinstance(findings, list)
            and len(findings) > 0
            and record.get("critical_findings", 1) == 0
        )
        return ok, "valid" if ok else "security audit requires distinct independent reviewer approval tied to the audited commit"

    if name == "strategy_eligibility.json":
        strategies = record.get("strategies")
        source_ok = _source_matches(
            record,
            environments={"research"},
            origins={"research"},
        )
        ok = (
            source_ok
            and record.get("qualification_passed") is True
            and isinstance(strategies, list)
            and len(strategies) > 0
            and all(
                isinstance(item, dict)
                and item.get("qualified") is True
                and isinstance(item.get("trade_count"), int)
                and not isinstance(item.get("trade_count"), bool)
                and item.get("trade_count") >= 100
                and isinstance(item.get("strategy_hash"), str)
                and bool(item.get("strategy_hash"))
                for item in strategies
            )
            and record.get("edge_removed") is True
        )
        return ok, "valid" if ok else "strategy live-eligibility evidence incomplete or not research-originated"

    if name == "deployment.json":
        source_ok = _source_matches(
            record,
            environments={"production"},
            origins={"runtime"},
        )
        provenance = record.get("provenance")
        deployment_matches = (
            isinstance(provenance, dict)
            and provenance.get("deployment_id") == record.get("deployment_id")
        )
        ok = (
            source_ok
            and deployment_matches
            and all(
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
            and record.get("source_commit") == record.get("source_hash")
            and record.get("runtime_matches_artifact") is True
        )
        return ok, "valid" if ok else "production deployment lineage incomplete or not runtime-originated"

    return False, "unknown evidence type"

def validate_evidence_file(
    root: Path,
    relative: str,
    *,
    now: datetime | None = None,
    expected_source_sha: str | None = None,
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

    if expected_source_sha is not None:
        if not re.fullmatch(r"[0-9a-f]{40}", expected_source_sha):
            return "BLOCKED", "candidate source SHA is invalid"
        if record.get("source_hash") != expected_source_sha:
            return "BLOCKED", f"{relative}: evidence source hash does not match candidate commit"

    ok, detail = _domain_valid(Path(relative).name, record)
    if not ok:
        return "BLOCKED", f"{relative}: {detail}"

    return "PASS", "valid"


def validate_evidence_bundle(
    root: Path,
    *,
    expected_source_sha: str | None = None,
) -> tuple[str, str]:
    results = [
        (
            relative,
            validate_evidence_file(
                root,
                relative,
                expected_source_sha=expected_source_sha,
            ),
        )
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
