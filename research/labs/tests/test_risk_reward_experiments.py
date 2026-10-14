from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta

from research.labs.risk_reward_experiments import (
    CostComponent, ExitPolicy, NormalizedBar, TradePath, block_bootstrap_mean_ci,
    compare_exit_policies, simulate_exit, standard_exit_policies,
)

NOW = datetime.now(timezone.utc).replace(microsecond=0)

def stamp(offset: int) -> str:
    return (NOW + timedelta(minutes=offset)).isoformat().replace("+00:00", "Z")

def cost(component_id="spread", amount=0.02):
    return CostComponent(component_id, component_id, amount, "USD", "STRESS_ASSUMPTION",
                         "fixture:cost-observation", stamp(0), "LOW",
                         "Synthetic unit-test fixture; not actual execution-cost evidence.")

def path(signal="s1", bars=None, costs_complete=True, cost_components=None, payoff="LINEAR_R_PATH", required_cost_components=("spread",)):
    return TradePath(
        signal_id=signal, strategy_id="TEST_STRATEGY", instrument_id="TEST_LINEAR",
        timeframe="1m", regime="TEST", entry_timestamp_utc=stamp(-1),
        initial_risk_cash=1.0, account_currency="USD", payoff_model=payoff,
        instrument_spec_ref="fixture:instrument-spec-v1", data_hash="sha256:fixture-data",
        required_cost_components=tuple(required_cost_components), bars=tuple(bars or [NormalizedBar(stamp(1), 0.0, 0.8, -0.4, 0.5),
                            NormalizedBar(stamp(2), 0.5, 1.4, 0.2, 1.2)]),
        cost_components=tuple(cost_components if cost_components is not None else [cost()]),
        costs_complete=costs_complete, unknown_cost_components=() if costs_complete else ("latency_slippage",),
    )

