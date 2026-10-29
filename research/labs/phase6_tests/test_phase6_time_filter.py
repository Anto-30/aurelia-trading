from __future__ import annotations

import unittest

import pandas as pd

from research.labs.phase6_time_filter import (
    BacktestConfig,
    _features,
    CAPITAL_AUTHORITY,
    LIVE_EXECUTION,
    generate_phase6_plus_9_signals,
    generate_phase6_signals,
    run_phase6_backtest,
)

NY = "America/New_York"


def minute_frame(day: str = "2026-10-30", *, end_time: str = "10:00", timezone_name: str = NY) -> pd.DataFrame:
    start = pd.Timestamp(f"{day} 04:00:00", tz=timezone_name)
    end = pd.Timestamp(f"{day} {end_time}:00", tz=timezone_name)
    idx = pd.date_range(start, end, freq="min")
    n = len(idx)
    close = [100.0 + i * 0.001 for i in range(n)]
    target_pos = next(k for k, t in enumerate(idx) if t.hour == 8 and t.minute == 50)
    for j, stamp in enumerate(idx):
        if stamp.hour == 8 and stamp.minute >= 50:
            close[j] += (j - target_pos + 1) * 0.03
    open_ = [close[i] - 0.01 for i in range(n)]
    high = [max(open_[i], close[i]) + 0.02 for i in range(n)]
    low = [min(open_[i], close[i]) - 0.02 for i in range(n)]
    volume = [1000.0] * n
    target_positions = [i for i, t in enumerate(idx) if t.hour == 8 and t.minute == 50]
    for i in target_positions:
        volume[i] = 2500.0
        high[i] = max(open_[i], close[i]) + 0.08
        low[i] = min(open_[i], close[i]) - 0.02
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)


class Phase6TimeFilterTests(unittest.TestCase):
    def config(self, **kwargs):
        base = dict(commission_per_share_per_side=0.0, slippage_per_share_per_side=0.0)
        base.update(kwargs)
        return BacktestConfig(**base)

    def test_timezone_naive_index_fails_closed(self):
        frame = minute_frame()
        frame.index = frame.index.tz_localize(None)
        with self.assertRaisesRegex(ValueError, "TIMEZONE_AWARE"):
            generate_phase6_signals(frame, self.config())

    def test_dst_offset_is_resolved_from_new_york_timezone(self):
        pre = pd.Timestamp("2026-10-30 08:50", tz=NY)
        post = pd.Timestamp("2026-11-02 08:50", tz=NY)
        self.assertEqual(pre.tz_convert("UTC").strftime("%H:%M"), "12:50")
        self.assertEqual(post.tz_convert("UTC").strftime("%H:%M"), "13:50")

    def test_phase6_signal_timezone_conversion_survives_dst_offset_change(self):
        frame = minute_frame("2026-11-02").tz_convert("UTC")
        signals = generate_phase6_signals(frame, self.config())
        nonzero = signals[signals != 0]
        self.assertEqual(len(nonzero), 1)
        self.assertEqual(nonzero.index[0].strftime("%Y-%m-%d %H:%M %z"), "2026-11-02 08:50 -0500")

    def test_phase6_signal_only_at_exact_target_time(self):
        frame = minute_frame()
        signals = generate_phase6_signals(frame, self.config())
        nonzero = signals[signals != 0]
        self.assertEqual(len(nonzero), 1)
        self.assertEqual(nonzero.index[0].strftime("%H:%M:%S"), "08:50:00")
        self.assertEqual(int(nonzero.iloc[0]), 1)

    def test_phase6_plus_9_requires_volume_column(self):
        frame = minute_frame().drop(columns="volume")
        with self.assertRaisesRegex(ValueError, "VOLUME_COLUMN_REQUIRED"):
            generate_phase6_plus_9_signals(frame, self.config())

    def test_volume_baseline_excludes_current_signal_bar(self):
        frame = minute_frame()
        target = frame.index[(frame.index.hour == 8) & (frame.index.minute == 50)][0]
        frame.loc[target, "volume"] = 1501.0
        signals = generate_phase6_plus_9_signals(frame, self.config())
        self.assertEqual(int(signals.loc[target]), 1)
        self.assertGreater(frame.loc[target, "volume"], 1.5 * frame.loc[:target].iloc[-21:-1].volume.mean())

    def test_true_range_includes_gap_from_previous_close(self):
        frame = minute_frame()
        next_ts = frame.index[1]
        prior_close = float(frame.iloc[0].close)
        frame.loc[next_ts, "open"] = prior_close - 3.0
        frame.loc[next_ts, "close"] = prior_close - 2.5
        frame.loc[next_ts, "high"] = prior_close - 2.4
        frame.loc[next_ts, "low"] = prior_close - 3.1
        features = _features(frame, self.config(), require_volume=False)
        self.assertAlmostEqual(float(features.loc[next_ts, "true_range"]), 3.1)

    def test_costs_are_required_for_backtest(self):
        with self.assertRaisesRegex(ValueError, "EXPLICIT_COMMISSION_AND_SLIPPAGE_REQUIRED"):
            run_phase6_backtest(minute_frame(), variant="PHASE6_ONLY", config=BacktestConfig())

    def test_commission_and_slippage_are_subtracted_from_net_pnl(self):
        frame = minute_frame()
        free = run_phase6_backtest(frame, variant="PHASE6_ONLY", config=self.config())
        charged = run_phase6_backtest(frame, variant="PHASE6_ONLY", config=self.config(
            commission_per_share_per_side=0.01, slippage_per_share_per_side=0.02))
        self.assertEqual(len(free["trades"]), 1)
        self.assertEqual(len(charged["trades"]), 1)
        self.assertAlmostEqual(float(free["trades"].iloc[0].net_pnl_per_share) -
                               float(charged["trades"].iloc[0].net_pnl_per_share), 0.06)

    def test_backtest_is_research_only(self):
        self.assertFalse(CAPITAL_AUTHORITY)
        self.assertFalse(LIVE_EXECUTION)

    def test_next_bar_entry_and_15_minute_time_exit(self):
        result = run_phase6_backtest(minute_frame(), variant="PHASE6_ONLY", config=self.config())
        trades = result["trades"]
        if not trades.empty:
            trade = trades.iloc[0]
            self.assertEqual(pd.Timestamp(trade.signal_timestamp_ny).strftime("%H:%M"), "08:50")
            self.assertEqual(pd.Timestamp(trade.entry_timestamp_ny).strftime("%H:%M"), "08:51")
            self.assertIn(trade.exit_reason, {"HARD_STOP", "TIME_EXIT_09_05_BAR_CLOSE"})
            if trade.exit_reason == "TIME_EXIT_09_05_BAR_CLOSE":
                self.assertEqual(trade.holding_minutes, 15.0)

    def test_missing_minute_during_hold_skips_candidate(self):
        frame = minute_frame().drop(pd.Timestamp("2026-10-30 08:57", tz=NY))
        result = run_phase6_backtest(frame, variant="PHASE6_ONLY", config=self.config())
        self.assertEqual(result["skipped_signals"].get("MISSING_MINUTE_BAR_DURING_HOLD", 0), 1)


if __name__ == "__main__":
    unittest.main()
