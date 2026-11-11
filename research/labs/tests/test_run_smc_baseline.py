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
    def test_legacy_baseline_cli_is_quarantined_without_writing_artifacts(self):
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
                with self.assertRaisesRegex(RuntimeError, "LEGACY_ATOS_SMC_BASELINE_QUARANTINED"):
                    main()
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
