from __future__ import annotations

import unittest
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from research.labs.atos_smc_v2 import (
    BacktestConfig,
    LiquidityPool,
    ResearchDataError,
    Setup,
    Strategy1Config,
    Strategy2Config,
    TimeWindow,
    _detect_sweep,
    _swing_context,
    build_prior_session_liquidity,
    calculate_metrics,
    data_quality_report,
    resample_15m,
    simulate,
    validate_ohlc,
)


def bars(index, *, opens=None, highs=None, lows=None, closes=None):
    count = len(index)
    opens = opens if opens is not None else [100.0] * count
    closes = closes if closes is not None else list(opens)
    highs = highs if highs is not None else [max(o, c) + 0.5 for o, c in zip(opens, closes)]
    lows = lows if lows is not None else [min(o, c) - 0.5 for o, c in zip(opens, closes)]
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes},
        index=pd.DatetimeIndex(index),
    )


class ATOSSMCDataContractTests(unittest.TestCase):
    def test_rejects_naive_timestamp_index(self):
        index = pd.date_range("2026-11-10 13:00", periods=3, freq="min")
        with self.assertRaisesRegex(ResearchDataError, "TIMEZONE_AWARE"):
            validate_ohlc(bars(index))

    def test_rejects_duplicate_and_non_monotonic_timestamps(self):
        base = pd.Timestamp("2026-11-10T13:00:00Z")
        duplicate = bars(pd.DatetimeIndex([base, base, base + pd.Timedelta(minutes=1)]))
        with self.assertRaisesRegex(ResearchDataError, "DUPLICATE"):
            validate_ohlc(duplicate)
        unordered = bars(pd.DatetimeIndex([base, base + pd.Timedelta(minutes=2), base + pd.Timedelta(minutes=1)]))
        with self.assertRaisesRegex(ResearchDataError, "STRICTLY_INCREASING"):
            validate_ohlc(unordered)

    def test_rejects_invalid_ohlc_envelope(self):
        index = pd.date_range("2026-11-10T13:00:00Z", periods=2, freq="min")
        data = bars(index, opens=[100, 100], highs=[99, 101], lows=[98, 99], closes=[100, 100])
        with self.assertRaisesRegex(ResearchDataError, "HIGH_INCONSISTENT"):
            validate_ohlc(data)

    def test_quality_report_exposes_missing_bars_without_filling(self):
        index = pd.DatetimeIndex([
            pd.Timestamp("2026-11-10T13:00:00Z"),
            pd.Timestamp("2026-11-10T13:02:00Z"),
        ])
        report = data_quality_report(
            bars(index),
            start_utc=pd.Timestamp("2026-11-10T13:00:00Z"),
            end_utc=pd.Timestamp("2026-11-10T13:03:00Z"),
        )
        self.assertEqual(report["expected_bars"], 3)
        self.assertEqual(report["present_bars_in_window"], 2)
        self.assertEqual(report["missing_bars"], 1)
        self.assertFalse(report["forward_filled"])
        self.assertAlmostEqual(report["coverage_pct"], 200.0 / 3.0)

    def test_only_complete_15_minute_bars_are_resampled(self):
        index = pd.date_range("2026-11-10T13:00:00Z", periods=30, freq="min")
        data = bars(index)
        data = data.drop(index[20])
        result = resample_15m(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.index[0], index[0])


class ATOSSMCTimeWindowTests(unittest.TestCase):
    def test_0849_open_bar_is_eligible_by_0850_close_but_0850_open_bar_is_not(self):
        # New York is UTC-5 on 2026-11-10 (after the autumn DST change).
        index = pd.DatetimeIndex([
            "2026-11-10T13:49:00Z",
            "2026-11-10T13:50:00Z",
            "2026-11-10T13:51:00Z",
        ])
        window = TimeWindow()
        self.assertEqual(window.mask(index).tolist(), [True, False, False])
        self.assertEqual(window.open_mask(index).tolist(), [True, True, False])
        self.assertTrue(window.is_cutoff_open(index[1]))
        self.assertFalse(window.is_cutoff_open(index[0]))

    def test_daylight_saving_time_is_resolved_by_timezone_database(self):
        # During US daylight time, 08:49 New York is 12:49 UTC, not 13:49.
        index = pd.DatetimeIndex(["2026-07-10T12:49:00Z"])
        self.assertTrue(TimeWindow().mask(index)[0])