class RiskRewardExperimentTests(unittest.TestCase):
    def test_candidate_ratios_include_required_grid(self):
        ids = {p.policy_id for p in standard_exit_policies()}
        for ratio in ("1R", "1.25R", "1.5R", "1.75R", "2R", "2.5R", "3R"):
            self.assertIn(f"FIXED_{ratio}", ids)

    def test_fixed_target_and_costed_net_expectancy(self):
        result = simulate_exit(path(), ExitPolicy("fixed_1r", target_r=1.0))
        self.assertEqual(result.exit_reason, "TARGET")
        self.assertAlmostEqual(result.exit_r, 1.0)
        self.assertAlmostEqual(result.net_r, 0.98)
        self.assertAlmostEqual(result.net_cash, 0.98)

    def test_stop_target_collision_is_resolved_adversely(self):
        bars = [NormalizedBar(stamp(1), 0.0, 1.5, -1.2, 0.1)]
        result = simulate_exit(path(bars=bars), ExitPolicy("collision", target_r=1.0))
        self.assertEqual(result.exit_reason, "STOP")
        self.assertAlmostEqual(result.exit_r, -1.0)

    def test_gap_through_stop_fills_at_open(self):
        bars = [NormalizedBar(stamp(1), -1.3, -1.0, -1.5, -1.2)]
        result = simulate_exit(path(bars=bars), ExitPolicy("gap", target_r=2.0))
        self.assertEqual(result.exit_reason, "STOP_GAP")
        self.assertAlmostEqual(result.exit_r, -1.3)

    def test_trailing_update_applies_next_bar_only(self):
        bars = [NormalizedBar(stamp(1), 0.0, 2.0, -0.2, 1.5),
                NormalizedBar(stamp(2), 1.2, 1.4, 0.2, 0.4)]
        result = simulate_exit(path(bars=bars), ExitPolicy("trail", trailing_activation_r=1.0, trailing_distance_r=1.0))
        self.assertEqual(result.exit_reason, "STOP")
        self.assertAlmostEqual(result.exit_r, 1.0)
        self.assertEqual(result.duration_bars, 2)

    def test_break_even_trigger_does_not_retroactively_change_same_bar_stop(self):
        bars = [NormalizedBar(stamp(1), 0.0, 1.2, -1.1, 0.1),
                NormalizedBar(stamp(2), 0.1, 0.2, -0.1, 0.0)]
        result = simulate_exit(path(bars=bars), ExitPolicy("be", break_even_trigger_r=1.0))
        self.assertEqual(result.exit_reason, "STOP")
        self.assertAlmostEqual(result.exit_r, -1.0)

    def test_incomplete_costs_never_report_net_expectancy(self):
        result = compare_exit_policies([path(costs_complete=False)], [ExitPolicy("fixed", target_r=1.0)], bootstrap_replicates=100)["fixed"]
        self.assertEqual(result["status"], "COST_INCOMPLETE")
        self.assertIsNone(result["net_expectancy_r"])
        self.assertIsNone(result["net_profit_factor"])

    def test_embedded_cost_is_not_counted_twice(self):
        embedded = CostComponent("embedded", "spread", .04, "USD", "STRESS_ASSUMPTION",
                                 "fixture:embedded", stamp(0), "LOW", "Synthetic test fixture.", True)
        result = simulate_exit(path(cost_components=[embedded, cost("commission", .01)],
                                    required_cost_components=("spread", "commission")),
                               ExitPolicy("fixed", target_r=1.0))
        self.assertAlmostEqual(result.known_cost_cash, 0.01)
        self.assertAlmostEqual(result.net_r, 0.99)

    def test_cost_completeness_requires_all_instrument_declared_components(self):
        with self.assertRaisesRegex(ValueError, "REQUIRED_COST_COMPONENTS_UNACCOUNTED"):
            path(cost_components=[cost("commission")],
                 required_cost_components=("spread", "commission")).validate()

    def test_fixed_payout_contract_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "PAYOFF_MODEL_NOT_SUPPORTED"):
            path(payoff="FIXED_PAYOUT").validate()

    def test_bad_timestamps_duplicate_signals_and_nonfinite_inputs_fail_closed(self):
        bad = [NormalizedBar("2026-10-14T12:00:00", 0.0, 1.0, -1.0, 0.0)]
        with self.assertRaisesRegex(ValueError, "TIMEZONE_AWARE"):
            simulate_exit(path(bars=bad), ExitPolicy("fixed", target_r=1.0))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ENTRY_SIGNAL_ID"):
            compare_exit_policies([path(), path()], [ExitPolicy("fixed", target_r=1.0)], bootstrap_replicates=100)
        bad_inf = [NormalizedBar(stamp(1), 0, float("inf"), -1, 0)]
        with self.assertRaisesRegex(ValueError, "NON_FINITE"):
            simulate_exit(path(bars=bad_inf), ExitPolicy("fixed", target_r=1.0))

    def test_comparison_uses_exact_same_entries_and_bootstrap_is_deterministic(self):
        paths = [path("s1"), path("s2", bars=[NormalizedBar(stamp(1), 0, .5, -.2, .1)])]
        result = compare_exit_policies(paths, [ExitPolicy("fixed_1r", target_r=1.0), ExitPolicy("time", time_stop_bars=1)], bootstrap_replicates=100)
        self.assertEqual(result["fixed_1r"]["entry_signal_ids"], ["s1", "s2"])
        self.assertIsNotNone(result["fixed_1r"]["net_expectancy_block_bootstrap_ci95_r"])
        self.assertEqual(
            block_bootstrap_mean_ci([1, -.5, .4, -.1], replicates=100),
            block_bootstrap_mean_ci([1, -.5, .4, -.1], replicates=100),
        )

    def test_time_stop_and_unknown_costs_are_not_zeroed(self):
        result = simulate_exit(path(costs_complete=False, cost_components=[]),
                               ExitPolicy("time", time_stop_bars=1))
        self.assertEqual(result.exit_reason, "TIME_STOP")
        self.assertIsNone(result.net_r)

    def test_invalid_policy_rejected(self):
        with self.assertRaisesRegex(ValueError, "MUST_BE_POSITIVE"):
            ExitPolicy("bad", target_r=0).validate()
        with self.assertRaisesRegex(ValueError, "HAS_NO_EXIT_RULE"):
            ExitPolicy("bad").validate()

if __name__ == "__main__":
    unittest.main()
