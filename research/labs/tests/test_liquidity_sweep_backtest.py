import unittest
from datetime import datetime, timedelta, timezone

from research.labs.liquidity_sweep_strategy import OHLCBar, ResearchSignal
from research.labs.liquidity_sweep_backtest import BacktestConfig, run_backtest, run_walk_forward

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_bars(rows):
    return [OHLCBar((START + timedelta(minutes=i)).isoformat().replace("+00:00", "Z"), *row)
            for i, row in enumerate(rows)]


def signal(entry_index=1):
    return ResearchSignal("long", 0, 0, entry_index - 1, entry_index, 100, 95, 110, 99, 2.0)


class CostAwareBacktestTests(unittest.TestCase):
    def test_target_exit_charges_commission(self):
        bars = make_bars([(100,101,99,100), (100,102,99,100), (100,111,99,108), (108,109,107,108)])
        result = run_backtest(bars, [signal()], BacktestConfig(1000, 1, 0.5, 0))
        self.assertEqual(result.metrics["total_trades"], 1)
        self.assertEqual(result.trade_ledger[0]["exit_reason"], "TARGET")
        self.assertAlmostEqual(result.trade_ledger[0]["net_pnl"], 9.0)

    def test_stop_wins_when_stop_and_target_touch_same_bar(self):
        bars = make_bars([(100,101,99,100), (100,102,99,100), (100,111,94,100)])
        result = run_backtest(bars, [signal()], BacktestConfig(1000, 1, 0, 0))
        self.assertEqual(result.trade_ledger[0]["exit_reason"], "STOP")
        self.assertAlmostEqual(result.trade_ledger[0]["net_pnl"], -5.0)

    def test_gap_through_stop_uses_open_price(self):
        bars = make_bars([(100,101,99,100), (100,102,99,100), (90,91,89,90)])
        result = run_backtest(bars, [signal()], BacktestConfig(1000, 1, 0, 0))
        self.assertAlmostEqual(result.trade_ledger[0]["exit_price"], 90.0)

    def test_overlapping_signal_rejected(self):
        bars = make_bars([(100,101,99,100), (100,102,99,100), (100,111,99,108), (108,109,107,108)])
        result = run_backtest(bars, [signal(1), signal(2)], BacktestConfig(1000, 1, 0, 0))
        self.assertEqual(result.metrics["total_trades"], 1)
        self.assertEqual(result.rejection_ledger[0]["reason"], "OVERLAPPING_POSITION")

    def test_walk_forward_folds_are_chronological(self):
        bars = make_bars([(100,101,99,100)] * 7)
        folds = run_walk_forward(bars, lambda train, test: [], BacktestConfig(1000,1,0,0),
                                 train_window=3, test_window=2)
        self.assertEqual(len(folds), 2)
        self.assertLess(folds[0]["test_end"], folds[1]["test_start"])

    def test_invalid_configuration_rejected(self):
        with self.assertRaises(ValueError):
            BacktestConfig(1000, 0, 0, 0)


if __name__ == "__main__":
    unittest.main()
