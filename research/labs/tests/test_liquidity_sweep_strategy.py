import unittest
from datetime import datetime, timedelta, timezone

from research.labs.liquidity_sweep_strategy import (
    OHLCBar, generate_research_signals, resample_1m_to_15m, _parse_bar,
)


def bars_from_rows(rows):
    start = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    return [
        OHLCBar((start + timedelta(minutes=i)).isoformat().replace("+00:00", "Z"), o, h, l, c)
        for i, (o, h, l, c) in enumerate(rows)
    ]


def bullish_context():
    rows = [
        (2, 3, 2, 2.5), (3, 5, 3, 4), (4, 4, 1, 2),
        (3, 6, 3, 5), (5, 5, 2, 4), (7, 8, 5, 7), (6, 6, 3, 4),
    ]
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    return [
        OHLCBar((start + timedelta(minutes=15 * i)).isoformat().replace("+00:00", "Z"), o, h, l, c)
        for i, (o, h, l, c) in enumerate(rows)
    ]


class LiquiditySweepStrategyTests(unittest.TestCase):
    def test_empty_or_short_input_returns_no_signals(self):
        self.assertEqual(generate_research_signals([]), [])
        self.assertEqual(generate_research_signals([
            {"timestamp_utc": "2026-01-01T00:00:00Z",
             "open": 1, "high": 2, "low": 0, "close": 1}
        ]), [])

    def test_rejects_naive_timestamp(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            _parse_bar({"timestamp_utc": "2026-01-01T00:00:00",
                        "open": 1, "high": 2, "low": 0, "close": 1})

    def test_rejects_invalid_ohlc_and_nonfinite_values(self):
        with self.assertRaisesRegex(ValueError, "invalid OHLC"):
            _parse_bar({"timestamp_utc": "2026-01-01T00:00:00Z",
                        "open": 3, "high": 2, "low": 1, "close": 2})
        with self.assertRaisesRegex(ValueError, "finite"):
            _parse_bar({"timestamp_utc": "2026-01-01T00:00:00Z",
                        "open": float("nan"), "high": 2, "low": 0, "close": 1})

    def test_rejects_unsorted_timestamps(self):
        rows = [
            {"timestamp_utc": "2026-01-01T00:01:00Z",
             "open": 1, "high": 2, "low": 0, "close": 1},
            {"timestamp_utc": "2026-01-01T00:00:00Z",
             "open": 1, "high": 2, "low": 0, "close": 1},
            {"timestamp_utc": "2026-01-01T00:02:00Z",
             "open": 1, "high": 2, "low": 0, "close": 1},
            {"timestamp_utc": "2026-01-01T00:03:00Z",
             "open": 1, "high": 2, "low": 0, "close": 1},
            {"timestamp_utc": "2026-01-01T00:04:00Z",
             "open": 1, "high": 2, "low": 0, "close": 1},
        ]
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            generate_research_signals(rows, pivot_window=1)

    def test_confirmed_sweep_and_structure_break_emits_next_bar_entry(self):
        rows = [
            (10, 11, 9, 10),   # 0
            (9, 10, 8, 9),     # 1: pivot low
            (9, 10, 9, 9),     # 2: pivot low becomes confirmed
            (9, 10, 7, 9),     # 3: sweep below 8 and reclaim
            (10, 12, 10, 11),  # 4: future pivot high
            (11, 11, 10, 10),  # 5: pivot high becomes confirmed
            (11, 13, 10, 13),  # 6: structural close above 12
            (13, 14, 12, 13),  # 7: next-bar entry at open 13
            (13, 14, 12, 13),  # 8: trailing bar for sufficient input
        ]
        bars = bars_from_rows(rows)
        signals = generate_research_signals(
            bars, context_bars_15m=bullish_context(), pivot_window=1, reward_risk=2.0
        )
        self.assertTrue(any(s.direction == "long" for s in signals))
        signal = next(s for s in signals if s.direction == "long")
        self.assertEqual(signal.sweep_index, 3)
        self.assertEqual(signal.reclaim_index, 3)
        self.assertEqual(signal.confirmation_index, 6)
        self.assertEqual(signal.entry_index, 7)
        self.assertEqual(signal.entry_price, 13)
        self.assertGreater(signal.target_price, signal.entry_price)



    def test_confirmed_short_setup_respects_bearish_15m_context(self):
        original = [
            (10, 11, 9, 10), (9, 10, 8, 9), (9, 10, 9, 9),
            (9, 10, 7, 9), (10, 12, 10, 11), (11, 11, 10, 10),
            (11, 13, 10, 13), (13, 14, 12, 13), (13, 14, 12, 13),
        ]
        mirrored = [(30 - o, 30 - low, 30 - high, 30 - close)
                    for o, high, low, close in original]
        candles = bars_from_rows(mirrored)
        bearish = [
            OHLCBar(bar.timestamp_utc, 30 - bar.open, 30 - bar.low,
                    30 - bar.high, 30 - bar.close)
            for bar in bullish_context()
        ]
        signals = generate_research_signals(
            candles, context_bars_15m=bearish, pivot_window=1, reward_risk=2.0
        )
        self.assertTrue(any(signal.direction == "short" for signal in signals))
        signal = next(signal for signal in signals if signal.direction == "short")
        self.assertEqual(signal.confirmation_index, 6)
        self.assertEqual(signal.entry_index, 7)
        self.assertLess(signal.target_price, signal.entry_price)

    def test_sufficient_input_requires_completed_15m_context(self):
        rows = [
            (10, 11, 9, 10), (9, 10, 8, 9), (9, 10, 9, 9),
            (9, 10, 7, 9), (10, 12, 10, 11), (11, 11, 10, 10),
            (11, 13, 10, 13), (13, 14, 12, 13), (13, 14, 12, 13),
        ]
        with self.assertRaisesRegex(ValueError, "context_bars_15m are required"):
            generate_research_signals(bars_from_rows(rows), pivot_window=1)

    def test_short_unsorted_input_is_still_rejected(self):
        rows = [
            {"timestamp_utc": "2026-01-01T00:01:00Z", "open": 1, "high": 2, "low": 0, "close": 1},
            {"timestamp_utc": "2026-01-01T00:00:00Z", "open": 1, "high": 2, "low": 0, "close": 1},
        ]
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            generate_research_signals(rows, pivot_window=1)

    def test_future_15m_context_cannot_authorize_candidate(self):
        rows = [
            (10, 11, 9, 10), (9, 10, 8, 9), (9, 10, 9, 9),
            (9, 10, 7, 9), (10, 12, 10, 11), (11, 11, 10, 10),
            (11, 13, 10, 13), (13, 14, 12, 13), (13, 14, 12, 13),
        ]
        future = [
            OHLCBar("2026-01-02T00:00:00Z", 1, 2, 0, 1),
            OHLCBar("2026-01-02T00:15:00Z", 1, 3, 0, 2),
            OHLCBar("2026-01-02T00:30:00Z", 2, 4, 1, 3),
        ]
        self.assertEqual(
            generate_research_signals(bars_from_rows(rows), context_bars_15m=future,
                                       pivot_window=1), []
        )


    def test_resampler_emits_only_complete_gap_free_15m_buckets(self):
        start = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
        minute_bars = [
            OHLCBar((start + timedelta(minutes=i)).isoformat().replace("+00:00", "Z"),
                    100 + i, 101 + i, 99 + i, 100.5 + i)
            for i in range(15)
        ]
        result = resample_1m_to_15m(minute_bars)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].timestamp_utc, "2026-01-01T00:15:00Z")
        self.assertEqual(result[0].open, minute_bars[0].open)
        self.assertEqual(result[0].close, minute_bars[-1].close)
        self.assertEqual(result[0].high, max(bar.high for bar in minute_bars))
        self.assertEqual(result[0].low, min(bar.low for bar in minute_bars))

    def test_resampler_drops_bucket_with_missing_minute(self):
        start = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
        minute_bars = [
            OHLCBar((start + timedelta(minutes=i)).isoformat().replace("+00:00", "Z"),
                    100, 101, 99, 100)
            for i in range(15) if i != 7
        ]
        self.assertEqual(resample_1m_to_15m(minute_bars), [])

    def test_reward_risk_must_be_preregistered(self):
        with self.assertRaisesRegex(ValueError, "reward_risk"):
            generate_research_signals([], reward_risk=2.5)

    def test_research_module_has_no_capital_authority(self):
        from research.labs import liquidity_sweep_strategy as strategy
        self.assertTrue(strategy.RESEARCH_ONLY)
        self.assertFalse(strategy.CAPITAL_AUTHORITY)
        self.assertFalse(strategy.LIVE_EXECUTION)


if __name__ == "__main__":
    unittest.main()
