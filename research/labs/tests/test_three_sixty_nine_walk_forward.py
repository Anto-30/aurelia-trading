from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from research.labs.three_sixty_nine_walk_forward import (
    WalkForwardConfig,
    build_rolling_windows,
    summarize_net_r,
)


class ThreeSixtyNineWalkForwardTests(unittest.TestCase):
    def test_rolling_windows_are_ordered_and_oos_segments_do_not_overlap(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=730)
        policy = WalkForwardConfig(
            training_days=365,
            oos_days=90,
            step_days=90,
        )
        folds = build_rolling_windows(start, end, policy)
        self.assertGreaterEqual(len(folds), 3)
        for previous, current in zip(folds, folds[1:]):
            self.assertEqual(previous.oos_end, current.oos_start)
            self.assertLess(previous.train_start, previous.train_end)
            self.assertLess(previous.oos_start, previous.oos_end)

    def test_overlapping_oos_windows_are_rejected_to_prevent_reuse(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "OOS_WINDOWS_MUST_NOT_OVERLAP"):
            policy = WalkForwardConfig(
                training_days=180,
                oos_days=60,
                step_days=30,
            )
            build_rolling_windows(start, start + timedelta(days=400), policy)

    def test_net_r_summary_reports_expectancy_profit_factor_and_drawdown(self):
        metrics = summarize_net_r([1.0, -1.0, 2.0, -0.5])
        self.assertEqual(metrics.trade_count, 4)
        self.assertAlmostEqual(metrics.net_expectancy_r, 0.375)
        self.assertAlmostEqual(metrics.profit_factor, 2.0)
        self.assertGreaterEqual(metrics.max_drawdown_r, 0.0)

    def test_empty_trade_sequence_is_not_qualified(self):
        metrics = summarize_net_r([])
        self.assertEqual(metrics.trade_count, 0)
        self.assertIsNone(metrics.net_expectancy_r)
        self.assertIsNone(metrics.profit_factor)


    def test_historical_cost_selector_never_uses_future_profile(self):
        from research.labs.three_sixty_nine_walk_forward import select_historical_cost_profile
        from research.labs.intraday_bias_cost_model import InstrumentCostProfile

        def profile(observed, source):
            return InstrumentCostProfile(
                instrument_id="TEST",
                instrument_type="SYNTHETIC_INDEX_UNDERLYING",
                return_basis="UNDERLYING_PRICE_NOTIONAL",
                spread_cost_bps_round_trip=1.0,
                slippage_cost_bps_round_trip=1.0,
                commission_bps_round_trip=0.0,
                other_fees_bps_round_trip=0.0,
                source=source,
                observed_at_utc=observed,
                verified=True,
                slippage_excludes_spread=True,
                max_age_seconds=86400.0,
            )

        before = profile("2026-01-05T09:00:00+00:00", "before")
        future = profile("2026-01-05T10:00:00+00:00", "future")
        chosen = select_historical_cost_profile(
            [future, before],
            instrument_id="TEST",
            entry_timestamp=datetime(2026, 1, 5, 9, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(chosen.source, "before")

    def test_historical_cost_selector_rejects_missing_or_stale_profile(self):
        from research.labs.three_sixty_nine_walk_forward import select_historical_cost_profile
        from research.labs.intraday_bias_cost_model import InstrumentCostProfile

        stale = InstrumentCostProfile(
            instrument_id="TEST",
            instrument_type="SYNTHETIC_INDEX_UNDERLYING",
            return_basis="UNDERLYING_PRICE_NOTIONAL",
            spread_cost_bps_round_trip=1.0,
            slippage_cost_bps_round_trip=1.0,
            commission_bps_round_trip=0.0,
            other_fees_bps_round_trip=0.0,
            source="stale",
            observed_at_utc="2026-01-01T00:00:00+00:00",
            verified=True,
            slippage_excludes_spread=True,
            max_age_seconds=3600.0,
        )
        with self.assertRaisesRegex(ValueError, "WFO_HISTORICAL_COST_PROFILE_MISSING_OR_STALE"):
            select_historical_cost_profile(
                [stale],
                instrument_id="TEST",
                entry_timestamp=datetime(2026, 1, 5, 9, 30, tzinfo=timezone.utc),
            )

    def test_regime_cells_are_gated_independently(self):
        from types import SimpleNamespace
        from research.labs.three_sixty_nine_walk_forward import summarize_regime_cells

        trades = [
            SimpleNamespace(regime="TRENDING_LOW_VOL", net_r=1.0),
            SimpleNamespace(regime="TRENDING_LOW_VOL", net_r=-0.5),
            SimpleNamespace(regime="RANGING_LOW_VOL", net_r=1.0),
        ]
        cells, failures = summarize_regime_cells(
            trades,
            ("TRENDING_LOW_VOL", "RANGING_LOW_VOL"),
            minimum_trades=2,
            minimum_expectancy_r=0.0,
            minimum_profit_factor=1.15,
            maximum_drawdown_r=15.0,
        )
        self.assertEqual(cells["TRENDING_LOW_VOL"]["trade_count"], 2)
        self.assertEqual(cells["RANGING_LOW_VOL"]["trade_count"], 1)
        self.assertTrue(any(
            item.startswith("REGIME_CELL_UNDERPOWERED:RANGING_LOW_VOL")
            for item in failures
        ))

    def test_unregistered_regime_cannot_disappear_into_aggregate(self):
        from types import SimpleNamespace
        from research.labs.three_sixty_nine_walk_forward import summarize_regime_cells

        _, failures = summarize_regime_cells(
            [SimpleNamespace(regime="UNKNOWN", net_r=1.0)],
            ("TRENDING_LOW_VOL", "RANGING_LOW_VOL"),
            minimum_trades=1,
            minimum_expectancy_r=0.0,
            minimum_profit_factor=1.15,
            maximum_drawdown_r=15.0,
        )
        self.assertIn("UNREGISTERED_REGIME_OBSERVED:UNKNOWN", failures)


    def test_normalized_bars_hash_binds_every_bar_field(self):
        from research.labs.deterministic_intraday_strategies import StrategyBar
        from research.labs.three_sixty_nine_walk_forward import calculate_normalized_bars_sha256

        first = StrategyBar(
            timestamp_utc="2026-01-01T00:00:00+00:00",
            open=100.0, high=101.0, low=99.0, close=100.5,
            volume=7.0, session_id="session-a",
        )
        changed = StrategyBar(
            timestamp_utc="2026-01-01T00:00:00+00:00",
            open=100.0, high=101.0, low=99.0, close=100.5,
            volume=8.0, session_id="session-a",
        )
        self.assertNotEqual(
            calculate_normalized_bars_sha256([first]),
            calculate_normalized_bars_sha256([changed]),
        )

    def test_parameter_grid_has_a_hard_trial_limit(self):
        from research.labs.three_sixty_nine_walk_forward import _parameter_sets

        grid = {
            "lookback_bars": [5, 10, 15],
            "min_sweep_ticks": [1.0, 2.0],
            "max_reclaim_bars": [1, 2],
            "displacement_filter": [False, True],
            "ema_atr_filter": [False, True],
        }
        with self.assertRaisesRegex(ValueError, "WFO_PARAMETER_GRID_EXCEEDS_MAXIMUM"):
            _parameter_sets(grid, max_parameter_sets=16)


    def test_protected_swing_hash_binds_rule_anchor_and_timestamps(self):
        from dataclasses import replace
        from research.labs.deterministic_intraday_strategies import StrategyBar
        from research.labs.three_sixty_nine_msnr import ProtectedSwing
        from research.labs.three_sixty_nine_walk_forward import calculate_protected_swings_sha256

        bars = [
            StrategyBar(f"2026-01-01T00:0{i}:00+00:00", 100.0, 101.0, 99.0, 100.5)
            for i in range(4)
        ]
        swing = ProtectedSwing(
            direction="LOW",
            anchor_price=99.0,
            pivot_timestamp_utc=bars[0].timestamp_utc,
            confirmation_timestamp_utc=bars[1].timestamp_utc,
            source_rule_id="protected-swing-v1",
            last_input_bar_timestamp_utc=bars[1].timestamp_utc,
        )
        original = calculate_protected_swings_sha256(
            {2: swing}, bars, timeframe_seconds=60
        )
        changed = calculate_protected_swings_sha256(
            {2: replace(swing, source_rule_id="protected-swing-v2")},
            bars,
            timeframe_seconds=60,
        )
        self.assertNotEqual(original, changed)

    def test_protected_swing_hash_rejects_future_or_unmapped_indices(self):
        from research.labs.deterministic_intraday_strategies import StrategyBar
        from research.labs.three_sixty_nine_msnr import ProtectedSwing
        from research.labs.three_sixty_nine_walk_forward import calculate_protected_swings_sha256

        bars = [
            StrategyBar(f"2026-01-01T00:0{i}:00+00:00", 100.0, 101.0, 99.0, 100.5)
            for i in range(3)
        ]
        swing = ProtectedSwing(
            direction="LOW",
            anchor_price=99.0,
            pivot_timestamp_utc=bars[0].timestamp_utc,
            confirmation_timestamp_utc=bars[1].timestamp_utc,
            source_rule_id="protected-swing-v1",
            last_input_bar_timestamp_utc=bars[1].timestamp_utc,
        )
        with self.assertRaisesRegex(ValueError, "WFO_PROTECTED_SWING_INDEX_INVALID"):
            calculate_protected_swings_sha256(
                {2: swing}, bars, timeframe_seconds=60
            )

    def test_historical_cost_hash_binds_numeric_cost_inputs(self):
        from dataclasses import replace
        from research.labs.three_sixty_nine_walk_forward import calculate_historical_cost_profiles_sha256
        from research.labs.intraday_bias_cost_model import InstrumentCostProfile

        profile = InstrumentCostProfile(
            instrument_id="TEST",
            instrument_type="SYNTHETIC_INDEX_UNDERLYING",
            return_basis="UNDERLYING_PRICE_NOTIONAL",
            spread_cost_bps_round_trip=1.0,
            slippage_cost_bps_round_trip=1.0,
            commission_bps_round_trip=0.0,
            other_fees_bps_round_trip=0.0,
            source="measured-fixture",
            observed_at_utc="2026-01-05T09:00:00+00:00",
            verified=True,
            slippage_excludes_spread=True,
        )
        original = calculate_historical_cost_profiles_sha256(
            [profile], instrument_id="TEST"
        )
        changed = calculate_historical_cost_profiles_sha256(
            [replace(profile, slippage_cost_bps_round_trip=2.0)],
            instrument_id="TEST",
        )
        self.assertNotEqual(original, changed)


    def test_day_block_bootstrap_ci_runs_with_trade_timestamps(self):
        from types import SimpleNamespace
        from research.labs.three_sixty_nine_walk_forward import _bootstrap_ci

        trades = [
            SimpleNamespace(entry_timestamp_utc="2026-01-01T09:00:00+00:00", net_r=1.0),
            SimpleNamespace(entry_timestamp_utc="2026-01-02T09:00:00+00:00", net_r=-0.25),
            SimpleNamespace(entry_timestamp_utc="2026-01-03T09:00:00+00:00", net_r=0.5),
        ]
        low, high = _bootstrap_ci(trades, replicates=250, seed=7)
        self.assertIsNotNone(low)
        self.assertIsNotNone(high)
        self.assertLessEqual(low, high)

    def test_invalid_or_naive_window_timestamps_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "WFO_TIMESTAMPS_MUST_BE_AWARE"):
            build_rolling_windows(
                datetime(2024, 1, 1),
                datetime(2025, 1, 1),
                WalkForwardConfig(),
            )


if __name__ == "__main__":
    unittest.main()
