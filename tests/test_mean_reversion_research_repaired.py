import math
import unittest

from research.labs.mean_reversion_research_repaired import (
    Layer6RiskEngine,
    _rolling_zscores,
    run_mean_reversion_backtest,
)


class MeanReversionResearchTests(unittest.TestCase):
    def test_rejects_invalid_prices_and_parameters(self):
        invalid_price_sets = (
            [1.0, float("nan"), 2.0],
            [1.0, float("inf")],
            [1.0, 0.0],
            [1.0, "bad"],
        )
        for values in invalid_price_sets:
            with self.subTest(values=values), self.assertRaises((ValueError, TypeError)):
                run_mean_reversion_backtest(values)
        with self.assertRaises(ValueError):
            run_mean_reversion_backtest([1.0, 2.0], window=1)
        with self.assertRaises(ValueError):
            run_mean_reversion_backtest([1.0, 2.0], window=True)
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

    def test_hand_calculated_trade_parity(self):
        # window=2 yields z=+/-1/sqrt(2) on non-flat pairs.
        # Signal at close[1] opens a short at open[2]=100; prior z turns
        # non-positive at close[2], so it exits at open[3]=90.
        # A long opens at open[4]=100 and is liquidated at final close=100.
        result = run_mean_reversion_backtest(
            [100.0, 110.0, 100.0, 90.0, 100.0],
            window=2,
            z_threshold=0.5,
            per_side_cost_bps=10.0,
        )
        self.assertEqual(len(result.trades), 2)
        first, second = result.trades
        self.assertEqual(first.direction, -1)
        self.assertAlmostEqual(first.entry_price, 100.0)
        self.assertAlmostEqual(first.exit_price, 90.0)
        self.assertAlmostEqual(first.gross_return, 0.10)
        self.assertAlmostEqual(first.cost_return, 0.002)
        self.assertAlmostEqual(first.net_return, 0.098)
        self.assertEqual(second.direction, 1)
        self.assertAlmostEqual(second.entry_price, 100.0)
        self.assertAlmostEqual(second.exit_price, 100.0)
        self.assertAlmostEqual(second.net_return, -0.002)
        self.assertAlmostEqual(result.expectancy, 0.048)
        self.assertAlmostEqual(result.profit_factor, 49.0)
        self.assertAlmostEqual(result.win_rate, 0.5)

    def test_rolling_zscores_are_prefix_stable(self):
        prices = [100, 110, 100, 90, 100, 110, 120, 110, 100]
        prefix = _rolling_zscores(prices[:5], 2)
        complete = _rolling_zscores(prices, 2)
        self.assertEqual(prefix, complete[:len(prefix)])

    def test_metrics_are_finite_for_oscillating_series(self):
        prices = [100 + math.sin(i / 2) * 3 for i in range(200)]
        result = run_mean_reversion_backtest(prices, window=15, z_threshold=0.9)
        self.assertTrue(result.trades)
        self.assertTrue(all(math.isfinite(t.net_return) for t in result.trades))
        self.assertTrue(math.isfinite(result.expectancy))
        self.assertTrue(math.isfinite(result.max_drawdown))
        self.assertTrue(math.isfinite(result.ulcer_index))
        self.assertTrue(math.isfinite(result.total_return))
        self.assertTrue(result.max_drawdown <= 0.0)

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

    def test_profit_factor_is_json_safe_when_no_trade_loses(self):
        result = run_mean_reversion_backtest(
            [100.0, 110.0, 100.0, 90.0, 100.0],
            window=2, z_threshold=0.5, per_side_cost_bps=0.0,
        )
        self.assertIsNone(result.profit_factor)

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
        with self.assertRaises(ValueError):
            Layer6RiskEngine(0.02, 1.0, True)

    def test_period_baselines_roll_explicitly_without_clearing_halt(self):
        risk = Layer6RiskEngine(0.05, 1.0, 100.0, 0.10)
        self.assertTrue(risk.roll_day_baseline(96.0))
        self.assertEqual(risk.start_of_day_equity, 96.0)
        self.assertTrue(risk.roll_week_baseline(96.0))
        self.assertEqual(risk.start_of_week_equity, 96.0)
        self.assertFalse(risk.check_circuit_breaker(93.5))
        self.assertTrue(risk.check_circuit_breaker(90.0))
        self.assertFalse(risk.roll_day_baseline(100.0))
        self.assertFalse(risk.roll_week_baseline(100.0))
        self.assertTrue(risk.halted)

    def test_halt_is_sticky_and_bad_equity_fails_closed(self):
        risk = Layer6RiskEngine(0.02, 1.0, 100.0, 0.05)
        self.assertTrue(risk.check_circuit_breaker(float("nan")))
        self.assertTrue(risk.halted)
        self.assertTrue(risk.check_circuit_breaker(100.0))


if __name__ == "__main__":
    unittest.main()
