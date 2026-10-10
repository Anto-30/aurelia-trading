from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from research.labs.session_breakout_backtest import (
    CostModel,
    backtest_session_a,
    backtest_session_b,
    build_opening_range_15m_from_5m,
    summarize_sessions,
)

NY = ZoneInfo("America/New_York")
DAY = date(2026, 10, 8)


def make_bars(
    *,
    session_date: date = DAY,
    breakout_at: time | None = time(9, 30),
    breakout_high: float = 107.0,
    breakout_low: float = 99.0,
    breakout_close: float = 106.0,
    target_at: time | None = time(9, 40),
    target_high: float = 130.0,
    target_low: float = 106.0,
) -> list:
    bars = []
    stamp = datetime.combine(session_date, time(4, 0), NY)
    end = datetime.combine(session_date, time(16, 0), NY)
    while stamp < end:
        local_time = stamp.time()
        values = (100.0, 101.0, 99.0, 100.0)
        if local_time == time(4, 50):
            values = (100.0, 105.0, 99.0, 100.0)
        elif local_time == time(5, 40):
            values = (100.0, 101.0, 95.0, 100.0)
        if breakout_at is not None and local_time == breakout_at:
            values = (100.0, breakout_high, breakout_low, breakout_close)
        if target_at is not None and local_time == target_at:
            values = (106.5, target_high, target_low, 120.0)
        bars.append(__import__("research.labs.session_breakout_candidates", fromlist=["OHLCBar"]).OHLCBar(
            timestamp_utc=stamp.astimezone(timezone.utc),
            open=values[0], high=values[1], low=values[2], close=values[3],
        ))
        stamp += timedelta(minutes=5)
    return bars


