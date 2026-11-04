from __future__ import annotations

import unittest

from research.entry_confirmation_backtest import (
    BacktestCostModel,
    ExitPolicy,
    compute_risk_metrics,
    chronological_split_indices,
    evaluate_filter_efficacy,
    simulate_trade,
)
from research.labs.deterministic_intraday_strategies import (
    MSNRConfirmationVerdict,
    StrategyBar,
)


def bar(index, open_, high, low, close):
    from datetime import datetime, timedelta, timezone
    stamp = datetime(2026, 10, 10, tzinfo=timezone.utc) + timedelta(minutes=index)
    return StrategyBar(stamp.isoformat(), open_, high, low, close)


class BacktestPolicyTests(unittest.TestCase):
    def test_exit_policy_requires_explicit_positive_max_hold_and_supported_exit_modes(self):
        with self.assertRaisesRegex(ValueError, "MAX_HOLD_BARS_REQUIRED"):
            ExitPolicy(max_hold_bars=0, breakeven_trigger_r=None, trailing_method="none")
        with self.assertRaisesRegex(ValueError, "TRAILING_STOP_METHOD_UNSUPPORTED"):
            ExitPolicy(max_hold_bars=10, breakeven_trigger_r=None, trailing_method="atr")

    def test_cost_model_requires_explicit_source_and_finite_nonnegative_costs(self):
        with self.assertRaisesRegex(ValueError, "COST_SOURCE_REQUIRED"):
            BacktestCostModel(
                tick_size=0.1,
                slippage_ticks_per_side=1.0,
                commission_price_units_round_trip=0.0,
                cost_source="",
            )
        with self.assertRaisesRegex(ValueError, "COST_ASSUMPTION_INVALID"):
            BacktestCostModel(
                tick_size=0.1,
                slippage_ticks_per_side=-1.0,
                commission_price_units_round_trip=0.0,
                cost_source="documented fixture",
            )

    def test_long_trade_uses_next_open_stop_target_and_round_trip_costs(self):
        bars = [
            bar(0, 100, 101, 99, 100),
            bar(1, 100, 102, 99, 101),
            bar(2, 101, 103, 100, 102),
        ]
        verdict = MSNRConfirmationVerdict(
            signal_valid=True,
            reason="PASSED",
            direction="LONG",
            stop_reference_price=99.0,
            target_reference_price=103.0,
        )
        result = simulate_trade(
            bars,
            signal_index=0,
            verdict=verdict,
            exit_policy=ExitPolicy(
                max_hold_bars=2,
                breakeven_trigger_r=None,
                trailing_method="none",
            ),
            costs=BacktestCostModel(
                tick_size=0.1,
                slippage_ticks_per_side=1.0,
                commission_price_units_round_trip=0.05,
                cost_source="test fixture, not Deriv quote evidence",
            ),
        )
        self.assertEqual(result.entry_index, 1)
        self.assertEqual(result.exit_reason, "TIME_EXIT")
        self.assertAlmostEqual(result.entry_price, 100.1)
        self.assertAlmostEqual(result.net_r_multiple, (102.0 - 100.1 - 0.1 - 0.05) / 1.1)
        self.assertFalse(result.capital_authority)
        self.assertFalse(result.order_submission_permitted)

    def test_same_bar_stop_and_target_uses_conservative_stop_first(self):
        bars = [
            bar(0, 100, 101, 99, 100),
            bar(1, 100, 104, 98, 102),
        ]
        verdict = MSNRConfirmationVerdict(
            signal_valid=True,
            reason="PASSED",
            direction="LONG",
            stop_reference_price=99.0,
            target_reference_price=103.0,
        )
        result = simulate_trade(
            bars,
            signal_index=0,
            verdict=verdict,
            exit_policy=ExitPolicy(1, None, "none"),
            costs=BacktestCostModel(0.1, 0.0, 0.0, "fixture"),
        )
        self.assertEqual(result.exit_reason, "STOP")
        self.assertAlmostEqual(result.gross_r_multiple, -1.0)

    def test_missing_next_bar_or_nonrewarding_stop_rejects_trade_simulation(self):
        verdict = MSNRConfirmationVerdict(
            True, "PASSED", "LONG",
            stop_reference_price=101.0,
            target_reference_price=103.0,
        )
        with self.assertRaisesRegex(ValueError, "NEXT_BAR_ENTRY_UNAVAILABLE"):
            simulate_trade(
                [bar(0, 100, 101, 99, 100)],
                signal_index=0,
                verdict=verdict,
                exit_policy=ExitPolicy(1, None, "none"),
                costs=BacktestCostModel(0.1, 0, 0, "fixture"),
            )
        with self.assertRaisesRegex(ValueError, "INITIAL_RISK_INVALID"):
            simulate_trade(
                [bar(0, 100, 101, 99, 100), bar(1, 100, 101, 99, 100)],
                signal_index=0,
                verdict=verdict,
                exit_policy=ExitPolicy(1, None, "none"),
                costs=BacktestCostModel(0.1, 0, 0, "fixture"),
            )

    def test_profit_factor_expectancy_drawdown_and_r_distribution_are_computed(self):
        metrics = compute_risk_metrics([1.5, -1.0, 2.0, -0.5])
        self.assertAlmostEqual(metrics.expectancy_r, 0.5)
        self.assertAlmostEqual(metrics.profit_factor, 3.5 / 1.5)
        self.assertAlmostEqual(metrics.max_drawdown_r, 1.0)
        self.assertEqual(metrics.trade_count, 4)
        self.assertLessEqual(metrics.r_p05, metrics.r_median)
        self.assertLessEqual(metrics.r_median, metrics.r_p95)

    def test_filter_efficacy_reports_rejected_loss_rate_over_accepted_loss_rate(self):
        efficacy = evaluate_filter_efficacy(
            accepted_r_multiples=[1.0, 2.0, -1.0, 1.5],
            rejected_counterfactual_r_multiples=[-1.0, -0.5, -1.0, 0.2],
        )
        self.assertAlmostEqual(efficacy.accepted_loss_rate, 0.25)
        self.assertAlmostEqual(efficacy.rejected_loss_rate, 0.75)
        self.assertAlmostEqual(efficacy.filter_efficacy_ratio, 3.0)
        self.assertEqual(efficacy.rejected_signal_count, 4)

    def test_filter_efficacy_is_unavailable_when_a_comparison_pool_is_empty(self):
        result = evaluate_filter_efficacy(
            accepted_r_multiples=[1.0, 2.0],
            rejected_counterfactual_r_multiples=[],
        )
        self.assertIsNone(result.filter_efficacy_ratio)
        self.assertEqual(result.status, "INSUFFICIENT_COUNTERFACTUAL_SAMPLE")

    def test_chronological_split_has_strict_train_validation_test_order_and_embargo(self):
        split = chronological_split_indices(1000, embargo_bars=10)
        self.assertEqual(split.train_start, 0)
        self.assertEqual(split.train_end, 600)
        self.assertEqual(split.validation_start, 610)
        self.assertEqual(split.validation_end, 790)
        self.assertEqual(split.test_start, 810)
        self.assertEqual(split.test_end, 1000)
        self.assertLess(split.train_end, split.validation_start)
        self.assertLess(split.validation_end, split.test_start)

    def test_research_backtest_objects_never_grant_capital_authority(self):
        verdict = MSNRConfirmationVerdict(True, "PASSED", "LONG")
        self.assertFalse(verdict.capital_authority)
        self.assertFalse(verdict.order_submission_permitted)


if __name__ == "__main__":
    unittest.main()
