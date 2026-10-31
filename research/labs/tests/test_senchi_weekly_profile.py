import unittest
from datetime import date, timedelta

from research.labs.senchi_weekly_profile import (
    DailyBar,
    build_completed_weekly_ranges,
    classify_monday_signals,
    measure_tuesday_outcomes,
    summarize_outcomes,
    validate_daily_bars,
    wilson_interval,
    validate_requested_range,
)


def bar(day, open_, high, low, close):
    return DailyBar(
        timestamp_utc=f"{day.isoformat()}T00:00:00Z",
        open=open_, high=high, low=low, close=close,
    )


def monday_signal(rows):
    return next(
        row for row in classify_monday_signals(rows)
        if row.monday_date == "2026-01-12"
    )


def base_previous_week():
    # 2026-01-05 Monday through 2026-01-11 Sunday; range is 90..110.
    start = date(2026, 1, 5)
    rows = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        rows.append(bar(
            day, 100.0,
            110.0 if offset == 2 else 105.0,
            90.0 if offset == 4 else 95.0,
            100.0,
        ))
    return rows


class SenchiWeeklyProfileTests(unittest.TestCase):
    def test_uses_previous_full_calendar_week_not_rolling_five_rows(self):
        rows = base_previous_week()
        ranges = build_completed_weekly_ranges(rows)
        weekly = ranges[date(2026, 1, 5)]
        self.assertEqual(weekly.high, 110.0)
        self.assertEqual(weekly.low, 90.0)
        self.assertEqual(weekly.source_bar_count, 7)

    def test_bullish_reversal_requires_low_sweep_and_close_inside(self):
        rows = base_previous_week()
        rows += [bar(date(2026, 1, 12), 94.0, 105.0, 88.0, 96.0)]
        signal = monday_signal(rows)
        self.assertEqual(signal.action, "BULLISH_REVERSAL")
        self.assertEqual(signal.target, 110.0)
        self.assertEqual(signal.invalidation, 88.0)

    def test_bearish_reversal_requires_high_sweep_and_close_inside(self):
        rows = base_previous_week()
        rows += [bar(date(2026, 1, 12), 106.0, 113.0, 95.0, 104.0)]
        signal = monday_signal(rows)
        self.assertEqual(signal.action, "BEARISH_REVERSAL")
        self.assertEqual(signal.target, 90.0)
        self.assertEqual(signal.invalidation, 113.0)

    def test_close_outside_range_is_expansion_even_if_opposite_wick_swept(self):
        rows = base_previous_week()
        rows += [bar(date(2026, 1, 12), 94.0, 114.0, 88.0, 112.0)]
        signal = monday_signal(rows)
        self.assertEqual(signal.action, "BULLISH_EXPANSION")
        self.assertIsNone(signal.target)

    def test_both_boundaries_swept_and_close_inside_is_complex(self):
        rows = base_previous_week()
        rows += [bar(date(2026, 1, 12), 100.0, 113.0, 88.0, 100.0)]
        signal = monday_signal(rows)
        self.assertEqual(signal.action, "COMPLEX_DUAL_SWEEP")

    def test_inside_day(self):
        rows = base_previous_week()
        rows += [bar(date(2026, 1, 12), 100.0, 105.0, 95.0, 101.0)]
        signal = monday_signal(rows)
        self.assertEqual(signal.action, "INSIDE")

    def test_incomplete_prior_week_is_not_used(self):
        rows = [
            bar(date(2026, 1, 9), 100.0, 105.0, 95.0, 100.0),
            bar(date(2026, 1, 10), 100.0, 105.0, 95.0, 100.0),
            bar(date(2026, 1, 11), 100.0, 105.0, 95.0, 100.0),
            bar(date(2026, 1, 12), 94.0, 105.0, 88.0, 96.0),
        ]
        signal = monday_signal(rows)
        self.assertEqual(signal.action, "NO_PRIOR_WEEK_RANGE")

    def test_tuesday_target_first_when_only_target_touched(self):
        rows = base_previous_week()
        rows += [bar(date(2026, 1, 12), 94.0, 105.0, 88.0, 96.0)]
        rows += [bar(date(2026, 1, 13), 97.0, 111.0, 92.0, 108.0)]
        signal = monday_signal(rows)
        outcome = measure_tuesday_outcomes(rows, [signal])[0]
        self.assertEqual(outcome.outcome, "TARGET_FIRST")

    def test_tuesday_stop_first_when_only_invalidation_touched(self):
        rows = base_previous_week()
        rows += [bar(date(2026, 1, 12), 94.0, 105.0, 88.0, 96.0)]
        rows += [bar(date(2026, 1, 13), 97.0, 108.0, 87.0, 90.0)]
        signal = monday_signal(rows)
        outcome = measure_tuesday_outcomes(rows, [signal])[0]
        self.assertEqual(outcome.outcome, "STOP_FIRST")

    def test_same_tuesday_candle_touching_both_sides_is_ambiguous(self):
        rows = base_previous_week()
        rows += [bar(date(2026, 1, 12), 94.0, 105.0, 88.0, 96.0)]
        rows += [bar(date(2026, 1, 13), 97.0, 111.0, 87.0, 100.0)]
        signal = monday_signal(rows)
        outcome = measure_tuesday_outcomes(rows, [signal])[0]
        self.assertEqual(outcome.outcome, "AMBIGUOUS_BOTH_TOUCHED")

    def test_open_gap_to_target(self):
        rows = base_previous_week()
        rows += [bar(date(2026, 1, 12), 94.0, 105.0, 88.0, 96.0)]
        rows += [bar(date(2026, 1, 13), 111.0, 113.0, 109.0, 112.0)]
        signal = monday_signal(rows)
        outcome = measure_tuesday_outcomes(rows, [signal])[0]
        self.assertEqual(outcome.outcome, "TARGET_GAP_AT_OPEN")

    def test_missing_tuesday_is_explicit(self):
        rows = base_previous_week()
        rows += [bar(date(2026, 1, 12), 94.0, 105.0, 88.0, 96.0)]
        signal = monday_signal(rows)
        outcome = measure_tuesday_outcomes(rows, [signal])[0]
        self.assertEqual(outcome.outcome, "MISSING_TUESDAY")

    def test_daily_gap_is_rejected(self):
        rows = base_previous_week()
        rows.append(bar(date(2026, 1, 12), 94.0, 105.0, 88.0, 96.0))
        rows.append(bar(date(2026, 1, 14), 97.0, 111.0, 92.0, 108.0))
        with self.assertRaisesRegex(ValueError, "DAILY_DATASET_HAS_GAP"):
            validate_daily_bars(rows)

    def test_out_of_order_daily_bars_are_rejected(self):
        rows = [
            bar(date(2026, 1, 2), 100.0, 105.0, 95.0, 100.0),
            bar(date(2026, 1, 1), 100.0, 105.0, 95.0, 100.0),
        ]
        with self.assertRaisesRegex(ValueError, "DAILY_BARS_NOT_STRICTLY_CHRONOLOGICAL"):
            validate_daily_bars(rows)

    def test_non_midnight_bar_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "UTC_MIDNIGHT_ALIGNED"):
            validate_daily_bars([
                DailyBar("2026-01-01T00:00:01Z", 1, 2, 0.5, 1.5)
            ])

    def test_ambiguous_touch_is_not_counted_as_a_win(self):
        rows = base_previous_week()
        rows += [bar(date(2026, 1, 12), 94.0, 105.0, 88.0, 96.0)]
        rows += [bar(date(2026, 1, 13), 97.0, 111.0, 87.0, 100.0)]
        signal = monday_signal(rows)
        outcome = measure_tuesday_outcomes(rows, [signal])[0]
        summary = summarize_outcomes([outcome])
        self.assertEqual(summary["target_first_count_including_open_gaps"], 0)
        self.assertEqual(summary["resolved_event_count"], 0)
        self.assertEqual(summary["target_touched_count_including_ambiguous"], 1)

    def test_exact_requested_date_range_passes(self):
        rows = base_previous_week() + [
            bar(date(2026, 1, 12), 94.0, 105.0, 88.0, 96.0)
        ]
        receipt = validate_requested_range(
            rows, start_date="2026-01-05", end_date="2026-01-12"
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["expected_calendar_days"], 8)

    def test_wrong_requested_date_range_is_rejected(self):
        rows = base_previous_week() + [
            bar(date(2026, 1, 12), 94.0, 105.0, 88.0, 96.0)
        ]
        with self.assertRaisesRegex(ValueError, "REQUESTED_DATE_RANGE_MISMATCH"):
            validate_requested_range(
                rows, start_date="2025-10-31", end_date="2026-10-31"
            )

    def test_wilson_interval(self):
        lower, upper = wilson_interval(50, 100)
        self.assertLess(lower, 0.5)
        self.assertGreater(upper, 0.5)


if __name__ == "__main__":
    unittest.main()
