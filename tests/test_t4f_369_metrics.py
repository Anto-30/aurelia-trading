"""Unit tests for T4F journal metrics."""
import unittest

import pandas as pd

from research.labs.t4f_369_metrics import calculate_performance_metrics, evaluate_369_filter_ablation


def journal():
    return pd.DataFrame([
        {"candidate_id": "a", "timestamp_utc": "2026-01-01T00:00:00Z",
         "risk_usd": 100, "gross_pnl_usd": 200, "commission_usd": 2,
         "spread_cost_usd": 3, "slippage_cost_usd": 5, "eligible_369": True},
        {"candidate_id": "b", "timestamp_utc": "2026-01-01T00:01:00Z",
         "risk_usd": 100, "gross_pnl_usd": -100, "commission_usd": 2,
         "spread_cost_usd": 3, "slippage_cost_usd": 5, "eligible_369": False},
    ])


class MetricsTests(unittest.TestCase):
    def test_metrics_are_net_of_costs(self):
        result = calculate_performance_metrics(journal())
        self.assertEqual(result["total_trades"], 2)
        self.assertEqual(result["net_pnl_usd"], 80.0)
        self.assertAlmostEqual(result["expectancy_net_r"], 0.4)
        self.assertAlmostEqual(result["profit_factor_net"], 190 / 110)

    def test_drawdown_includes_initial_zero_equity(self):
        frame = journal().iloc[[1]].copy()
        result = calculate_performance_metrics(frame)
        self.assertEqual(result["max_drawdown_r"], -1.1)

    def test_ablation_uses_same_candidate_cohort_and_filter(self):
        result = evaluate_369_filter_ablation(journal())
        self.assertEqual(result["structure_only_baseline"]["total_trades"], 2)
        self.assertEqual(result["t4f_369_filtered"]["total_trades"], 1)
        self.assertEqual(result["trade_count_retention"], 0.5)

    def test_negative_cost_rejected(self):
        frame = journal()
        frame.loc[0, "slippage_cost_usd"] = -1
        with self.assertRaisesRegex(ValueError, "COSTS_MUST_BE_NON_NEGATIVE"):
            calculate_performance_metrics(frame)

    def test_bad_risk_rejected(self):
        frame = journal()
        frame.loc[0, "risk_usd"] = 0
        with self.assertRaisesRegex(ValueError, "RISK_USD_MUST_BE_POSITIVE"):
            calculate_performance_metrics(frame)

    def test_empty_369_subset_returns_zero_trade_metrics(self):
        frame = journal()
        frame["eligible_369"] = False
        result = evaluate_369_filter_ablation(frame)
        self.assertEqual(result["t4f_369_filtered"]["total_trades"], 0)
        self.assertIsNone(result["t4f_369_filtered"]["expectancy_net_r"])


if __name__ == "__main__":
    unittest.main()
