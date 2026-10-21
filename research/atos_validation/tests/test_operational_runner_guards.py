from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_oos_validation import COST_SCHEMA, _load_cost_evidence
from scripts.run_soak_test import percentile


class OperationalRunnerGuardTests(unittest.TestCase):
    def test_oos_cost_evidence_must_bind_source_dataset_window_and_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "quotes.csv"
            source.write_text("quote_time,stake,payout\n2026-01-01T00:00:00Z,1,1.8\n", encoding="utf-8")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            payload = {
                "schema": COST_SCHEMA,
                "symbol": "R_100",
                "oos_start_epoch": 100,
                "oos_end_epoch": 200,
                "data_sha256": "a" * 64,
                "trade_ledger_sha256": "b" * 64,
                "cost_basis": "verified_deriv_quote_snapshot",
                "cost_source_file": source.name,
                "cost_source_sha256": digest,
                "cost_method": "entry quote and exit settlement rules documented in source",
                "independent_review_status": "PENDING",
            }
            evidence = root / "cost-evidence.json"
            evidence.write_text(json.dumps(payload), encoding="utf-8")
            accepted = _load_cost_evidence(
                evidence, symbol="R_100", start_epoch=100, end_epoch=200,
                data_sha256="a" * 64, ledger_sha256="b" * 64,
            )
            self.assertEqual(accepted["cost_source_sha256_verified"], digest)
            self.assertFalse(accepted["cost_source_authenticity_independently_verified"])

    def test_oos_cost_evidence_rejects_wrong_dataset_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.csv"
            source.write_text("source\n", encoding="utf-8")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            evidence = root / "cost-evidence.json"
            evidence.write_text(json.dumps({
                "schema": COST_SCHEMA,
                "symbol": "R_100",
                "oos_start_epoch": 100,
                "oos_end_epoch": 200,
                "data_sha256": "0" * 64,
                "trade_ledger_sha256": "b" * 64,
                "cost_basis": "preregistered_conservative_scenario",
                "cost_source_file": source.name,
                "cost_source_sha256": digest,
                "cost_method": "preregistered conservative scenario",
                "independent_review_status": "PENDING",
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "data_sha256"):
                _load_cost_evidence(
                    evidence, symbol="R_100", start_epoch=100, end_epoch=200,
                    data_sha256="a" * 64, ledger_sha256="b" * 64,
                )

    def test_soak_percentile_handles_empty_and_populated_samples(self):
        self.assertIsNone(percentile([], .95))
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], .95), 4.0)


if __name__ == "__main__":
    unittest.main()