class SessionBreakoutBacktestTests(unittest.TestCase):
    def test_module_is_research_only(self):
        from research.labs import session_breakout_backtest as module
        self.assertTrue(module.RESEARCH_ONLY)
        self.assertFalse(module.CAPITAL_AUTHORITY)
        self.assertFalse(module.LIVE_EXECUTION)

    def test_candidate_a_target_hit_and_costs_calculated_only_when_complete(self):
        bars = make_bars()
        costs = CostModel(
            tick_size=0.25,
            multiplier_usd_per_point=2.0,
            spread_round_trip_points=0.0,
            slippage_ticks_per_side=1.0,
            commission_roundtrip_usd=1.0,
        )
        result = backtest_session_a(
            bars, DAY, stop_mode="OPPOSITE_RANGE_BOUNDARY", costs=costs
        )
        self.assertEqual(result.status, "TRADED")
        self.assertEqual(result.trade.exit_status, "TARGET")
        self.assertAlmostEqual(result.trade.pnl_r_conservative, 2.0)
        self.assertAlmostEqual(result.trade.net_pnl_r_conservative, 1.8)
        self.assertEqual(result.trade.net_pnl_usd_per_contract_conservative, 18.0)
        result_unknown_costs = backtest_session_a(
            bars, DAY, stop_mode="OPPOSITE_RANGE_BOUNDARY",
            costs=CostModel(0.25, 2.0, 0.0, 1.0, None),
        )
        self.assertIsNone(result_unknown_costs.trade.net_pnl_r_conservative)

    def test_candidate_a_same_bar_stop_and_target_is_ambiguous(self):
        bars = make_bars(target_at=time(9, 40), target_high=130.0, target_low=90.0)
        result = backtest_session_a(
            bars, DAY, stop_mode="OPPOSITE_RANGE_BOUNDARY"
        )
        self.assertEqual(result.trade.exit_status, "AMBIGUOUS")
        self.assertTrue(result.trade.ambiguous_ohlc_order)
        self.assertIsNone(result.trade.pnl_r_known)
        self.assertLess(result.trade.pnl_r_conservative, 0.0)

    def test_candidate_a_no_breakout_is_no_trade(self):
        bars = make_bars(breakout_at=None, target_at=None)
        result = backtest_session_a(
            bars, DAY, stop_mode="OPPOSITE_RANGE_BOUNDARY"
        )
        self.assertEqual(result.status, "NO_TRADE")
        self.assertEqual(result.reason, "NO_BREAKOUT")

    def test_missing_range_bars_are_ineligible_not_no_trade(self):
        bars = make_bars()
        bars = [bar for i, bar in enumerate(bars) if i != 5]
        result = backtest_session_a(
            bars, DAY, stop_mode="OPPOSITE_RANGE_BOUNDARY"
        )
        self.assertEqual(result.status, "INELIGIBLE")
        self.assertTrue(result.reason.startswith("INCOMPLETE_SESSION_WINDOW"))

    def test_opening_range_aggregator_and_candidate_b(self):
        bars = make_bars(
            breakout_at=time(10, 0),
            breakout_high=110.0,
            breakout_low=99.0,
            breakout_close=108.0,
            target_at=time(10, 10),
            target_high=130.0,
            target_low=106.0,
        )
        bars_15m = build_opening_range_15m_from_5m(bars, DAY)
        self.assertEqual(len(bars_15m), 2)
        self.assertEqual(bars_15m[0].timestamp_utc.astimezone(NY).time(), time(9, 30))
        self.assertEqual(bars_15m[1].timestamp_utc.astimezone(NY).time(), time(9, 45))
        result = backtest_session_b(
            bars, bars_15m, DAY, target_mode="R_MULTIPLE", target_value=2.0
        )
        self.assertEqual(result.status, "TRADED")
        self.assertEqual(result.trade.exit_status, "STOP")
        self.assertFalse(result.trade.ambiguous_ohlc_order)

    def test_opening_range_aggregator_rejects_missing_bars(self):
        bars = make_bars()
        bars = [
            bar for bar in bars
            if bar.timestamp_utc.astimezone(NY).time() != time(9, 40)
        ]
        with self.assertRaisesRegex(ValueError, "OPENING_30M_INCOMPLETE"):
            build_opening_range_15m_from_5m(bars, DAY)

    def test_summary_counts_no_trade_sessions_and_unknown_net_costs(self):
        from research.labs.session_breakout_backtest import SessionResult
        traded = backtest_session_a(
            make_bars(), DAY, stop_mode="OPPOSITE_RANGE_BOUNDARY"
        )
        no_trade = backtest_session_a(
            make_bars(session_date=date(2026, 10, 9), breakout_at=None, target_at=None),
            date(2026, 10, 9),
            stop_mode="OPPOSITE_RANGE_BOUNDARY",
        )
        summary = summarize_sessions([traded, no_trade], variant_id="A_TEST")
        self.assertEqual(summary.input_sessions, 2)
        self.assertEqual(summary.eligible_sessions, 2)
        self.assertEqual(summary.trades, 1)
        self.assertEqual(summary.no_trade_sessions, 1)
        self.assertEqual(summary.net_economics_status, "UNDETERMINED")
        self.assertAlmostEqual(summary.expectancy_conservative_r_per_eligible_session, 1.0)

    def test_complete_cost_model_reports_net_metrics(self):
        costs = CostModel(
            tick_size=0.25,
            multiplier_usd_per_point=2.0,
            spread_round_trip_points=0.25,
            slippage_ticks_per_side=1.0,
            commission_roundtrip_usd=0.5,
        )
        trade = backtest_session_a(
            make_bars(), DAY, stop_mode="OPPOSITE_RANGE_BOUNDARY", costs=costs
        )
        no_trade = backtest_session_a(
            make_bars(breakout_at=None, target_at=None),
            date(2026, 10, 9),
            stop_mode="OPPOSITE_RANGE_BOUNDARY",
            costs=costs,
        )
        summary = summarize_sessions([trade, no_trade], variant_id="A_COST_TEST")
        self.assertEqual(summary.net_economics_status, "CALCULATED")
        self.assertIsNotNone(summary.net_expectancy_conservative_r_per_trade)
        self.assertIsNone(summary.net_profit_factor_conservative)  # undefined with no losing observations

    def test_cost_model_rejects_negative_costs(self):
        with self.assertRaisesRegex(ValueError, "INVALID_COST"):
            CostModel(0.25, 2.0, -0.1, 1.0, 0.0)

    def test_losing_trade_streak_skips_no_trade_but_session_streak_resets(self):
        from research.labs.session_breakout_backtest import SessionResult
        one = backtest_session_a(make_bars(), DAY, stop_mode="OPPOSITE_RANGE_BOUNDARY")
        self.assertIsNotNone(one.trade)
        trade = one.trade
        loss = replace(
            trade,
            exit_price_conservative=trade.entry_reference_price-trade.initial_risk_points,
            gross_pnl_points_conservative=-trade.initial_risk_points,
            gross_pnl_usd_per_contract_conservative=None,
            pnl_r_known=-1.0,
            pnl_r_conservative=-1.0,
            net_pnl_usd_per_contract_conservative=None,
            net_pnl_r_conservative=None,
            exit_status="STOP",
            ambiguous_ohlc_order=False,
        )
        results = [
            SessionResult(date(2026, 10, 8), "TRADED", "fixture", None, loss),
            SessionResult(date(2026, 10, 9), "NO_TRADE", "no signal", None, None),
            SessionResult(date(2026, 10, 10), "TRADED", "fixture", None, loss),
            SessionResult(date(2026, 10, 11), "TRADED", "fixture", None, loss),
        ]
        summary = summarize_sessions(results, variant_id="STREAK_TEST")
        self.assertEqual(summary.longest_consecutive_losing_trades, 3)
        self.assertEqual(summary.longest_consecutive_losing_sessions, 2)

    def test_daily_drawdown_includes_zero_trade_sessions(self):
        from research.labs.session_breakout_backtest import SessionResult, TradeOutcome
        summary = summarize_sessions([], variant_id="EMPTY")
        self.assertEqual(summary.eligible_sessions, 0)
        self.assertEqual(summary.trades, 0)
        self.assertIsNone(summary.max_drawdown_conservative_r)
        self.assertEqual(summary.net_economics_status, "UNDETERMINED")


if __name__ == "__main__":
    unittest.main()
