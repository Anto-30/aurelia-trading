import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.labs.import_deriv_mt5_ticks import import_mt5_ticks


class DerivMT5TickImportTests(unittest.TestCase):
    def _write_ticks(self, path: Path, minutes: int = 15) -> None:
        start = datetime(2022, 10, 21, tzinfo=timezone.utc)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Time", "Bid", "Ask", "Last", "Volume", "Flags"])
            for i in range(minutes):
                stamp = start + timedelta(minutes=i, seconds=5)
                writer.writerow([
                    stamp.strftime("%Y.%m.%d %H:%M:%S.%f")[:-3],
                    f"{10000 + i * 0.1:.2f}",
                    f"{10000 + i * 0.1 + 0.05:.2f}",
                    "",
                    "1",
                    "0",
                ])

    def test_imports_full_contiguous_m1_and_m15_with_explicit_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "ticks.csv"
            output = root / "out"
            self._write_ticks(source, 15)
            result = import_mt5_ticks(
                input_path=source,
                output_dir=output,
                source_symbol="Volatility 100 Index",
                canonical_symbol="R_100",
                source_timezone="UTC",
                mapping_confirmed=True,
                start_epoch=1666310400,
                end_epoch=1666311300,
            )
            self.assertEqual(result["status"], "RESEARCH_IMPORT_READY")
            self.assertEqual(result["tick_count"], 15)
            self.assertEqual(result["m1_bar_count"], 15)
            self.assertEqual(result["m15_bar_count"], 1)
            self.assertEqual(result["m1_gap_count"], 0)
            self.assertEqual(result["m15_gap_count"], 0)
            self.assertFalse(result["feed_equivalence_to_deriv_options_verified"])
            self.assertFalse(result["strategy_validation_eligible"])
            self.assertTrue((output / "manifest.json").is_file())
            self.assertTrue((output / "R100_M1.csv").is_file())
            self.assertTrue((output / "R100_M15.csv").is_file())

    def test_unconfirmed_symbol_mapping_blocks_import_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "ticks.csv"
            self._write_ticks(source, 15)
            result = import_mt5_ticks(
                input_path=source,
                output_dir=root / "out",
                source_symbol="Volatility 100 Index",
                source_timezone="UTC",
                mapping_confirmed=False,
                start_epoch=1666310400,
                end_epoch=1666311300,
            )
            self.assertEqual(result["status"], "BLOCKED_IMPORT_QUALITY_OR_MAPPING")
            self.assertIn("SYMBOL_MAPPING_NOT_OPERATOR_CONFIRMED", result["blockers"])

    def test_missing_m1_minute_is_reported_not_interpolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "ticks.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Time", "Bid", "Ask"])
                writer.writerow(["2022.10.21 00:00:05.000", "10000", "10000.05"])
                writer.writerow(["2022.10.21 00:02:05.000", "10001", "10001.05"])
            result = import_mt5_ticks(
                input_path=source,
                output_dir=root / "out",
                source_symbol="R_100",
                source_timezone="UTC",
                mapping_confirmed=True,
                start_epoch=1666310400,
                end_epoch=1666310580,
            )
            self.assertEqual(result["status"], "BLOCKED_IMPORT_QUALITY_OR_MAPPING")
            self.assertEqual(result["m1_gap_count"], 1)
            self.assertFalse(result["gap_interpolation_performed"])

    def test_dst_ambiguous_local_timestamp_fails_closed(self):
        from research.labs.import_deriv_mt5_ticks import _parse_timestamp
        with self.assertRaisesRegex(
            ValueError, "SOURCE_TIMEZONE_AMBIGUOUS_LOCAL_TIME_UNRESOLVED"
        ):
            _parse_timestamp(
                {"time": "2022-10-30 03:30:00.000"},
                "Europe/Helsinki",
            )

    def test_dst_ambiguous_local_timestamp_uses_monotonic_utc_sequence(self):
        from research.labs.import_deriv_mt5_ticks import _parse_timestamp
        previous = datetime(2022, 10, 30, 0, 59, 0, tzinfo=timezone.utc)
        parsed, resolved = _parse_timestamp(
            {"time": "2022-10-30 03:00:00.000"},
            "Europe/Helsinki",
            previous_utc=previous,
        )
        self.assertEqual(parsed, datetime(2022, 10, 30, 1, 0, 0, tzinfo=timezone.utc))
        self.assertTrue(resolved)

    def test_dst_nonexistent_local_timestamp_fails_closed(self):
        from research.labs.import_deriv_mt5_ticks import _parse_timestamp
        with self.assertRaisesRegex(ValueError, "SOURCE_TIMEZONE_NONEXISTENT_LOCAL_TIME"):
            _parse_timestamp(
                {"time": "2022-03-27 03:30:00.000"},
                "Europe/Helsinki",
            )

    def test_naive_timestamps_require_explicit_timezone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "ticks.csv"
            self._write_ticks(source, 15)
            with self.assertRaisesRegex(
                ValueError,
                "SOURCE_TIMEZONE_REQUIRED_FOR_NAIVE_MT5_TIMESTAMPS",
            ):
                import_mt5_ticks(
                    input_path=source,
                    output_dir=root / "out",
                    source_symbol="R_100",
                    source_timezone=None,
                    mapping_confirmed=True,
                    start_epoch=1666310400,
                    end_epoch=1666311300,
                )


if __name__ == "__main__":
    unittest.main()
