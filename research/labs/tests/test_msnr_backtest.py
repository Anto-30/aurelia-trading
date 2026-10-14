import unittest

from research.labs.msnr_backtest import (
    BacktestConfig, BacktestInputError, Candle, TradeSignal, run_backtest,
)


def bars(rows):
    return tuple(Candle(i, *row) for i, row in enumerate(rows))


class EventDrivenBacktestTests(unittest.TestCase):
    def test_entry_occurs_on_next_open_not_signal_close(self):
        candles = bars([(100, 101, 99, 100), (110, 112, 109, 111), (112, 114, 111, 113)])
        result = run_backtest(candles, [TradeSignal(0, "LONG", 5, 10, 0.60)])
        self.assertEqual(result.trades[0].entry_index, 1)
        self.assertEqual(result.trades[0].entry_price, 110)

    def test_spread_slippage_and_commission_reduce_pnl(self):
        candles = bars([(100, 101, 99, 100), (100, 112, 99, 110)])
        signal = TradeSignal(0, "LONG", 5, 10, 0.60)
        no_cost = run_backtest(candles, [signal])
        with_cost = run_backtest(candles, [signal], BacktestConfig(
            spread=2, slippage_per_fill=0.5, commission_per_unit_round_trip=1
        ))
        self.assertLess(with_cost.trades[0].net_pnl, no_cost.trades[0].net_pnl)

    def test_stop_wins_when_stop_and_target_hit_same_bar(self):
        candles = bars([(100, 101, 99, 100), (100, 112, 88, 100)])
        result = run_backtest(candles, [TradeSignal(0, "LONG", 5, 10, 0.60)])
        self.assertEqual(result.trades[0].exit_reason, "STOP")
        self.assertEqual(result.trades[0].net_pnl, -5)

    def test_probability_outside_policy_is_rejected_not_clipped(self):
        candles = bars([(100, 101, 99, 100), (100, 101, 99, 100)])
        result = run_backtest(candles, [TradeSignal(0, "LONG", 5, 10, 0.82)])
        self.assertEqual(result.trades, ())
        self.assertEqual(result.skipped_signals, ((0, "PROBABILITY_OUT_OF_POLICY"),))

    def test_short_stop_and_target(self):
        candles = bars([(100, 101, 99, 100), (100, 101, 88, 90)])
        result = run_backtest(candles, [TradeSignal(0, "SHORT", 5, 10, 0.60)])
        self.assertEqual(result.trades[0].exit_reason, "TARGET")
        self.assertEqual(result.trades[0].net_pnl, 10)

    def test_signal_during_open_position_is_skipped(self):
        candles = bars([
            (100, 101, 99, 100), (100, 102, 99, 101),
            (101, 102, 99, 100), (100, 111, 99, 110),
        ])
        signals = [TradeSignal(0, "LONG", 20, 30, 0.60), TradeSignal(1, "SHORT", 5, 10, 0.60)]
        result = run_backtest(candles, signals)
        self.assertEqual(result.skipped_signals, ((1, "POSITION_ALREADY_OPEN"),))

    def test_invalid_ohlc_and_duplicate_signal_fail_closed(self):
        with self.assertRaisesRegex(BacktestInputError, "CANDLE_OHLC_INVALID"):
            run_backtest(bars([(100, 99, 98, 100), (100, 101, 99, 100)]), [])
        candles = bars([(100, 101, 99, 100), (100, 101, 99, 100)])
        with self.assertRaisesRegex(BacktestInputError, "DUPLICATE_SIGNAL_INDEX"):
            run_backtest(candles, [
                TradeSignal(0, "LONG", 1, 1, 0.60), TradeSignal(0, "SHORT", 1, 1, 0.60),
            ])

    def test_signal_without_following_bar_is_rejected(self):
        candles = bars([(100, 101, 99, 100), (100, 101, 99, 100)])
        with self.assertRaisesRegex(BacktestInputError, "SIGNAL_REQUIRES_A_FOLLOWING_CANDLE"):
            run_backtest(candles, [TradeSignal(1, "LONG", 1, 1, 0.60)])

    def test_empty_trade_set_has_defined_metrics(self):
        candles = bars([(100, 101, 99, 100), (100, 101, 99, 100)])
        result = run_backtest(candles, [])
        self.assertEqual(result.win_rate, 0.0)
        self.assertEqual(result.expectancy, 0.0)
        self.assertIsNone(result.profit_factor)


if __name__ == "__main__":
    unittest.main()
