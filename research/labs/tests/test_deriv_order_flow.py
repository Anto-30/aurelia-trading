import unittest

from research.labs.deriv_order_flow import (
    LabelEvent,
    OrderFlowDataError,
    PriceBar,
    Tick,
    compute_tick_features,
    detect_price_delta_divergence,
    label_triple_barrier,
    parse_live_tick_response,
    parse_ticks_history_response,
    tick_frequency_context,
)


class DerivTickSchemaTests(unittest.TestCase):
    def test_parses_documented_history_prices_and_times_without_fabricated_volume(self):
        rows = parse_ticks_history_response({
            "msg_type": "history",
            "history": {"prices": [100.0, 100.2, 100.1], "times": [10, 11, 12]},
            "pip_size": 2,
        })
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1], Tick(timestamp=11.0, price=100.2))
        self.assertFalse(hasattr(rows[0], "volume"))
        self.assertIsNone(rows[0].bid)
        self.assertIsNone(rows[0].ask)

    def test_history_array_length_mismatch_fails_closed(self):
        with self.assertRaisesRegex(OrderFlowDataError, "LENGTH_MISMATCH"):
            parse_ticks_history_response({"history": {"prices": [1.0, 2.0], "times": [1]}})

    def test_history_api_error_fails_closed(self):
        with self.assertRaisesRegex(OrderFlowDataError, "API_REQUEST_FAILED"):
            parse_ticks_history_response({"error": {"code": "InvalidSymbol"}})

    def test_live_bid_ask_is_optional_and_spread_is_computed_only_when_present(self):
        price_only = parse_live_tick_response({"tick": {"epoch": 100, "quote": 1.25, "pip_size": 2}})
        quoted = parse_live_tick_response({"tick": {"epoch": 100, "quote": 1.25, "bid": 1.24, "ask": 1.26}})
        self.assertIsNone(price_only.bid)
        self.assertIsNone(price_only.ask)
        self.assertAlmostEqual(compute_tick_features([quoted])[0].spread, 0.02)

    def test_invalid_spread_fails_closed(self):
        with self.assertRaisesRegex(OrderFlowDataError, "ASK_BELOW_BID"):
            parse_live_tick_response({"tick": {"epoch": 100, "quote": 1.25, "bid": 1.26, "ask": 1.24}})


class TickProxyFeatureTests(unittest.TestCase):
    def test_flat_ticks_have_zero_weight_and_rolling_windows_are_time_based(self):
        ticks = [
            Tick(0, 100.0),
            Tick(10, 100.1),
            Tick(20, 100.1),
            Tick(61, 100.0),
            Tick(901, 100.2),
        ]
        rows = compute_tick_features(ticks)
        self.assertEqual([x.tick_direction for x in rows], [0, 1, 0, -1, 1])
        self.assertEqual(rows[2].cumulative_signed_tick_count, 1)
        self.assertEqual(rows[3].signed_tick_count_60s, 0)
        self.assertEqual(rows[4].signed_tick_count_900s, 1)
        self.assertEqual(rows[4].tick_count_900s, 4)

    def test_out_of_order_ticks_are_rejected(self):
        with self.assertRaisesRegex(OrderFlowDataError, "NONDECREASING"):
            compute_tick_features([Tick(2, 1.0), Tick(1, 1.1)])

    def test_tick_frequency_context_is_marked_as_proxy(self):
        ticks = [
            Tick(0, 100.0), Tick(1, 100.0), Tick(2, 100.0),
            Tick(3, 101.0), Tick(4, 102.0), Tick(5, 101.0),
            Tick(6, 100.0),
        ]
        result = tick_frequency_context(ticks, 6, lookback_seconds=20, bin_width=1.0)
        self.assertEqual(result.price_bin, 100)
        self.assertEqual(result.occupied_bins, 3)
        self.assertIn("PROXY", result.status)

    def test_tick_frequency_context_does_not_include_future_ticks(self):
        ticks = [Tick(0, 100.0), Tick(1, 101.0), Tick(2, 100.0), Tick(100, 105.0)]
        before = tick_frequency_context(ticks, 2, lookback_seconds=20, bin_width=1.0)
        prefix_only = tick_frequency_context(ticks[:3], 2, lookback_seconds=20, bin_width=1.0)
        self.assertEqual(before, prefix_only)

    def test_causal_delta_divergence_detects_new_extremes(self):
        bearish = detect_price_delta_divergence([100, 101, 100.5, 102], [0, 3, 2, 1], lookback=3)
        bullish = detect_price_delta_divergence([100, 99, 99.5, 98], [0, -3, -2, -1], lookback=3)
        self.assertEqual(bearish, "BEARISH_PRICE_DELTA_DIVERGENCE_PROXY")
        self.assertEqual(bullish, "BULLISH_PRICE_DELTA_DIVERGENCE_PROXY")


