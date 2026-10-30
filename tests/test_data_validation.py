"""Unit tests for fail-closed research data validation."""
import unittest

import pandas as pd

from research.labs.data_validation import ValidationConfig, validate_frame


def valid_frame(index=None):
    if index is None:
        index = pd.date_range("2026-01-05 13:00:00", periods=3, freq="min", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [101.0, 102.0, 103.0],
        },
        index=index,
    )


class DataValidationTests(unittest.TestCase):
    def test_valid_utc_frame_passes_and_hashes(self):
        result = validate_frame(valid_frame())
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.report["missing_bars"], 0)
        self.assertEqual(len(result.report["normalized_data_sha256"]), 64)

    def test_naive_timestamps_fail_without_source_timezone(self):
        frame = valid_frame(pd.date_range("2026-01-05 13:00", periods=3, freq="min"))
        result = validate_frame(frame)
        self.assertEqual(result.status, "FAIL")
        self.assertIn("NAIVE_TIMESTAMP_WITHOUT_SOURCE_TIMEZONE", result.report["errors"])

    def test_naive_timestamps_can_be_localized_when_source_is_declared(self):
        frame = valid_frame(pd.date_range("2026-01-05 13:00", periods=3, freq="min"))
        result = validate_frame(frame, ValidationConfig(source_timezone="UTC"))
        self.assertEqual(result.status, "PASS")

    def test_duplicate_timestamps_fail(self):
        index = pd.DatetimeIndex(
            ["2026-01-05T13:00:00Z", "2026-01-05T13:01:00Z", "2026-01-05T13:01:00Z"]
        )
        result = validate_frame(valid_frame(index))
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.report["duplicate_timestamps"], 2)

    def test_out_of_order_timestamps_fail_without_sorting(self):
        index = pd.DatetimeIndex(
            ["2026-01-05T13:00:00Z", "2026-01-05T13:02:00Z", "2026-01-05T13:01:00Z"]
        )
        result = validate_frame(valid_frame(index))
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.report["out_of_order_timestamps"], 1)

    def test_missing_bars_count_actual_absent_candles(self):
        index = pd.DatetimeIndex(
            ["2026-01-05T13:00:00Z", "2026-01-05T13:03:00Z", "2026-01-05T13:04:00Z"]
        )
        result = validate_frame(valid_frame(index))
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.report["missing_bars"], 2)

    def test_invalid_ohlc_fails(self):
        frame = valid_frame()
        frame.loc[frame.index[1], "high"] = 1.0
        result = validate_frame(frame)
        self.assertEqual(result.status, "FAIL")
        self.assertGreater(result.report["invalid_ohlc_rows"], 0)

    def test_non_numeric_ohlc_fails(self):
        frame = valid_frame()
        frame.loc[frame.index[0], "close"] = "bad"
        result = validate_frame(frame)
        self.assertEqual(result.status, "FAIL")
        self.assertGreater(result.report["non_finite_rows"], 0)

    def test_missing_required_column_fails(self):
        result = validate_frame(valid_frame().drop(columns=["volume"], errors="ignore").drop(columns=["low"]))
        self.assertEqual(result.status, "FAIL")
        self.assertFalse(result.report["schema_valid"])

    def test_dst_ambiguous_naive_local_time_fails(self):
        index = pd.date_range("2026-11-01 01:30", periods=3, freq="min")
        frame = valid_frame(index)
        result = validate_frame(frame, ValidationConfig(source_timezone="America/New_York"))
        self.assertEqual(result.status, "FAIL")
        self.assertIn("Cannot infer dst time", " ".join(result.report["errors"]))

if __name__ == "__main__":
    unittest.main()
