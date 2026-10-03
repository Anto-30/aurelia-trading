import json
import tempfile
import unittest
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
        record = {
            "evidence_id": "E-TEST",
            "source_hash": "s",
            "artifact_hash": "a",
            "config_hash": "c",
            "data_hash": "d",
            "environment": "ci",
            "started_at_utc": "2026-10-03T10:00:00Z",
            "ended_at_utc": "2026-10-03T10:01:00Z",
            "status": "CURRENT",
            "result": "PROVEN",
            "invariants_failed": [],
            "transaction_trace_complete": True,
            "broker_unknown_recovery_proven": True,
            "reconciliation_proven": True,
            "critical_scenarios_passed": True,
            "blind_resubmissions": 0,
            "duplicate_economic_effects": 0,
            "duration_seconds": 3600,
            "invariant_violations": 0,
            "silent_degradations": 0,
            "capital_authority_escapes": 0,
            "unresolved_unknown_states": 0,
            "sealed_prospective_data": True,
            "retuning_after_seal": False,
            "min_trades_per_strategy_symbol_regime": 100,
            "calibration_validated": True,
            "drift_monitoring": True,
            "brier_score": 0.2,
            "log_loss": 0.6,
            "net_expectancy_status": "KNOWN",
            "stress_passed": True,
            "credential_isolation_passed": True,
            "capital_bypass_audit_passed": True,
            "source_commit": "commit",
            "build_hash": "build",
            "artifact_hash": "a",
            "deployment_id": "deploy",
            "runtime_hash": "a",
            "config_hash": "c",
            "runtime_matches_artifact": True,
        }
        record["record_hash"] = payload_sha256(record)
        return record

    def _populate_passing_bundle(self, root: Path) -> None:
        for marker in REQUIRED_RUNTIME_MARKERS:
            self._write(root, marker, "runtime")
        for relative in REQUIRED_EVIDENCE_FILES:
            self._write(root, relative, json.dumps(self._passing_record()))

    def test_missing_bundle_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            status, detail = validate_evidence_bundle(Path(d))
            self.assertEqual(status, "BLOCKED")
            self.assertIn("Missing evidence artifacts", detail)

    def test_passing_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._populate_passing_bundle(root)
            status, detail = validate_evidence_bundle(root)
            self.assertEqual(status, "PASS", detail)

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
