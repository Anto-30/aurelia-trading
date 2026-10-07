import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts import promote_r100_certification_evidence


class R100CertificationPromotionTests(unittest.TestCase):
    def _base_state_and_report(self):
        manifest = {
            "experiment_id": "R100-PROSPECTIVE-TEST",
            "strategy_version": "0.2.0",
            "strategy_id": "R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0",
            "started_at_utc": "2026-10-01T00:00:00Z",
            "campaign_end_at_utc": "2026-10-08T00:00:00Z",
            "oos_start_at_utc": "2026-10-02T00:00:00Z",
            "sealed": False,
            "code_commit": "test-commit",
            "config_hash": "test-config",
        }
        observations = [
            {
                "signal_id": f"s{i}",
                "signal_timestamp_utc": "2026-10-03T00:00:00Z",
                "direction": "CALL",
                "raw_return": 0.01,
                "outcome": 1,
                "probability": 0.55 + (i % 3) * 0.10,
            }
            for i in range(120)
        ]
        state = {
            "schema": "aurelia.r100.prospective_oos.v1",
            "manifest": manifest,
            "observations": observations,
            "quote_observations": [],
            "last_run_completed_at_utc": "2026-10-07T00:00:00Z",
        }
        report = {
            "experiment_id": manifest["experiment_id"],
            "strategy_version": manifest["strategy_version"],
            "campaign_complete": False,
            "retuning_after_seal": False,
            "multiple_testing": {"status": "ACCOUNTED"},
            "min_trades_per_strategy_symbol_regime": 120,
            "oos_observations": 120,
            "archive_hash": "archive-hash",
            "probability": {
                "calibration_status": "VALIDATED_RESEARCH",
                "qualifying_reliability_buckets": 3,
                "max_reliability_gap": 0.02,
                "drift_detected": False,
                "sample_count": 120,
                "brier_score": 0.12,
                "log_loss": 0.35,
                "reliability_buckets": [],
            },
        }
        return state, report

    def test_incomplete_campaign_never_promotes_oos(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                state, report = self._base_state_and_report()
                Path(".research_state").mkdir()
                Path(".research_state/aurelia_r100_state.json").write_text(json.dumps(state))
                Path(".research_state/aurelia_r100_report.json").write_text(json.dumps(report))
                self.assertEqual(promote_r100_certification_evidence.main(), 0)
                self.assertFalse(Path("evidence/prospective_oos.json").exists())
            finally:
                os.chdir(cwd)

    def test_sealed_validated_campaign_promotes_oos_and_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                state, report = self._base_state_and_report()
                state["manifest"]["sealed"] = True
                report["campaign_complete"] = True
                Path(".research_state").mkdir()
                Path(".research_state/aurelia_r100_state.json").write_text(json.dumps(state))
                Path(".research_state/aurelia_r100_report.json").write_text(json.dumps(report))
                self.assertEqual(promote_r100_certification_evidence.main(), 0)
                self.assertTrue(Path("evidence/prospective_oos.json").exists())
                self.assertTrue(Path("evidence/calibration.json").exists())
                oos = json.loads(Path("evidence/prospective_oos.json").read_text())
                cal = json.loads(Path("evidence/calibration.json").read_text())
                self.assertEqual(oos["min_trades_per_strategy_symbol_regime"], 120)
                self.assertTrue(oos["sealed_prospective_data"])
                self.assertTrue(cal["calibration_validated"])
                self.assertEqual(oos["record_hash"], promote_r100_certification_evidence.hash_payload({k:v for k,v in oos.items() if k != "record_hash"}))
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
