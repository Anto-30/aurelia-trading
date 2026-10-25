import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "aurelia_certification_report.schema.json"


def pending_report():
    gate_names = (
        "gate_1_broker_lifecycle",
        "gate_2_recovery_matrix",
        "gate_3_soak_test_3600s",
        "gate_4_out_of_sample",
        "gate_5_calibration",
        "gate_6_execution_economics",
        "gate_7_security_audit",
        "gate_8_deployment",
        "gate_9_strategy_eligibility",
    )
    report = {
        "report_metadata": {
            "commit_sha": "a" * 40,
            "generated_at_utc": "2026-10-25T00:00:00Z",
            "environment": "verify_only",
        },
        "safety_state": {
            "live_execution": "BLOCKED",
            "final_authorization": False,
            "capital_plane_mode": "VERIFY_ONLY",
        },
        "final_disposition": {
            "overall_status": "NOT_READY",
            "human_review_required": True,
            "human_reviewer_signature": None,
        },
    }
    report.update({name: {"status": "PENDING"} for name in gate_names})
    return report


class CertificationReportSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def test_all_pending_report_is_valid_without_fabricated_evidence_hashes(self):
        self.validator.validate(pending_report())

    def test_pass_without_evidence_hash_is_rejected(self):
        report = pending_report()
        report["gate_1_broker_lifecycle"] = {
            "status": "PASS",
            "otp_latency_ms": 10,
        }
        self.assertTrue(list(self.validator.iter_errors(report)))

    def test_pass_requires_gate_specific_evidence(self):
        report = pending_report()
        report["gate_1_broker_lifecycle"] = {
            "status": "PASS",
            "evidence_log_hash": "b" * 64,
        }
        self.assertTrue(list(self.validator.iter_errors(report)))

    def test_certified_requires_reviewer_signature(self):
        report = pending_report()
        report["final_disposition"] = {
            "overall_status": "CERTIFIED",
            "human_review_required": True,
            "human_reviewer_signature": None,
        }
        self.assertTrue(list(self.validator.iter_errors(report)))

    def test_certified_report_requires_all_nine_gates_to_pass(self):
        report = pending_report()
        report["final_disposition"] = {
            "overall_status": "CERTIFIED",
            "human_review_required": True,
            "human_reviewer_signature": "reviewer-signature-reference",
        }
        self.assertTrue(list(self.validator.iter_errors(report)))

    def test_non_fail_closed_safety_state_is_rejected(self):
        report = pending_report()
        report["safety_state"]["final_authorization"] = True
        self.assertTrue(list(self.validator.iter_errors(report)))


if __name__ == "__main__":
    unittest.main()
