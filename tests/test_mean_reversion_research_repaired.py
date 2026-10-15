import math
import unittest

from research.labs.mean_reversion_research_repaired import (
    Layer6RiskEngine,
    run_mean_reversion_backtest,
)


class MeanReversionResearchTests(unittest.TestCase):
    def test_rejects_invalid_prices_and_parameters(self):
        with self.assertRaises(ValueError):
            run_mean_reversion_backtest([1.0, float("nan"), 2.0])
        with self.assertRaises(ValueError):
            run_mean_reversion_backtest([1.0, 2.0], window=1)
        with self.assertRaises(ValueError):
            run_mean_reversion_backtest([1.0, 2.0], per_side_cost_bps=-1)
        with self.assertRaises(ValueError):
            run_mean_reversion_backtest([1.0, 2.0], opens=[1.0])
        with self.assertRaises(ValueError):
            run_mean_reversion_backtest([1.0, 2.0], opens=[1.0, float("inf")])

    def test_no_signal_is_valid_empty_result(self):
        result = run_mean_reversion_backtest([100.0] * 30, window=10)
        self.assertEqual(result.trades, ())
        self.assertEqual(result.expectancy, 0.0)
        self.assertIsNone(result.profit_factor)

    def test_metrics_are_finite_for_oscillating_series(self):
        prices = [100 + math.sin(i / 2) * 3 for i in range(200)]
        result = run_mean_reversion_backtest(prices, window=15, z_threshold=0.9)
        self.assertTrue(result.trades)
        self.assertTrue(all(math.isfinite(t.net_return) for t in result.trades))
        self.assertTrue(math.isfinite(result.expectancy))
        self.assertTrue(math.isfinite(result.max_drawdown))
        self.assertTrue(math.isfinite(result.ulcer_index))

    def test_cost_sensitivity_charges_two_sides_per_completed_trade(self):
        prices = [100 + math.sin(i / 2) * 3 for i in range(200)]
        zero_cost = run_mean_reversion_backtest(
            prices, window=15, z_threshold=0.9, per_side_cost_bps=0.0
        )
        paid_cost = run_mean_reversion_backtest(
            prices, window=15, z_threshold=0.9, per_side_cost_bps=5.0
        )
        self.assertEqual(len(zero_cost.trades), len(paid_cost.trades))
        self.assertTrue(zero_cost.trades)
        for free, paid in zip(zero_cost.trades, paid_cost.trades):
            self.assertAlmostEqual(free.gross_return, paid.gross_return)
            self.assertAlmostEqual(paid.cost_return - free.cost_return, 0.001)
            self.assertAlmostEqual(free.net_return - paid.net_return, 0.001)

    def test_risk_guard_halts_and_rejects_additional_exposure(self):
        risk = Layer6RiskEngine(0.02, 1.0, 100.0, 0.05)
        self.assertTrue(risk.validate_net_position(0.25, 0.25))
        self.assertFalse(risk.validate_net_position(0.9, 0.2))
        self.assertFalse(risk.validate_net_position(float("nan"), 0.1))
        self.assertTrue(risk.check_circuit_breaker(97.0))
        self.assertFalse(risk.validate_net_position(0.0, 0.1))

    def test_invalid_risk_configuration_rejected(self):
        with self.assertRaises(ValueError):
            Layer6RiskEngine(0.0, 1.0, 100.0)
        with self.assertRaises(ValueError):
            Layer6RiskEngine(0.02, float("inf"), 100.0)

    def test_halt_is_sticky_and_bad_equity_fails_closed(self):
        risk = Layer6RiskEngine(0.02, 1.0, 100.0, 0.05)
        self.assertTrue(risk.check_circuit_breaker(float("nan")))
        self.assertTrue(risk.halted)
        self.assertTrue(risk.check_circuit_breaker(100.0))


if __name__ == "__main__":
    unittest.main()
