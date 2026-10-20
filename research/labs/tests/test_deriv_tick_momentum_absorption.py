import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from research.labs.deriv_tick_momentum_absorption import (
    Config, SIGNAL_GRID, _volume_profile_for_window, build_profile,
    calculate_metrics, governance_verdict, load_data, simulate,
)


class DerivTickMomentumAbsorptionTests(unittest.TestCase):
    def make_bars(self, n=80):
        index = pd.date_range("2026-01-01T00:00:00Z", periods=n, freq="min")
        close = 100 + np.sin(np.arange(n) / 3.0) * 0.8 + np.arange(n) * 0.005
        open_ = np.concatenate(([close[0]], close[:-1]))
        high = np.maximum(open_, close) + 0.2
        low = np.minimum(open_, close) - 0.2
        return pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": np.ones(n) * 10},
            index=index,
        )

    def base_for_binary(self):
        idx = pd.date_range("2026-01-01T00:00:00Z", periods=5, freq="min")
        return {
            "index": idx,
            "o": np.array([100.0, 100.0, 101.0, 101.0, 100.0]),
            "h": np.array([100.5, 101.5, 101.5, 101.5, 100.5]),
            "l": np.array([99.5, 99.5, 100.5, 100.5, 99.5]),
            "c": np.array([100.0, 101.0, 101.0, 100.0, 100.0]),
            "atr": np.ones(5),
        }

    def test_profile_has_valid_levels(self):
        levels = _volume_profile_for_window(self.make_bars(30), bins=30, va_pct=0.70)
        self.assertIsNotNone(levels)
        val, vah = levels
        self.assertLess(val, vah)

    def test_profile_excludes_current_bar(self):
        df1 = self.make_bars(30)
        df2 = df1.copy()
        df2.iloc[20, df2.columns.get_loc("high")] = 10_000
        df2.iloc[20, df2.columns.get_loc("low")] = 9_999
        cfg = Config(vp_lookback=20, vp_bins=20, is_bars=100, oos_bars=50)
        vah1, val1 = build_profile(df1, cfg)
        vah2, val2 = build_profile(df2, cfg)
        self.assertAlmostEqual(vah1[20], vah2[20])
        self.assertAlmostEqual(val1[20], val2[20])

    def test_loader_drops_duplicates_and_invalid_ohlc(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bars.csv"
            pd.DataFrame([
                ["2026-01-01T00:00:00Z", 1, 2, 0, 1.5, 5],
                ["2026-01-01T00:00:00Z", 1, 2, 0, 1.5, 5],
                ["2026-01-01T00:01:00Z", 1, 0, 2, 1.5, 5],
                ["2026-01-01T00:10:00Z", 1, 2, 0, 1.5, 5],
            ], columns=["timestamp", "open", "high", "low", "close", "volume"]).to_csv(path, index=False)
            data, report = load_data(path)
            self.assertEqual(len(data), 2)
            self.assertEqual(report["duplicate_timestamps_dropped"], 1)
            self.assertEqual(report["invalid_or_nonfinite_ohlc_rows_dropped"], 1)
            self.assertEqual(report["gaps_over_3x_median_spacing"], 0)

    def test_rise_fall_uses_next_bar_and_fixed_expiry(self):
        cfg = Config(contract_type="RISE_FALL_PROXY", rf_duration_bars=1,
                     stake=10.0, payout_pct=0.90, is_bars=100, oos_bars=50)
        trades = simulate(self.base_for_binary(), np.array([1, 0, 0, 0, 0], dtype=np.int8), cfg, 0, 5)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["reason"], "fixed_expiry")
        self.assertAlmostEqual(trades[0]["pnl_cash_proxy"], 9.0)
        self.assertEqual(trades[0]["bars_held"], 1)

    def test_binary_tie_is_conservatively_a_loss(self):
        base = self.base_for_binary()
        base["c"][2] = 100.0
        cfg = Config(contract_type="RISE_FALL_PROXY", rf_duration_bars=1,
                     stake=10.0, payout_pct=0.90, is_bars=100, oos_bars=50)
        trades = simulate(base, np.array([1, 0, 0, 0, 0], dtype=np.int8), cfg, 0, 5)
        self.assertEqual(trades[0]["pnl_cash_proxy"], -10.0)

    def test_unresolved_boundary_trade_is_excluded(self):
        cfg = Config(contract_type="RISE_FALL_PROXY", rf_duration_bars=3,
                     stake=10.0, payout_pct=0.90, is_bars=100, oos_bars=50)
        trades = simulate(self.base_for_binary(), np.array([1, 0, 0, 0, 0], dtype=np.int8), cfg, 0, 4)
        self.assertEqual(trades, [])

    def test_empty_metrics_fail_governance_closed(self):
        metrics = calculate_metrics([])
        verdict = governance_verdict(metrics, 0.0, Config(is_bars=100, oos_bars=50))
        self.assertEqual(verdict["decision"], "FAIL_DO_NOT_DEPLOY_CAPITAL")
        self.assertFalse(all(verdict["gates"].values()))

    def test_payoff_parameters_are_not_in_signal_grid(self):
        self.assertNotIn("multiplier", SIGNAL_GRID)
        self.assertNotIn("rf_duration_bars", SIGNAL_GRID)


if __name__ == "__main__":
    unittest.main()
