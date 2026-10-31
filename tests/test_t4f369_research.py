"""Unit tests for T4F x 369 research utilities."""
import unittest
from datetime import datetime, timedelta, timezone

from research.labs.t4f369_research import (
    Candle,
    ConfirmedPivot,
    detect_confirmed_pivots,
    digital_root_from_price,
    performance_metrics,
    project_369_levels,
    scan_level_touches,
    validate_candles,
)


def bars(prices):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(start + timedelta(minutes=i), p, p + 1, p - 1, p + 0.25)
        for i, p in enumerate(prices)
    ]


class T4F369Tests(unittest.TestCase):
    def test_integer_part_selects_step_but_full_price_projects(self):
        projection = project_369_levels(
            4217.395, instrument="XAUUSD", direction="bearish"
        )
        self.assertEqual(digital_root_from_price(4217.395), (4217, 14, 5))
        self.assertEqual(projection.base_step, 15.0)
        self.assertAlmostEqual(projection.levels[0], 4202.395, places=8)
        self.assertAlmostEqual(projection.levels[3], 4157.395, places=8)

    def test_nq_scale_and_es_warning(self):
        nq = project_369_levels(4217.395, instrument="NQ", direction="bearish")
        es = project_369_levels(4217.395, instrument="ES", direction="bullish")
        self.assertEqual(nq.scaled_step, 150.0)
        self.assertTrue(es.es_scaling_unverified)
        self.assertEqual(es.scaled_step, 15.0)

    def test_invalid_reference_rejected(self):
        for price in (0, -1, 0.75, float("nan"), float("inf")):
            with self.subTest(price=price), self.assertRaises(ValueError):
                project_369_levels(price, instrument="XAUUSD", direction="bullish")

    def test_candle_validation_counts_missing_bars(self):
        seq = bars([100, 101, 102])
        # Remove the middle timestamp: two intervals apart means one missing bar.
        seq = [seq[0], seq[2]]
        quality = validate_candles(seq, interval_seconds=60)
        self.assertEqual(quality.missing_intervals, 1)
        self.assertEqual(quality.status, "FAIL_CLOSED")

    def test_off_grid_timestamp_delta_fails_closed(self):
        seq = bars([100, 101])
        seq[1] = Candle(seq[0].timestamp + timedelta(seconds=90), 101, 102, 100, 101.25)
        quality = validate_candles(seq, interval_seconds=60)
        self.assertEqual(quality.status, "FAIL_CLOSED")
        self.assertEqual(quality.missing_intervals, 1)

    def test_pivot_detector_rejects_gap_input(self):
        seq = bars([10, 11, 15, 12, 11, 10, 9])
        seq[3] = Candle(seq[2].timestamp + timedelta(minutes=2), 12, 13, 11, 12.25)
        with self.assertRaisesRegex(ValueError, "PIVOT_INPUT_QUALITY_FAILED_CLOSED"):
            detect_confirmed_pivots(seq, left_bars=2, right_bars=2)

    def test_pivot_not_available_until_right_side_closes(self):
        seq = bars([10, 11, 15, 12, 11, 10, 9])
        pivots = detect_confirmed_pivots(seq, left_bars=2, right_bars=2)
        high = next(p for p in pivots if p.kind == "HIGH")
        self.assertEqual(high.pivot_index, 2)
        self.assertEqual(high.confirmed_at_index, 4)

    def test_touch_scan_starts_after_confirmation(self):
        seq = bars([10, 11, 15, 12, 11, 10, 9, 8, 7, 6])
        pivot = ConfirmedPivot("HIGH", 2, 4, 16.0)
        projection = project_369_levels(
            16.0, instrument="XAUUSD", direction="bearish"
        )
        touches = scan_level_touches(
            seq, pivot=pivot, projection=projection,
            max_bars_after_confirmation=5, tolerance_fraction=0.0,
        )
        self.assertTrue(all(t.first_touch_index > 4 for t in touches))
        wrong_reference = project_369_levels(
            17.0, instrument="XAUUSD", direction="bearish"
        )
        with self.assertRaisesRegex(ValueError, "PIVOT_PROJECTION_REFERENCE_MISMATCH"):
            scan_level_touches(
                seq, pivot=pivot, projection=wrong_reference,
                max_bars_after_confirmation=5,
            )

    def test_metrics_require_minimum_sample_and_use_net_values(self):
        self.assertEqual(
            performance_metrics([{"pnl_net": 1, "r_multiple": 1}] * 10)["status"],
            "INSUFFICIENT_SAMPLE",
        )
        rows = [{"pnl_net": 2.0, "risk_usd": 2.0, "r_multiple": 1.0}] * 20
        rows += [{"pnl_net": -1.0, "risk_usd": 2.0, "r_multiple": -0.5}] * 10
        metrics = performance_metrics(rows)
        self.assertEqual(metrics["status"], "DESCRIPTIVE_ONLY")
        self.assertAlmostEqual(metrics["profit_factor"], 4.0)
        self.assertAlmostEqual(metrics["expectancy_r"], 0.5)
        inconsistent = [{"pnl_net": 2.0, "risk_usd": 1.0, "r_multiple": 1.0}] * 30
        with self.assertRaisesRegex(ValueError, "R_MULTIPLE_DOES_NOT_MATCH_NET_PNL_OVER_RISK"):
            performance_metrics(inconsistent)


if __name__ == "__main__":
    unittest.main()