class ATOSSMCStructureTests(unittest.TestCase):
    def test_fractal_is_unavailable_until_right_hand_bars_close(self):
        index = pd.date_range("2026-11-10T13:00:00Z", periods=7, freq="min")
        data = bars(
            index,
            opens=[1.5, 2.5, 4.5, 3.5, 2.5, 2.2, 1.8],
            highs=[2.0, 3.0, 5.0, 4.0, 3.0, 2.7, 2.2],
            lows=[1.0, 2.0, 4.0, 3.0, 2.0, 1.9, 1.5],
            closes=[1.5, 2.5, 4.5, 3.5, 2.5, 2.2, 1.8],
        )
        state, highs, _ = _swing_context(data)
        self.assertTrue(np.isnan(state["last_high"].iloc[3]))
        self.assertEqual(state["last_high"].iloc[4], 5.0)
        event = next(item for item in highs if item["pivot_index"] == 2)
        self.assertEqual(event["confirmed_index"], 4)
        self.assertEqual(event["available_at_utc"], index[4] + pd.Timedelta(minutes=1))

    def test_strategy1_enforces_minimum_three_risk_reward(self):
        with self.assertRaisesRegex(ValueError, "STRATEGY1_RR_OR_STOP_INVALID"):
            Strategy1Config(minimum_rr=2.99)

    def test_strategy2_rejects_invalid_displacement_threshold(self):
        with self.assertRaisesRegex(ValueError, "STRATEGY2_THRESHOLD_INVALID"):
            Strategy2Config(displacement_atr_multiple=0)


class ATOSSMCLiquidityTests(unittest.TestCase):
    def test_high_sweep_requires_wick_pierce_and_close_reclaim(self):
        pool = LiquidityPool(
            pool_id="EQH-1", session_date="2026-11-10", session_name="LONDON",
            kind="EQUAL_HIGHS", side="HIGH", level=100.0,
        )
        valid = pd.Series({"open": 99.5, "high": 100.02, "low": 99.2, "close": 99.7})
        self.assertEqual(
            _detect_sweep(valid, [pool], tick_size=0.01, minimum_sweep_ticks=1)["direction"],
            "SHORT",
        )
        inversion = valid.copy()
        inversion["close"] = 100.03
        self.assertIsNone(
            _detect_sweep(inversion, [pool], tick_size=0.01, minimum_sweep_ticks=1)
        )

    def test_low_sweep_requires_wick_pierce_and_close_reclaim(self):
        pool = LiquidityPool(
            pool_id="EQL-1", session_date="2026-11-10", session_name="ASIA",
            kind="EQUAL_LOWS", side="LOW", level=100.0,
        )
        valid = pd.Series({"open": 100.5, "high": 100.8, "low": 99.98, "close": 100.3})
        self.assertEqual(
            _detect_sweep(valid, [pool], tick_size=0.01, minimum_sweep_ticks=1)["direction"],
            "LONG",
        )
        inversion = valid.copy()
        inversion["close"] = 99.97
        self.assertIsNone(
            _detect_sweep(inversion, [pool], tick_size=0.01, minimum_sweep_ticks=1)
        )

    def test_two_sided_sweep_is_rejected_as_ambiguous(self):
        high = LiquidityPool("H", "2026-11-10", "LONDON", "SESSION_HIGH", "HIGH", 100.0)
        low = LiquidityPool("L", "2026-11-10", "ASIA", "SESSION_LOW", "LOW", 99.0)
        candle = pd.Series({"open": 99.5, "high": 100.2, "low": 98.8, "close": 99.5})
        self.assertIsNone(
            _detect_sweep(candle, [high, low], tick_size=0.01, minimum_sweep_ticks=1)
        )

    def test_liquidity_uses_only_prior_completed_london_session(self):
        index = pd.date_range("2026-11-09T07:00:00Z", "2026-11-10T10:00:00Z", freq="min")
        opens = [100.0 + (i % 20) * 0.01 for i in range(len(index))]
        highs = [value + 0.05 for value in opens]
        lows = [value - 0.05 for value in opens]
        closes = list(opens)
        data = bars(index, opens=opens, highs=highs, lows=lows, closes=closes)
        pools = build_prior_session_liquidity(data, tick_size=0.01)
        current_day_london = [
            pool for pool in pools["2026-11-10"] if pool.session_name == "LONDON"
        ]
        self.assertTrue(current_day_london)
        # Nov 10 London is still forming during the requested morning window;
        # levels must instead come from the already-completed Nov 9 session.
        self.assertTrue(all(pd.Timestamp(pool.source_time_utc).date().isoformat() == "2026-11-09"
                            for pool in current_day_london if pool.source_time_utc))


