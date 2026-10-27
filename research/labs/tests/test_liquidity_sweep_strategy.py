import unittest

from research.labs.liquidity_sweep_strategy import (
    OHLCBar, generate_research_signals, _parse_bar,
)


def bars_from_rows(rows):
    return [
        OHLCBar(f"2026-01-01T00:{i:02d}:00Z", o, h, l, c)
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
