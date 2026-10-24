from __future__ import annotations

import unittest

from assurance.trade_metrics import (
    TradeObservation, compute_research_metrics, out_of_sample_degradation, report_to_dict,
)


def trade(gross, spread=0.0, commission=0.0, payout=0.0, slip=0.0, risk=1.0):
    return TradeObservation(gross, spread, commission, payout, slip, risk)


class TradeMetricsTests(unittest.TestCase):
    def test_cost_adjusted_expectancy_gross_profit_factor_and_drawdown(self):
        result = compute_research_metrics([trade(2), trade(-1), trade(3), trade(-2)])
        self.assertEqual(result.trade_count, 4)
        self.assertAlmostEqual(result.net_profit, 2.0)
        self.assertAlmostEqual(result.expectancy_per_trade, 0.5)
        self.assertAlmostEqual(result.profit_factor, 5 / 3)
        self.assertAlmostEqual(result.maximum_drawdown_currency, 2.0)
        self.assertAlmostEqual(result.maximum_drawdown_r, 2.0)

    def test_profit_factor_uses_gross_pnl_while_net_profit_deducts_costs(self):
        result = compute_research_metrics([trade(2.0, spread=1.5), trade(-1.0)])
        self.assertAlmostEqual(result.profit_factor, 2.0)
        self.assertAlmostEqual(result.net_profit, -0.5)
        self.assertAlmostEqual(result.expectancy_per_trade, -0.25)

    def test_deriv_costs_are_deducted_explicitly(self):
        result = compute_research_metrics([
            trade(1.5, spread=0.05, commission=0.02, payout=0.2, slip=0.03),
            trade(-1.0),
        ])
        self.assertAlmostEqual(result.net_profit, 0.2)
        self.assertAlmostEqual(result.total_spread_costs, 0.05)
        self.assertAlmostEqual(result.total_commission_costs, 0.02)
        self.assertAlmostEqual(result.total_payout_costs, 0.2)
        self.assertAlmostEqual(result.total_slippage_costs, 0.03)

    def test_profit_factor_is_json_safe_when_no_gross_losses(self):
        result = compute_research_metrics([trade(1), trade(2)])
        self.assertIsNone(result.profit_factor)
        self.assertEqual(result.profit_factor_status, "UNDEFINED_NO_GROSS_LOSSES")

    def test_missing_trades_reject(self):
        with self.assertRaisesRegex(ValueError, "RESEARCH_TRADES_REQUIRED"):
            compute_research_metrics([])

    def test_bad_costs_or_risk_reject(self):
        with self.assertRaisesRegex(ValueError, "COSTS_MUST_BE_NON_NEGATIVE"):
            trade(1, spread=-1).net_pnl()
        with self.assertRaisesRegex(ValueError, "RISK_AMOUNT_MUST_BE_POSITIVE"):
            trade(1, risk=0).net_r()

    def test_non_finite_trade_input_rejects(self):
        with self.assertRaisesRegex(ValueError, "NON_FINITE_GROSS_PNL"):
            trade(float("nan")).net_pnl()

    def test_oos_degradation_over_30_percent_rejects(self):
        result = out_of_sample_degradation(1.0, 0.69)
        self.assertTrue(result["rejected"])
        self.assertEqual(result["status"], "REJECT_EXCESSIVE_OOS_DEGRADATION")

    def test_non_positive_in_sample_expectancy_rejects(self):
        result = out_of_sample_degradation(0.0, 0.5)
        self.assertTrue(result["rejected"])
        self.assertIsNone(result["degradation_fraction"])

    def test_invalid_oos_degradation_threshold_rejects(self):
        with self.assertRaisesRegex(ValueError, "OOS_DEGRADATION_THRESHOLD_OUT_OF_RANGE"):
            out_of_sample_degradation(1.0, 0.9, rejection_threshold=1.0)

    def test_report_never_grants_execution_authority(self):
        metrics = compute_research_metrics([trade(2), trade(-1)])
        report = report_to_dict(metrics, is_expectancy=1.0, oos_expectancy=0.9)
        self.assertFalse(report["execution_authorization_granted"])
        self.assertNotIn("win_rate", report["metrics"])


if __name__ == "__main__":
    unittest.main()
