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


from research.labs.deterministic_intraday_strategies import MSNRConfig, RegimeConfig, StrategyBar
from research.labs.three_sixty_nine_msnr import (
    ProtectedSwing,
    ThreeSixtyNineMSNRConfig,
    evaluate_369_msnr_candidate,
)


def _candidate_fixture(*, start_minute=40, entry_open=101.0, signal_close=101.1):
    ny = ZoneInfo("America/New_York")
    rows = [
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 100.5, 98.0, 99.0),
        (99.0, 101.0, 98.5, 100.0),
        (100.0, 100.7, 99.0, 100.0),
        (100.0, 101.15, 97.0, signal_close),
        (entry_open, entry_open + 1.0, entry_open - 1.0, entry_open + 0.5),
    ]
    bars = []
    for index, (opened, high, low, close) in enumerate(rows):
        local = datetime(2026, 1, 15, 9, start_minute + index, tzinfo=ny)
        stamp = local.astimezone(timezone.utc).isoformat()
        bars.append(StrategyBar(stamp, opened, high, low, close))
    swing = ProtectedSwing(
        direction="LOW",
        anchor_price=100.0,
        pivot_timestamp_utc=bars[1].timestamp_utc,
        confirmation_timestamp_utc=bars[4].timestamp_utc,
        source_rule_id="test-confirmed-swing-v1",
        last_input_bar_timestamp_utc=bars[3].timestamp_utc,
    )
    config = ThreeSixtyNineMSNRConfig(
        instrument_id="TEST_SYMBOL",
        tick_size=0.1,
        price_scale=1.0,
        instrument_mapping_verified=True,
        msnr_config=MSNRConfig(
            lookback_bars=3,
            tick_size=0.1,
            min_sweep_ticks=2.0,
            max_reclaim_bars=2,
        ),
        regime_config=RegimeConfig(
            lookback_bars=2,
            trend_efficiency_min=0.35,
            high_volatility_pct=10.0,
        ),
    )
    return bars, swing, config


class ThreeSixtyNineCandidateTests(unittest.TestCase):
    def test_candidate_uses_confirmed_close_and_next_bar_open(self):
        bars, swing, config = _candidate_fixture()
        candidate = evaluate_369_msnr_candidate(
            bars, timeframe_seconds=60, protected_swing=swing, config=config
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.direction, "LONG")
        self.assertEqual(candidate.signal_close_timestamp_utc, (datetime.fromisoformat(bars[4].timestamp_utc) + timedelta(minutes=1)).isoformat())
        self.assertEqual(candidate.entry_timestamp_utc, bars[5].timestamp_utc)
        self.assertAlmostEqual(candidate.entry_price, bars[5].open)
        self.assertEqual(candidate.entry_price, 101.0)
        self.assertFalse(candidate.capital_authority)
        self.assertFalse(candidate.order_submission_permitted)

    def test_candidate_rejects_close_at_1000_new_york(self):
        bars, swing, config = _candidate_fixture(start_minute=55)
        self.assertIsNone(evaluate_369_msnr_candidate(
            bars, timeframe_seconds=60, protected_swing=swing, config=config
        ))

    def test_candidate_requires_a_following_bar(self):
        bars, swing, config = _candidate_fixture()
        self.assertIsNone(evaluate_369_msnr_candidate(
            bars[:-1], timeframe_seconds=60, protected_swing=swing, config=config
        ))

    def test_candidate_rejects_unconfirmed_or_future_swing_provenance(self):
        bars, swing, config = _candidate_fixture()
        future_swing = ProtectedSwing(
            direction=swing.direction,
            anchor_price=swing.anchor_price,
            pivot_timestamp_utc=swing.pivot_timestamp_utc,
            confirmation_timestamp_utc=(datetime.fromisoformat(bars[4].timestamp_utc) + timedelta(minutes=2)).isoformat(),
            source_rule_id=swing.source_rule_id,
            last_input_bar_timestamp_utc=swing.last_input_bar_timestamp_utc,
        )
        self.assertIsNone(evaluate_369_msnr_candidate(
            bars, timeframe_seconds=60, protected_swing=future_swing, config=config
        ))
        incomplete = ProtectedSwing(
            direction=swing.direction,
            anchor_price=swing.anchor_price,
            pivot_timestamp_utc=swing.pivot_timestamp_utc,
            confirmation_timestamp_utc=swing.confirmation_timestamp_utc,
            source_rule_id="",
            last_input_bar_timestamp_utc=swing.last_input_bar_timestamp_utc,
        )
        self.assertIsNone(evaluate_369_msnr_candidate(
            bars, timeframe_seconds=60, protected_swing=incomplete, config=config
        ))

    def test_candidate_rejects_swing_direction_mismatch(self):
        bars, swing, config = _candidate_fixture()
        wrong_side = ProtectedSwing(
            direction="HIGH",
            anchor_price=swing.anchor_price,
            pivot_timestamp_utc=swing.pivot_timestamp_utc,
            confirmation_timestamp_utc=swing.confirmation_timestamp_utc,
            source_rule_id=swing.source_rule_id,
            last_input_bar_timestamp_utc=swing.last_input_bar_timestamp_utc,
        )
        self.assertIsNone(evaluate_369_msnr_candidate(
            bars, timeframe_seconds=60, protected_swing=wrong_side, config=config
        ))

    def test_candidate_requires_verified_instrument_mapping(self):
        from dataclasses import replace
        bars, swing, config = _candidate_fixture()
        self.assertIsNone(evaluate_369_msnr_candidate(
            bars, timeframe_seconds=60, protected_swing=swing,
            config=replace(config, instrument_mapping_verified=False),
        ))

    def test_candidate_rejects_if_no_369_target_reaches_three_gross_r(self):
        bars, swing, config = _candidate_fixture(entry_open=110.0)
        self.assertIsNone(evaluate_369_msnr_candidate(
            bars, timeframe_seconds=60, protected_swing=swing, config=config
        ))

    def test_displacement_variant_requires_body_over_prior_three_mean(self):
        from dataclasses import replace
        bars, swing, config = _candidate_fixture(signal_close=101.1)
        candidate = evaluate_369_msnr_candidate(
            bars, timeframe_seconds=60, protected_swing=swing,
            config=replace(config, displacement_filter=True),
        )
        self.assertIsNotNone(candidate)
        self.assertIn("DISPLACEMENT", candidate.variant_id)

        weak_bars, weak_swing, weak_config = _candidate_fixture(signal_close=100.9)
        self.assertIsNone(evaluate_369_msnr_candidate(
            weak_bars, timeframe_seconds=60, protected_swing=weak_swing,
            config=replace(weak_config, displacement_filter=True),
        ))

    def test_next_bar_high_low_close_do_not_change_entry_or_signal(self):
        from dataclasses import replace
        bars, swing, config = _candidate_fixture()
        first = evaluate_369_msnr_candidate(
            bars, timeframe_seconds=60, protected_swing=swing, config=config
        )
        altered_next = replace(bars[5], high=1000.0, low=1.0, close=999.0)
        second = evaluate_369_msnr_candidate(
            bars[:5] + [altered_next], timeframe_seconds=60,
            protected_swing=swing, config=config
        )
        self.assertEqual(first.entry_price, second.entry_price)
        self.assertEqual(first.target_price, second.target_price)
        self.assertEqual(first.signal_close_timestamp_utc, second.signal_close_timestamp_utc)
