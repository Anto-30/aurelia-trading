import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

from research.labs.liquidity_sweep_strategy import OHLCBar, ResearchSignal
from research.labs.liquidity_sweep_backtest import (
    BacktestConfig, run_backtest, run_walk_forward, load_verified_cost_config,
)

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_bars(rows):
    return [OHLCBar((START + timedelta(minutes=i)).isoformat().replace("+00:00", "Z"), *row)
            for i, row in enumerate(rows)]


def signal(entry_index=2):
    pivot_index = max(0, entry_index - 2)
    return ResearchSignal("long", pivot_index, pivot_index, entry_index - 1,
                          entry_index, 100, 95, 110, 99, 2.0)


class CostAwareBacktestTests(unittest.TestCase):
    def test_target_exit_charges_commission(self):
        bars = make_bars([(100,101,99,100), (100,102,99,100), (100,102,99,100), (100,111,99,108)])
        result = run_backtest(bars, [signal()], BacktestConfig(1000, 1, 0.5, 0, 1.0))
        self.assertEqual(result.metrics["total_trades"], 1)
        self.assertEqual(result.trade_ledger[0]["exit_reason"], "TARGET")
        self.assertAlmostEqual(result.trade_ledger[0]["net_pnl"], 9.0)

    def test_stop_wins_when_stop_and_target_touch_same_bar(self):
        bars = make_bars([(100,101,99,100), (100,102,99,100), (100,102,99,100), (100,111,94,100)])
        result = run_backtest(bars, [signal()], BacktestConfig(1000, 1, 0, 0, 1.0))
        self.assertEqual(result.trade_ledger[0]["exit_reason"], "STOP")
        self.assertAlmostEqual(result.trade_ledger[0]["net_pnl"], -5.0)

    def test_gap_through_stop_uses_open_price(self):
        bars = make_bars([(100,101,99,100), (100,102,99,100), (100,102,99,100), (90,91,89,90)])
        result = run_backtest(bars, [signal()], BacktestConfig(1000, 1, 0, 0, 1.0))
        self.assertAlmostEqual(result.trade_ledger[0]["exit_price"], 90.0)

    def test_overlapping_signal_rejected(self):
        bars = make_bars([(100,101,99,100), (100,102,99,100), (100,102,99,100), (100,111,99,108), (108,109,107,108)])
        result = run_backtest(bars, [signal(2), signal(3)], BacktestConfig(1000, 1, 0, 0, 1.0))
        self.assertEqual(result.metrics["total_trades"], 1)
        self.assertEqual(result.rejection_ledger[0]["reason"], "OVERLAPPING_POSITION")

    def test_walk_forward_folds_are_chronological(self):
        bars = make_bars([(100,101,99,100)] * 7)
        folds = run_walk_forward(bars, lambda train, test: [], BacktestConfig(1000,1,0,0,1.0),
                                 train_window=3, test_window=2)
        self.assertEqual(len(folds), 2)
        self.assertLess(folds[0]["test_end"], folds[1]["test_start"])


    def test_point_costs_are_applied_once_per_side_and_commission_scales_with_quantity(self):
        bars = make_bars([
            (100,101,99,100), (100,102,99,100),
            (100,102,99,100), (100,111,99,108),
        ])
        result = run_backtest(
            bars, [signal()], BacktestConfig(
                1000, 2, 0.5, 0, 1.0, spread_points=2, slippage_points=1
            )
        )
        trade = result.trade_ledger[0]
        self.assertAlmostEqual(trade["gross_pnl"], 20.0)
        self.assertAlmostEqual(trade["execution_cost"], 8.0)
        self.assertAlmostEqual(trade["commission"], 2.0)
        self.assertAlmostEqual(trade["net_pnl"], 10.0)

    def test_unknown_or_unverified_cost_config_fails_closed(self):
        config = Path(__file__).resolve().parents[3] / "config" / "costs.yaml"
        with self.assertRaisesRegex(ValueError, "COST_CONFIG_NOT_SOURCE_VERIFIED"):
            load_verified_cost_config(str(config), "1m")

    def test_verified_cost_loader_requires_all_fields_and_source_timestamp(self):
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "costs.yaml"
            observed = datetime.now(timezone.utc).isoformat()
            config.write_text("\n".join([
                "schema_version: 1",
                "instrument: R_100",
                "status: VERIFIED_SOURCE_BACKED_COSTS",
                "max_slippage_sensitivity_multiplier: 2.0",
                "pnl_model: LINEAR_INDEX_POINT_VALUE",
                "bar_price_basis: MIDPOINT",
                'contract_type: "test linear contract"',
                "usd_per_point_per_unit: 1.0",
                "economics_verified: true",
                'economics_source: "test contract spec"',
                f'economics_observed_at_utc: "{observed}"',
                "resolutions:",
                '  "1m":',
                "    spread_points: 1.0",
                "    slippage_points: 1.5",
                "    commission_per_unit_usd_per_side: 0.1",
                "    verified: true",
                "    spread_status: VERIFIED_MEASURED",
                "    commission_status: VERIFIED_MEASURED",
                '    source: "source-backed paper quote capture"',
                f'    observed_at_utc: "{observed}"',
                "    slippage_status: VERIFIED_MEASURED",
            ]) + "\n", encoding="utf-8")
            loaded = load_verified_cost_config(str(config), "1m")
            self.assertEqual(loaded["spread_points"], 1.0)
            self.assertEqual(loaded["slippage_points"], 1.5)
            self.assertEqual(loaded["commission_per_unit_usd_per_side"], 0.1)
            self.assertEqual(loaded["max_slippage_sensitivity_multiplier"], 2.0)

    def test_invalid_configuration_rejected(self):
        with self.assertRaises(ValueError):
            BacktestConfig(1000, 0, 0, 0, 1.0)


if __name__ == "__main__":
    unittest.main()