def bars(rows):
    return tuple(PriceBar(float(i), *row) for i, row in enumerate(rows))


class TripleBarrierTests(unittest.TestCase):
    def test_signal_uses_next_bar_open_and_profit_first_touch(self):
        data = bars([(100, 101, 99, 100), (110, 120, 109, 118), (118, 119, 117, 118)])
        labels = label_triple_barrier(data, [LabelEvent(0, "LONG")], [1.0, 1.0, 1.0],
                                      pt_sl=(1.5, 1.0), max_horizon=2)
        self.assertEqual(labels[0].entry_index, 1)
        self.assertEqual(labels[0].entry_price, 110)
        self.assertEqual(labels[0].touch, "PROFIT_TARGET")
        self.assertEqual(labels[0].label, 1)
        self.assertEqual(labels[0].exit_price, 111.5)

    def test_stop_wins_if_both_barriers_are_touched_inside_same_bar(self):
        data = bars([(100, 101, 99, 100), (100, 103, 97, 100), (100, 101, 99, 100)])
        labels = label_triple_barrier(data, [LabelEvent(0, "LONG")], [1.0, 1.0, 1.0],
                                      pt_sl=(1.5, 1.0), max_horizon=1)
        self.assertEqual(labels[0].touch, "STOP_LOSS")
        self.assertEqual(labels[0].label, -1)

    def test_stop_gap_is_filled_at_worse_open(self):
        data = bars([(100, 101, 99, 100), (100, 101, 96, 100), (88, 89, 87, 88)])
        labels = label_triple_barrier(data, [LabelEvent(0, "LONG")], [1.0, 1.0, 1.0],
                                      pt_sl=(3.0, 1.0), max_horizon=2)
        self.assertEqual(labels[0].touch, "STOP_LOSS")
        self.assertEqual(labels[0].exit_price, 88)

    def test_vertical_barrier_uses_signed_return_and_full_horizon(self):
        data = bars([(100, 101, 99, 100), (100, 101, 99, 100), (100, 102, 99, 101),
                     (101, 102, 100, 101)])
        labels = label_triple_barrier(data, [LabelEvent(0, "LONG")], [10.0, 10.0, 10.0, 10.0],
                                      pt_sl=(5.0, 5.0), max_horizon=3)
        self.assertEqual(labels[0].touch, "VERTICAL")
        self.assertEqual(labels[0].exit_index, 3)
        self.assertEqual(labels[0].label, 1)

    def test_unfinished_vertical_horizon_is_omitted_when_no_barrier_touched(self):
        data = bars([(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100)])
        labels = label_triple_barrier(data, [LabelEvent(0, "LONG")], [10.0, 10.0, 10.0],
                                      pt_sl=(5.0, 5.0), max_horizon=4)
        self.assertEqual(labels, ())

    def test_invalid_target_and_duplicate_events_are_rejected(self):
        data = bars([(100, 101, 99, 100), (100, 101, 99, 100)])
        with self.assertRaisesRegex(OrderFlowDataError, "TARGET_VOLATILITY_MUST_BE_POSITIVE"):
            label_triple_barrier(data, [LabelEvent(0, "LONG")], [0.0, 1.0])
        with self.assertRaisesRegex(OrderFlowDataError, "DUPLICATE_LABEL_EVENT"):
            label_triple_barrier(data, [LabelEvent(0, "LONG"), LabelEvent(0, "SHORT")], [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
