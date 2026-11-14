from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from assurance.control_path_soak import run_control_path_soak
from assurance.evidence_writer import build_evidence, payload_sha256, write_evidence


SCENARIO_NAMES = (
    "unknown_outcome_recovered_without_blind_retry",
    "stale_authorization_rejected",
    "independent_kill_switch_blocks_submission",
    "concurrent_duplicate_intent_is_idempotent",
    "reconciliation_mismatch_fails_closed",
)


def _count(result: Mapping[str, Any], key: str, default: int = 0) -> int:
    value = result.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _scenario_results(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    unknown_ok = (
        _count(result, "unknown_outcomes_observed") > 0
        and _count(result, "recovered") > 0
        and _count(result, "unknown_records", 1) == 0
        and _count(result, "blind_resubmission_checks") > 0
        and _count(result, "blind_resubmissions", 1) == 0
    )
    stale_ok = _count(result, "stale_authorization_blocked") > 0
    kill_switch_ok = _count(result, "kill_switch_blocked") > 0
    duplicate_ok = (
        _count(result, "concurrent_duplicate_checks") > 0
        and _count(result, "duplicate_economic_effects", 1) == 0
        and _count(result, "idempotent_effects_recorded", -1)
        == _count(result, "economic_effects", -2)
    )
    reconciliation_checks = _count(result, "reconciliation_mismatch_checks")
    reconciliation_failures = _count(result, "reconciliation_mismatch_failures", -1)
    reconciliation_ok = (
        reconciliation_checks > 0
        and reconciliation_failures == reconciliation_checks
    )

    return [
        {
            "name": SCENARIO_NAMES[0],
            "passed": unknown_ok,
            "observed": {
                "unknown_outcomes": _count(result, "unknown_outcomes_observed"),
                "recovered": _count(result, "recovered"),
                "unresolved_unknown": _count(result, "unknown_records", 1),
                "blind_retry_checks": _count(result, "blind_resubmission_checks"),
                "blind_resubmissions": _count(result, "blind_resubmissions", 1),
            },
        },
        {
            "name": SCENARIO_NAMES[1],
            "passed": stale_ok,
            "observed": {"blocked_stale_authorizations": _count(result, "stale_authorization_blocked")},
        },
        {
            "name": SCENARIO_NAMES[2],
            "passed": kill_switch_ok,
            "observed": {"blocked_kill_switch_attempts": _count(result, "kill_switch_blocked")},
        },
        {
            "name": SCENARIO_NAMES[3],
            "passed": duplicate_ok,
            "observed": {
                "concurrent_duplicate_checks": _count(result, "concurrent_duplicate_checks"),
                "economic_effects": _count(result, "economic_effects", -1),
                "idempotent_effects_recorded": _count(result, "idempotent_effects_recorded", -2),
                "duplicate_economic_effects": _count(result, "duplicate_economic_effects", 1),
            },
        },
        {
            "name": SCENARIO_NAMES[4],
            "passed": reconciliation_ok,
            "observed": {
                "mismatch_checks": reconciliation_checks,
                "mismatches_rejected": reconciliation_failures,
            },
        },
    ]


def build_recovery_matrix_record(
    result: Mapping[str, Any],
    *,
    source_commit: str,
    issuer: str,
    started_at_utc: str,
    ended_at_utc: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("RECOVERY_MATRIX_SOURCE_COMMIT_INVALID")
    if not issuer.strip():
        raise ValueError("RECOVERY_MATRIX_ISSUER_REQUIRED")

    started = datetime.fromisoformat(started_at_utc.replace("Z", "+00:00"))
    ended = datetime.fromisoformat(ended_at_utc.replace("Z", "+00:00"))
    if started.tzinfo is None or ended.tzinfo is None or ended < started:
        raise ValueError("RECOVERY_MATRIX_TIME_RANGE_INVALID")

    scenarios = _scenario_results(result)
    passed = (
        result.get("passed") is True
        and _count(result, "iterations") >= 3600
        and all(item["passed"] is True for item in scenarios)
    )
    failed_scenarios = [item["name"] for item in scenarios if not item["passed"]]
    if result.get("passed") is not True:
        failed_scenarios.append("control_path_soak_harness_failed")
    if _count(result, "iterations") < 3600:
        failed_scenarios.append("minimum_3600_control_path_cycles_not_completed")

    evidence = build_evidence(
        evidence_id=f"RECOVERY_MATRIX_CI:{source_commit[:12]}",
        source_hash=source_commit,
        artifact_hash=payload_sha256(
            {
                "harness": "assurance.control_path_soak.run_control_path_soak",
                "source_commit": source_commit,
            }
        ),
        config_hash=payload_sha256(
            {
                "iterations": _count(result, "iterations"),
                "scenario_names": list(SCENARIO_NAMES),
                "execution_mode": "DETERMINISTIC_BROKER_STUB",
            }
        ),
        data_hash=payload_sha256(dict(result)),
        environment="ci",
        started_at_utc=started_at_utc,
        ended_at_utc=ended_at_utc,
        valid_until_utc=(ended + timedelta(days=14)).isoformat(),
        status="CURRENT",
        result="PROVEN" if passed else "UNPROVEN",
        provenance={
            "origin": "ci",
            "issuer": issuer,
            "source_commit": source_commit,
            "generated_at_utc": ended_at_utc,
        },
        invariants_checked=list(SCENARIO_NAMES),
        invariants_failed=failed_scenarios,
    )
    evidence.update(
        {
            "critical_scenarios_passed": passed,
            "scenario_results": scenarios,
            "blind_resubmissions": _count(result, "blind_resubmissions", 1),
            "duplicate_economic_effects": _count(result, "duplicate_economic_effects", 1),
            "evidence_classification": "CI_SIMULATION_ONLY",
            "execution_mode": "DETERMINISTIC_BROKER_STUB",
            "iterations": _count(result, "iterations"),
            "authenticated_deriv_session": False,
            "broker_truth_observed": False,
            "capital_authority_granted": False,
            "order_submission_permitted": False,
            "live_execution": "BLOCKED",
        }
    )
    evidence["record_hash"] = payload_sha256(
        {key: value for key, value in evidence.items() if key != "record_hash"}
    )
    return evidence


async def _run() -> int:
    source_commit = os.getenv("GITHUB_SHA", "").strip()
    run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or not run_id:
        print("RECOVERY_MATRIX_EVIDENCE=BLOCKED")
        print("REASON=GITHUB_CI_PROVENANCE_REQUIRED")
        return 2

    started = datetime.now(timezone.utc)
    result = await run_control_path_soak(iterations=3600)
    ended = datetime.now(timezone.utc)
    record = build_recovery_matrix_record(
        result,
        source_commit=source_commit,
        issuer=f"github-actions:{run_id}",
        started_at_utc=started.isoformat(),
        ended_at_utc=ended.isoformat(),
    )
    output = Path(
        os.getenv("AURELIA_RECOVERY_MATRIX_EVIDENCE_OUT", "evidence/recovery_matrix.json")
    )
    write_evidence(output, record)
    print(
        json.dumps(
            {
                "RECOVERY_MATRIX_EVIDENCE": "PROVEN_CI_SIMULATION"
                if record["critical_scenarios_passed"]
                else "UNPROVEN",
                "EVIDENCE_PATH": str(output),
                "EVIDENCE_HASH": record["record_hash"],
                "ITERATIONS": record["iterations"],
                "SCENARIOS_PASSED": sum(
                    1 for item in record["scenario_results"] if item["passed"]
                ),
                "SCENARIOS_TOTAL": len(record["scenario_results"]),
                "BROKER_TRUTH_OBSERVED": False,
                "CAPITAL_AUTHORITY_GRANTED": False,
                "LIVE_EXECUTION": "BLOCKED",
            },
            sort_keys=True,
        )
    )
    return 0 if record["critical_scenarios_passed"] else 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
