from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from research.labs.three_sixty_nine_msnr import (
    bar_close_timestamp,
    build_369_levels,
    digital_root,
    level_step_for_root,
    signal_close_is_eligible,
)


class ThreeSixtyNineArithmeticTests(unittest.TestCase):
    def test_digital_root_and_step_mapping_for_roots_one_to_nine(self):
        expected = {
            1: 12, 2: 15, 3: 18, 4: 12, 5: 15,
            6: 18, 7: 12, 8: 15, 9: 18,
        }
        for value, step in expected.items():
            with self.subTest(value=value):
                self.assertEqual(digital_root(value), value)
                self.assertEqual(level_step_for_root(value), step)

    def test_digital_root_reduces_multiple_digits(self):
        self.assertEqual(digital_root(4217), 5)
        self.assertEqual(level_step_for_root(digital_root(4217)), 15)

    def test_digital_root_rejects_non_integer_or_non_positive_values(self):
        for value in (0, -1, 12.5, True, "4217", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    digital_root(value)

    def test_level_mapping_rejects_invalid_roots(self):
        for root in (0, 10, -1, 2.5, True):
            with self.subTest(root=root):
                with self.assertRaises(ValueError):
                    level_step_for_root(root)

    def test_short_levels_descend_and_preserve_fractional_anchor(self):
        levels = build_369_levels(4217.395, direction="SHORT")
        self.assertEqual(len(levels), 4)
        for actual, expected in zip(
            levels, (4202.395, 4187.395, 4172.395, 4157.395)
        ):
            self.assertAlmostEqual(actual, expected, places=9)

    def test_long_levels_ascend_and_preserve_fractional_anchor(self):
        levels = build_369_levels(4217.395, direction="LONG", level_count=5)
        self.assertEqual(len(levels), 5)
        for actual, expected in zip(
            levels, (4232.395, 4247.395, 4262.395, 4277.395, 4292.395)
        ):
            self.assertAlmostEqual(actual, expected, places=9)

    def test_level_mapping_rejects_invalid_price_direction_and_count(self):
        invalid = (
            (0, "LONG", 4),
            (-10.0, "LONG", 4),
            (float("nan"), "LONG", 4),
            (4217.395, "SIDEWAYS", 4),
            (4217.395, "LONG", 3),
        )
        for anchor, direction, count in invalid:
            with self.subTest(anchor=anchor, direction=direction, count=count):
                with self.assertRaises(ValueError):
                    build_369_levels(anchor, direction=direction, level_count=count)

    def test_signal_window_is_half_open_in_new_york_time(self):
        ny = ZoneInfo("America/New_York")
        self.assertTrue(signal_close_is_eligible(datetime(2026, 1, 15, 9, 45, tzinfo=ny)))
        self.assertTrue(signal_close_is_eligible(datetime(2026, 1, 15, 9, 59, 59, 999999, tzinfo=ny)))
        self.assertFalse(signal_close_is_eligible(datetime(2026, 1, 15, 10, 0, tzinfo=ny)))
        self.assertFalse(signal_close_is_eligible(datetime(2026, 1, 15, 9, 44, 59, tzinfo=ny)))

    def test_signal_window_converts_utc_correctly_across_dst(self):
        # 09:45 New York is 13:45 UTC during EDT and 14:45 UTC during EST.
        self.assertTrue(signal_close_is_eligible(datetime(2026, 3, 9, 13, 45, tzinfo=timezone.utc)))
        self.assertTrue(signal_close_is_eligible(datetime(2026, 11, 2, 14, 45, tzinfo=timezone.utc)))
        self.assertFalse(signal_close_is_eligible(datetime(2026, 3, 9, 14, 45, tzinfo=timezone.utc)))
        self.assertFalse(signal_close_is_eligible(datetime(2026, 11, 2, 13, 45, tzinfo=timezone.utc)))

    def test_naive_signal_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            signal_close_is_eligible(datetime(2026, 1, 15, 9, 45))

    def test_bar_close_timestamp_uses_declared_timeframe(self):
        opened = datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc)
        self.assertEqual(
            bar_close_timestamp(opened, 900),
            opened + timedelta(minutes=15),
        )

    def test_bar_close_timestamp_rejects_naive_time_and_invalid_duration(self):
        with self.assertRaises(ValueError):
            bar_close_timestamp(datetime(2026, 1, 15, 14, 30), 900)
        for seconds in (0, -1, 1.5, True):
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):
                    bar_close_timestamp(datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc), seconds)


if __name__ == "__main__":
    unittest.main()
