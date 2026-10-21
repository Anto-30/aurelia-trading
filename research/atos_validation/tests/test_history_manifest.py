from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from research.atos_validation.deriv_data import persist_history
from scripts.verify_deriv_history_manifest import verify_history


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.to_datetime([60, 120, 180], unit="s", utc=True),
        "epoch": [60, 120, 180],
        "open": [100.0, 101.0, 102.0],
        "high": [102.0, 103.0, 104.0],
        "low": [99.0, 100.0, 101.0],
        "close": [101.0, 102.0, 103.0],
        "volume": [np.nan, np.nan, np.nan],
    })


class HistoryManifestTests(unittest.TestCase):
    def test_valid_data_and_manifest_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv = Path(tmp) / "sample.csv"
            persist_history(sample_frame(), csv, symbol="R_100", granularity=60, start_epoch=60, end_epoch=180)
            report = verify_history(csv)
            self.assertTrue(report["verified"])
            self.assertEqual(report["bar_count"], 3)
            self.assertEqual(report["symbol"], "R_100")
            self.assertEqual(len(report["data_sha256"]), 64)
            self.assertEqual(len(report["manifest_sha256"]), 64)

    def test_csv_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv = Path(tmp) / "sample.csv"
            persist_history(sample_frame(), csv, symbol="R_100", granularity=60, start_epoch=60, end_epoch=180)
            csv.write_text(csv.read_text(encoding="utf-8").replace("101.0", "111.0"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CSV SHA-256 mismatch"):
                verify_history(csv)

    def test_manifest_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv = Path(tmp) / "sample.csv"
            persist_history(sample_frame(), csv, symbol="R_100", granularity=60, start_epoch=60, end_epoch=180)
            manifest_path = csv.with_suffix(".csv.manifest.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["coverage_complete"] = False
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest SHA-256 mismatch"):
                verify_history(csv)

    def test_missing_candle_is_detected_even_with_rehashed_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv = Path(tmp) / "sample.csv"
            persist_history(sample_frame(), csv, symbol="R_100", granularity=60, start_epoch=60, end_epoch=180)
            frame = pd.read_csv(csv).iloc[:2]
            frame.to_csv(csv, index=False)
            manifest_path = csv.with_suffix(".csv.manifest.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            import hashlib
            manifest["data_sha256"] = hashlib.sha256(csv.read_bytes()).hexdigest()
            unsigned = {key: val for key, val in manifest.items() if key != "manifest_sha256"}
            canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            manifest["manifest_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly cover"):
                verify_history(csv)


if __name__ == "__main__":
    unittest.main()
