import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from assurance.certification_evidence import (
    REQUIRED_EVIDENCE_FILES,
    REQUIRED_RUNTIME_MARKERS,
    validate_evidence_bundle,
)
from assurance.certification_gate import _overall_status
from assurance.evidence_writer import payload_sha256


class CertificationEvidenceTest(unittest.TestCase):
    def _write(self, root: Path, relative: str, content: str = "") -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _passing_record(self) -> dict:
        now = datetime.now(timezone.utc)
        source_commit = "a" * 40
        record = {
            "evidence_id": "E-TEST",
            "source_hash": source_commit,
            "artifact_hash": "b" * 64,
            "config_hash": "c" * 64,
            "data_hash": "d" * 64,
            "environment": "ci",
            "started_at_utc": (now - timedelta(minutes=1)).isoformat(),
            "ended_at_utc": now.isoformat(),
            "valid_until_utc": (now + timedelta(days=7)).isoformat(),
            "status": "CURRENT",
            "result": "PROVEN",
            "invariants_failed": [],
            "provenance": {
                "origin": "ci",
                "issuer": "test-suite",
                "source_commit": source_commit,
                "generated_at_utc": now.isoformat(),
            },
            "transaction_trace_complete": True,
            "broker_unknown_recovery_proven": True,
            "reconciliation_proven": True,
            "broker_truth_observed": True,
            "broker_transaction_id": "TX-TEST",
            "lifecycle_events": [
                {"event": "INTENT"},
                {"event": "REQUEST"},
                {"event": "ACK"},
                {"event": "STATE"},
                {"event": "TRANSACTION"},
                {"event": "RECONCILIATION"},
            ],
            "critical_scenarios_passed": True,
            "scenario_results": [
                {"scenario_id": "UNKNOWN", "passed": True},
                {"scenario_id": "CRASH", "passed": True},
                {"scenario_id": "CONCURRENCY", "passed": True},
                {"scenario_id": "KILL_SWITCH", "passed": True},
                {"scenario_id": "RECONCILIATION", "passed": True},
            ],
            "blind_resubmissions": 0,
            "duplicate_economic_effects": 0,
            "duration_seconds": 3600,
            "actual_elapsed_seconds": 3600,
            "continuous": True,
            "execution_mode": "VERIFY_ONLY",
            "deployment_id": "DEPLOY-TEST",
            "runtime_instance_id": "RUNTIME-TEST",
            "invariant_violations": 0,
            "silent_degradations": 0,
            "capital_authority_escapes": 0,
            "unresolved_unknown_states": 0,
            "evidence_classification": "ADVERSARIAL_RUNTIME_SOAK",
            "fault_matrix": {
                "stale_and_duplicate_market_data": True,
                "out_of_order_events": True,
                "websocket_interruption": True,
                "request_timeout": True,
                "response_loss_after_economic_effect": True,
                "unknown_broker_state": True,
                "duplicate_and_concurrent_intent": True,
                "crash_at_lifecycle_transitions": True,
                "restart_with_kill_switch": True,
                "stale_authorization": True,
                "configuration_and_account_mismatch": True,
                "ledger_reconciliation_mismatch": True,
                "backup_restore": True,
                "credential_boundary_violation": True,
                "shadow_path_divergence": True,
            },
            "sealed_prospective_data": True,
            "retuning_after_seal": False,
            "multiple_testing_accounted": True,
            "archive_hash": "f" * 64,
            "strategy_version": "S-TEST",
            "oos_window": "2026-01-01/2026-01-31",
            "min_trades_per_strategy_symbol_regime": 100,
            "calibration_validated": True,
            "drift_monitoring": True,
            "drift_detected": False,
            "sample_count": 1000,
            "reliability_buckets": [
                {"bucket": "0.55-0.60", "count": 100, "mean_probability": 0.575, "realized_rate": 0.57},
                {"bucket": "0.60-0.65", "count": 100, "mean_probability": 0.625, "realized_rate": 0.62},
                {"bucket": "0.65-0.70", "count": 100, "mean_probability": 0.675, "realized_rate": 0.67},
            ],
            "max_reliability_gap": 0.005,
            "brier_score": 0.2,
            "log_loss": 0.6,
            "net_expectancy_status": "KNOWN",
            "net_expectancy": 0.12,
            "realized_execution_status": "MEASURED",
            "stress_passed": True,
            "cost_components": {"spread": 0.01, "slippage": 0.01, "fees": 0.0},
            "execution_model": "DERIV_OPTIONS_MEASURED",
            "credential_isolation_passed": True,
            "capital_bypass_audit_passed": True,
            "audit_id": "AUDIT-TEST",
            "auditor": "auditor@example.test",
            "independent_reviewer": "reviewer@example.test",
            "independent_review_reference": "https://github.com/example/review/123",
            "independent_review_approval": "APPROVED",
            "reviewed_commit": source_commit,
            "scope": "capital-boundary",
            "findings": [{"severity": "info", "count": 0}],
            "critical_findings": 0,
            "source_commit": source_commit,
            "build_hash": "e" * 64,
            "artifact_hash": "b" * 64,
            "deployment_id": "DEPLOY-TEST",
            "runtime_hash": "f" * 64,
            "config_hash": "c" * 64,
            "runtime_matches_artifact": True,
            "qualification_passed": True,
            "strategies": [
                {
                    "strategy_id": "S-TEST",
                    "qualified": True,
                    "trade_count": 100,
                    "strategy_hash": "1" * 64,
                }
            ],
            "edge_removed": True,
        }
        record["record_hash"] = payload_sha256(record)
        return record

    def _populate_passing_bundle(self, root: Path) -> None:
        for marker in REQUIRED_RUNTIME_MARKERS:
            self._write(root, marker, "runtime")
        for relative in REQUIRED_EVIDENCE_FILES:
            record = self._passing_record()
            name = Path(relative).name
            provenance = record["provenance"]
            if name == "broker_lifecycle.json":
                record.update({"environment": "staging", "broker_truth_observed": True})
                provenance["origin"] = "runtime"
            elif name == "recovery_matrix.json":
                record.update({
                    "environment": "ci",
                    "evidence_classification": "CI_SIMULATION_ONLY",
                    "execution_mode": "DETERMINISTIC_BROKER_STUB",
                    "broker_truth_observed": False,
                    "capital_authority_granted": False,
                    "order_submission_permitted": False,
                    "live_execution": "BLOCKED",
                })
                provenance["origin"] = "ci"
            elif name == "soak_3600s.json":
                record.update({"environment": "staging"})
                provenance["origin"] = "runtime"
            elif name in {"prospective_oos.json", "calibration.json", "strategy_eligibility.json"}:
                record.update({"environment": "research"})
                provenance["origin"] = "research"
            elif name == "execution_economics.json":
                record.update({
                    "environment": "staging",
                    "realized_execution_status": "MEASURED",
                    "net_expectancy": 0.12,
                })
                provenance["origin"] = "runtime"
            elif name == "security_audit.json":
                record.update({"environment": "ci"})
                provenance["origin"] = "ci"
            elif name == "deployment.json":
                record.update({"environment": "production"})
                provenance["origin"] = "runtime"
                provenance["deployment_id"] = record["deployment_id"]
            record["record_hash"] = payload_sha256(
                {key: value for key, value in record.items() if key != "record_hash"}
            )
            self._write(root, relative, json.dumps(record))

    def test_missing_bundle_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            status, detail = validate_evidence_bundle(Path(d))
            self.assertEqual(status, "BLOCKED")
            self.assertIn("missing evidence artifact", detail)

    def test_passing_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            status, detail = validate_evidence_bundle(root)
            self.assertEqual(status, "PASS", detail)

    def test_tracked_evidence_cannot_certify_itself(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            tracked = root / REQUIRED_EVIDENCE_FILES[0]
            subprocess.run(["git", "add", str(tracked)], cwd=root, check=True)
            status, detail = validate_evidence_bundle(root)
            self.assertEqual(status, "BLOCKED")
            self.assertIn("repository-tracked", detail)

    def test_incomplete_domain_proof_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            path = root / "evidence/broker_lifecycle.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record.pop("lifecycle_events")
            record["record_hash"] = payload_sha256(
                {key: value for key, value in record.items() if key != "record_hash"}
            )
            path.write_text(json.dumps(record), encoding="utf-8")
            status, detail = validate_evidence_bundle(root)
            self.assertEqual(status, "BLOCKED")
            self.assertIn("broker lifecycle", detail)

    def test_detected_probability_drift_blocks_calibration(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            path = root / "evidence/calibration.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["drift_detected"] = True
            record["record_hash"] = payload_sha256(
                {key: value for key, value in record.items() if key != "record_hash"}
            )
            path.write_text(json.dumps(record), encoding="utf-8")
            status, detail = validate_evidence_bundle(root)
            self.assertEqual(status, "BLOCKED")
            self.assertIn("calibration or drift", detail)

    def test_nonfinite_calibration_metric_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            path = root / "evidence/calibration.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["brier_score"] = float("inf")
            record["record_hash"] = payload_sha256(
                {key: value for key, value in record.items() if key != "record_hash"}
            )
            path.write_text(json.dumps(record, allow_nan=True), encoding="utf-8")
            status, detail = validate_evidence_bundle(root)
            self.assertEqual(status, "BLOCKED")
            self.assertIn("calibration or drift", detail)

    def test_tampered_evidence_hash_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            path = root / "evidence/execution_economics.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["stress_passed"] = False
            path.write_text(json.dumps(record), encoding="utf-8")

            status, detail = validate_evidence_bundle(root)
            self.assertEqual(status, "BLOCKED")
            self.assertIn("record_hash mismatch", detail)


    def _rewrite_record(self, root: Path, relative: str, mutate) -> tuple[str, str]:
        path = root / relative
        record = json.loads(path.read_text(encoding="utf-8"))
        mutate(record)
        record["record_hash"] = payload_sha256(
            {key: value for key, value in record.items() if key != "record_hash"}
        )
        path.write_text(json.dumps(record), encoding="utf-8")
        from assurance.certification_evidence import validate_evidence_file
        return validate_evidence_file(root, relative)

    def test_ci_stub_cannot_certify_real_broker_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            status, detail = self._rewrite_record(
                root,
                "evidence/broker_lifecycle.json",
                lambda record: (
                    record.update({"environment": "ci", "broker_truth_observed": False}),
                    record["provenance"].update({"origin": "ci"}),
                ),
            )
            self.assertEqual(status, "BLOCKED", detail)
            self.assertIn("broker", detail.lower())

    def test_ci_health_soak_cannot_certify_adversarial_runtime_soak(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            status, detail = self._rewrite_record(
                root,
                "evidence/soak_3600s.json",
                lambda record: (
                    record.update({"environment": "ci"}),
                    record["provenance"].update({"origin": "ci"}),
                ),
            )
            self.assertEqual(status, "BLOCKED", detail)
            self.assertIn("soak", detail.lower())

    def test_ci_deployment_assertion_cannot_certify_production_deployment(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            status, detail = self._rewrite_record(
                root,
                "evidence/deployment.json",
                lambda record: (
                    record.update({"environment": "ci"}),
                    record["provenance"].update({"origin": "ci"}),
                ),
            )
            self.assertEqual(status, "BLOCKED", detail)
            self.assertIn("deployment", detail.lower())

    def test_ci_generated_oos_data_is_not_prospective_research_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            status, detail = self._rewrite_record(
                root,
                "evidence/prospective_oos.json",
                lambda record: (
                    record.update({"environment": "ci"}),
                    record["provenance"].update({"origin": "ci"}),
                ),
            )
            self.assertEqual(status, "BLOCKED", detail)
            self.assertIn("prospective", detail.lower())

    def test_ci_generated_calibration_is_not_research_calibration_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            status, detail = self._rewrite_record(
                root,
                "evidence/calibration.json",
                lambda record: (
                    record.update({"environment": "ci"}),
                    record["provenance"].update({"origin": "ci"}),
                ),
            )
            self.assertEqual(status, "BLOCKED", detail)
            self.assertIn("calibration", detail.lower())

    def test_quoted_economics_without_realized_execution_costs_are_not_proven(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            status, detail = self._rewrite_record(
                root,
                "evidence/execution_economics.json",
                lambda record: record.update({
                    "realized_execution_status": "NOT_MEASURED",
                    "net_expectancy": None,
                }),
            )
            self.assertEqual(status, "BLOCKED", detail)
            self.assertIn("economics", detail.lower())

    def test_security_audit_requires_independent_review_reference(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            status, detail = self._rewrite_record(
                root,
                "evidence/security_audit.json",
                lambda record: record.pop("independent_review_reference", None),
            )
            self.assertEqual(status, "BLOCKED", detail)
            self.assertIn("security", detail.lower())

    def test_evidence_source_commit_must_match_provenance_commit(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            status, detail = self._rewrite_record(
                root,
                "evidence/recovery_matrix.json",
                lambda record: record["provenance"].update({"source_commit": "DIFFERENT"}),
            )
            self.assertEqual(status, "BLOCKED", detail)
            self.assertIn("source", detail.lower())

    def test_evidence_must_have_expiry(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            status, detail = self._rewrite_record(
                root,
                "evidence/recovery_matrix.json",
                lambda record: record.pop("valid_until_utc", None),
            )
            self.assertEqual(status, "BLOCKED", detail)
            self.assertIn("valid_until_utc", detail)

    def test_live_execution_block_is_not_repository_failure(self):
        result = [
            {"name": "ASSURANCE_DOCUMENTS", "status": "PASS", "detail": ""},
            {"name": "HARDENING_CONTRACTS", "status": "PASS", "detail": ""},
            {"name": "AURELIA_SOURCE_SYNC", "status": "PASS", "detail": ""},
            {"name": "PRODUCTION_EVIDENCE", "status": "PASS", "detail": ""},
            {"name": "LIVE_EXECUTION", "status": "BLOCKED", "detail": ""},
        ]
        self.assertEqual(_overall_status(result), "READY_FOR_CAPITAL_REVIEW")


if __name__ == "__main__":
    unittest.main()
