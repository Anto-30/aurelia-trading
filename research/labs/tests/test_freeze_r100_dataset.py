import csv
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.labs.freeze_r100_dataset import (
    aggregate_15m, freeze_r100_dual_resolution, read_validate_1m_csv, verify_manifest,
)


def write_csv(path: Path, times, *, bad_row=None):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["datetime", "open", "high", "low", "close"])
        writer.writeheader()
        for i, stamp in enumerate(times):
            row = {"datetime": stamp, "open": 100+i, "high": 102+i,
                   "low": 99+i, "close": 101+i}
            if bad_row == i:
                row["high"] = 50
            writer.writerow(row)


class FreezeR100DatasetTests(unittest.TestCase):
    def test_freezes_valid_1m_and_aggregates_15m_with_hash_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.csv"
            start = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
            times = [(start + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
                     for i in range(45)]
            write_csv(raw, times)
            frozen = root / "frozen"
            manifest = freeze_r100_dual_resolution(
                str(raw), source="test fixture", description="unit test only",
                timestamp_role="close", manifest_dir=str(frozen),
            )
            self.assertEqual(manifest["status"], "SEALED")
            self.assertFalse(manifest["qualification_allowed"])
            self.assertEqual(manifest["datasets"]["1m"]["row_count"], 45)
            self.assertEqual(manifest["datasets"]["15m"]["row_count"], 3)
            self.assertEqual(verify_manifest(frozen / "r100_dual_resolution_manifest.json")["status"], "SEALED")
            self.assertEqual(raw.stat().st_mode & 0o222, raw.stat().st_mode & 0o222)
            self.assertEqual((frozen / "r100_1m.csv").stat().st_mode & 0o222, 0)
            self.assertEqual((frozen / "r100_15m.csv").stat().st_mode & 0o222, 0)

    def test_timestamp_role_open_shifts_to_candle_close(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "raw.csv"
            start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
            times = [(start + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
                     for i in range(30)]
            write_csv(raw, times)
            rows = read_validate_1m_csv(raw, timestamp_role="open")
            self.assertEqual(rows[0]["datetime"], "2026-01-01T00:01:00Z")

    def test_rejects_missing_file_and_never_creates_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "frozen"
            with self.assertRaisesRegex(FileNotFoundError, "DATASET_NOT_FOUND"):
                freeze_r100_dual_resolution(
                    str(Path(directory) / "missing.csv"), source="fixture",
                    description="missing", timestamp_role="close", manifest_dir=str(output),
                )
            self.assertFalse((output / "r100_dual_resolution_manifest.json").exists())

    def test_rejects_bad_ohlc_and_minute_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            start = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
            times = [(start + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
                     for i in range(30)]
            bad = root / "bad.csv"
            write_csv(bad, times, bad_row=4)
            with self.assertRaisesRegex(ValueError, "HIGH_BELOW_OPEN_OR_CLOSE"):
                read_validate_1m_csv(bad)
            missing_time_csv = root / "gap.csv"
            write_csv(missing_time_csv, [value for index, value in enumerate(times) if index != 8])
            with self.assertRaisesRegex(ValueError, "ONE_MINUTE_GAP_OR_DUPLICATE"):
                read_validate_1m_csv(missing_time_csv)

    def test_aggregation_drops_incomplete_edge_bucket(self):
        start = datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc)
        rows = []
        for index in range(29):
            stamp = start + timedelta(minutes=index)
            rows.append({
                "datetime": stamp.isoformat().replace("+00:00", "Z"),
                "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0,
            })
        output, dropped = aggregate_15m(rows)
        self.assertEqual(len(output), 1)
        self.assertGreaterEqual(dropped, 1)


if __name__ == "__main__":
    unittest.main()
