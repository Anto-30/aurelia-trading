from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from assurance.certification_evidence import validate_evidence_file
from scripts.emit_recovery_matrix_evidence import build_recovery_matrix_record


NOW = datetime.now(timezone.utc)


def passing_result() -> dict[str, int | bool]:
    return {
        "passed": True,
        "iterations": 3600,
        "unknown_outcomes_observed": 24,
        "unknown_records": 0,
        "stale_authorization_blocked": 28,
        "kill_switch_blocked": 24,
        "concurrent_duplicate_checks": 31,
        "reconciliation_mismatch_checks": 19,
        "duplicate_economic_effects": 0,
        "blind_resubmissions": 0,
    }


class RecoveryMatrixEvidenceTests(unittest.TestCase):
    def test_builds_validator_compatible_ci_simulation_evidence(self) -> None:
        record = build_recovery_matrix_record(
            passing_result(),
            source_commit="a" * 40,
            issuer="github-actions:12345",
            started_at_utc=(NOW - timedelta(seconds=3)).isoformat(),
            ended_at_utc=NOW.isoformat(),
        )

        self.assertEqual(record["environment"], "ci")
        self.assertEqual(record["result"], "PROVEN")
        self.assertTrue(record["critical_scenarios_passed"])
        self.assertEqual(len(record["scenario_results"]), 5)
        self.assertEqual(record["blind_resubmissions"], 0)
        self.assertEqual(record["duplicate_economic_effects"], 0)
        self.assertEqual(record["evidence_classification"], "CI_SIMULATION_ONLY")
        self.assertFalse(record["broker_truth_observed"])
        self.assertFalse(record["capital_authority_granted"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_path = root / "evidence" / "recovery_matrix.json"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text(json.dumps(record), encoding="utf-8")
            status, detail = validate_evidence_file(root, "evidence/recovery_matrix.json")
        self.assertEqual((status, detail), ("PASS", "valid"))

    def test_failed_scenario_is_not_promoted_to_passing_evidence(self) -> None:
        result = passing_result()
        result["kill_switch_blocked"] = 0
        record = build_recovery_matrix_record(
            result,
            source_commit="b" * 40,
            issuer="github-actions:12346",
            started_at_utc=(NOW - timedelta(seconds=3)).isoformat(),
            ended_at_utc=NOW.isoformat(),
        )

        self.assertFalse(record["critical_scenarios_passed"])
        self.assertEqual(record["result"], "UNPROVEN")
        self.assertTrue(record["invariants_failed"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_path = root / "evidence" / "recovery_matrix.json"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text(json.dumps(record), encoding="utf-8")
            status, _ = validate_evidence_file(root, "evidence/recovery_matrix.json")
        self.assertEqual(status, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