class ATOSSMCBacktestTests(unittest.TestCase):
    def make_setup(self, signal_index: int, signal_open: pd.Timestamp) -> Setup:
        return Setup(
            strategy_id="TEST_STRATEGY",
            direction="LONG",
            signal_index=signal_index,
            signal_time_utc=(signal_open + pd.Timedelta(minutes=1)).isoformat(),
            entry=100.0,
            stop=98.0,
            target=102.0,
            invalidation_price=99.0,
            zone_low=99.0,
            zone_high=101.0,
            order_ttl_bars=3,
            minimum_rr=1.0,
            evidence=("TEST_ONLY",),
            liquidity_reference="TEST_LEVEL",
        )

    def test_limit_orders_do_not_fill_on_the_signal_bar_and_stop_wins_collision(self):
        index = pd.date_range("2026-11-10T13:00:00Z", periods=3, freq="min")
        data = bars(
            index,
            opens=[100, 100, 100],
            highs=[101, 103, 101],
            lows=[99.5, 97, 99],
            closes=[100, 101, 100],
        )
        config = BacktestConfig(starting_equity=10_000, risk_fraction=0.01, tick_size=0.01)
        result = simulate(
            data, [self.make_setup(0, index[0])],
            config=config, strategy_id="TEST",
        )
        self.assertEqual(result["trade_count"], 1)
        trade = result["trades"][0]
        self.assertEqual(trade["entry_time_utc"], index[1].isoformat())
        self.assertEqual(trade["exit_reason"], "STOP")
        self.assertAlmostEqual(trade["exit_price"], 98.0)
        self.assertAlmostEqual(trade["r_multiple_net"], -1.0)

    def test_same_bar_limit_fill_does_not_credit_target_only_touch(self):
        index = pd.date_range("2026-11-10T13:00:00Z", periods=3, freq="min")
        data = bars(
            index,
            opens=[100, 101, 101],
            highs=[101, 103, 101],
            lows=[99.5, 99.5, 99],
            closes=[100, 102.5, 100],
        )
        # The limit fills inside bar 1, whose high also reaches target. Since
        # OHLC cannot establish whether the target preceded the fill, target-only
        # same-bar profit is not credited. The position is marked at bar 2 close.
        result = simulate(
            data, [self.make_setup(0, index[0])],
            config=BacktestConfig(tick_size=0.01), strategy_id="TEST",
        )
        self.assertEqual(result["trade_count"], 1)
        self.assertEqual(result["trades"][0]["exit_reason"], "END_OF_DATA_MARK_TO_MARK")
        self.assertEqual(result["trades"][0]["exit_price"], 100.0)

    def test_one_percent_risk_and_three_percent_daily_drawdown_halt(self):
        index = pd.date_range("2026-11-10T13:00:00Z", periods=10, freq="min")
        opens = [100.0] * 10
        highs = [101.0] * 10
        lows = [99.0] * 10
        closes = [100.0] * 10
        for i in (1, 3, 5, 7):
            lows[i] = 97.0
        data = bars(index, opens=opens, highs=highs, lows=lows, closes=closes)
        setups = [self.make_setup(i, index[i]) for i in (0, 2, 4, 6, 8)]
        result = simulate(
            data, setups,
            config=BacktestConfig(starting_equity=10_000, risk_fraction=0.01,
                                  daily_drawdown_limit=0.03, tick_size=0.01),
            strategy_id="TEST",
        )
        self.assertEqual(result["trade_count"], 4)
        self.assertGreaterEqual(result["rejections"]["DAILY_DRAWDOWN_HALT"], 1)
        self.assertTrue(any(row["daily_halted"] for row in result["equity_curve"]))
        self.assertFalse(result["order_submission_permitted"])
        self.assertEqual(result["live_execution"], "BLOCKED")

    def test_risk_fraction_cannot_exceed_two_percent_and_daily_dd_three_percent(self):
        with self.assertRaisesRegex(ValueError, "RISK_FRACTION_ABOVE_2_PERCENT"):
            BacktestConfig(risk_fraction=0.0201)
        with self.assertRaisesRegex(ValueError, "DAILY_DRAWDOWN_ABOVE_3_PERCENT"):
            BacktestConfig(daily_drawdown_limit=0.0301)

    def test_empty_metrics_are_null_not_invented_zero_statistics(self):
        result = calculate_metrics(
            pd.DataFrame(),
            pd.DataFrame(),
            initial_equity=10_000,
        )
        self.assertIsNone(result["expectancy_r_per_trade"])
        self.assertIsNone(result["profit_factor"])
        self.assertIsNone(result["sharpe_daily_annualized_sqrt365"])
        self.assertEqual(result["r_multiple_distribution"]["count"], 0)


if __name__ == "__main__":
    unittest.main()
