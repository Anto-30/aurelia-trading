from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime

from research.labs.walk_forward_splits import (
    monthly_walk_forward_splits,
    validate_split,
)


class MonthlyWalkForwardSplitTests(unittest.TestCase):
    def test_rolls_three_month_train_and_one_month_oos(self) -> None:
        splits = monthly_walk_forward_splits("2026-01", "2026-07")
        self.assertEqual(len(splits), 3)
        self.assertEqual(
            [split.split_id for split in splits],
            [
                "2026-01_IS3M_OOS2026-04",
                "2026-02_IS3M_OOS2026-05",
                "2026-03_IS3M_OOS2026-06",
            ],
        )
        for split in splits:
            validate_split(split)
            self.assertEqual(split.nominal_in_sample_months, 3)
            self.assertEqual(split.out_of_sample_months, 1)

    def test_purge_interval_is_excluded_before_oos(self) -> None:
        split = monthly_walk_forward_splits(
            "2026-01", "2026-05", purge_days=7
        )[0]
        self.assertEqual(split.train_end_exclusive_utc, split.purge_start_utc)
        self.assertEqual(split.purge_end_exclusive_utc, split.oos_start_utc)
        train_end = datetime.fromisoformat(
            split.train_end_exclusive_utc.replace("Z", "+00:00")
        )
        oos_start = datetime.fromisoformat(
            split.oos_start_utc.replace("Z", "+00:00")
        )
        self.assertEqual((oos_start - train_end).days, 7)
        validate_split(split)

    def test_incomplete_trailing_oos_window_is_omitted(self) -> None:
        self.assertEqual(monthly_walk_forward_splits("2026-01", "2026-04"), [])
        self.assertEqual(len(monthly_walk_forward_splits("2026-01", "2026-05")), 1)

    def test_invalid_month_or_window_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "MONTH_MUST_USE_YYYY_MM"):
            monthly_walk_forward_splits("2026-1", "2026-07")
        with self.assertRaisesRegex(ValueError, "END_MONTH_MUST_FOLLOW_START_MONTH"):
            monthly_walk_forward_splits("2026-05", "2026-04")
        with self.assertRaisesRegex(ValueError, "PURGE_DAYS_MUST_NOT_BE_NEGATIVE"):
            monthly_walk_forward_splits("2026-01", "2026-05", purge_days=-1)

    def test_overlapping_or_reversed_windows_are_rejected(self) -> None:
        split = monthly_walk_forward_splits("2026-01", "2026-05")[0]
        invalid = replace(split, oos_start_utc=split.train_start_utc)
        with self.assertRaisesRegex(
            ValueError, "WALK_FORWARD_WINDOWS_OVERLAP_OR_REVERSED"
        ):
            validate_split(invalid)

    def test_overlapping_oos_windows_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "OUT_OF_SAMPLE_WINDOWS_MUST_NOT_OVERLAP"):
            monthly_walk_forward_splits(
                "2026-01", "2026-08", out_of_sample_months=2, step_months=1
            )

    def test_non_default_step_rolls_by_two_months(self) -> None:
        splits = monthly_walk_forward_splits(
            "2026-01", "2026-08", step_months=2
        )
        self.assertEqual(len(splits), 2)
        self.assertEqual(splits[0].train_start_utc, "2026-01-01T00:00:00Z")
        self.assertEqual(splits[1].train_start_utc, "2026-03-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
