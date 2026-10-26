import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "aurelia_certification_report.schema.json"
CONFIG_SCHEMA_PATH = ROOT / "config" / "AURELIA_CERTIFICATION_REPORT.schema.json"


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
            "research_capital_authority": False,
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

    def test_config_schema_matches_canonical_schema(self):
        config_schema = json.loads(CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
        canonical_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(config_schema)
        # Each copy must have a resolvable path-specific ID; all rules must match.
        config_id = config_schema.pop("$id", None)
        canonical_id = canonical_schema.pop("$id", None)
        self.assertTrue(config_id and config_id.endswith("/config/AURELIA_CERTIFICATION_REPORT.schema.json"))
        self.assertTrue(canonical_id and canonical_id.endswith("/schemas/aurelia_certification_report.schema.json"))
        self.assertEqual(config_schema, canonical_schema)

    def test_all_pending_report_is_valid_without_fabricated_evidence_hashes(self):
        self.validator.validate(pending_report())

    def test_checked_in_certification_report_matches_schema(self):
        report_path = ROOT / "AURELIA_CERTIFICATION_REPORT.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.validator.validate(report)

    def test_config_schema_mirror_matches_canonical_schema(self):
        config_schema_path = ROOT / "config" / "AURELIA_CERTIFICATION_REPORT.schema.json"
        config_schema = json.loads(config_schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(config_schema)

        # The two schema copies have path-specific IDs; every other schema rule must match.
        canonical_for_compare = dict(self.schema)
        config_for_compare = dict(config_schema)
        canonical_for_compare.pop("$id", None)
        config_for_compare.pop("$id", None)
        self.assertEqual(
            config_for_compare,
            canonical_for_compare,
            "config schema must mirror the canonical report schema; divergent report shapes are unsafe",
        )
        report_path = ROOT / "AURELIA_CERTIFICATION_REPORT.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        Draft202012Validator(config_schema).validate(report)

    def test_checked_in_report_has_no_duplicate_json_keys(self):
        def reject_duplicates(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
                result[key] = value
            return result

        report_path = ROOT / "AURELIA_CERTIFICATION_REPORT.json"
        json.loads(
            report_path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
        )

    def test_semgrep_severity_breakdown_reconciles_to_sast_total(self):
        report = json.loads(
            (ROOT / "AURELIA_CERTIFICATION_REPORT.json").read_text(encoding="utf-8")
        )
        gate = report["gate_7_security_audit"]
        severities = (
            "semgrep_error_severity_findings",
            "semgrep_warning_severity_findings",
            "semgrep_info_severity_findings",
            "semgrep_medium_severity_findings",
            "semgrep_unknown_severity_findings",
        )
        self.assertEqual(
            sum(gate.get(key, 0) for key in severities),
            gate["sast_findings"],
        )

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

    def test_research_capital_authority_must_remain_disabled(self):
        report = pending_report()
        report["safety_state"]["research_capital_authority"] = True
        self.assertTrue(list(self.validator.iter_errors(report)))


if __name__ == "__main__":
    unittest.main()
