from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from research.labs.run_smc_baseline import main


class ATOSSMCBaselineCliTests(unittest.TestCase):
    def test_csv_baseline_writes_json_and_ohlc_evidence_without_live_authority(self):
        index = pd.date_range("2026-11-10T13:00:00Z", periods=60, freq="min")
        prices = [100.0] * len(index)
        source = pd.DataFrame({
            "open": prices,
            "high": [100.1] * len(index),
            "low": [99.9] * len(index),
            "close": prices,
        }, index=index)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "r100.csv"
            output_dir = root / "output"
            source.to_csv(csv_path, index_label="timestamp_utc")
            args = [
                "run_smc_baseline",
                "--provider", "csv",
                "--symbol", "R_100",
                "--input-csv", str(csv_path),
                "--start", index[0].isoformat(),
                "--end", index[-1].isoformat(),
                "--tick-size", "0.01",
                "--tick-size-source", "synthetic-unit-test",
                "--minimum-coverage-pct", "100",
                "--output-dir", str(output_dir),
            ]
            with patch.object(sys, "argv", args):
                self.assertEqual(main(), 0)
            reports = list(output_dir.glob("*.json"))
            candles = list(output_dir.glob("*.csv"))
            self.assertEqual(len(reports), 1)
            self.assertEqual(len(candles), 1)
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertEqual(report["symbol"], "R_100")
            self.assertEqual(report["data_quality"]["coverage_pct"], 100.0)
            self.assertFalse(report["capital_authority"])
            self.assertFalse(report["order_submission_permitted"])
            self.assertEqual(report["live_execution"], "BLOCKED")
            self.assertFalse(report["input_assumptions"]["costs_user_asserted_verified"])
            self.assertFalse(report["input_assumptions"]["point_value_user_asserted_verified"])


if __name__ == "__main__":
    unittest.main()
