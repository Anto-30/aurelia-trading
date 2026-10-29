"""Network-free tests for the Deriv candle payload validator."""
import unittest

from research.labs.fetch_deriv_candles import validate_candles


def candle(epoch=1_760_000_040, open_=100, high=102, low=99, close=101):
    # Default epoch is minute-aligned.
    return {"epoch": epoch, "open": open_, "high": high, "low": low, "close": close}


class DerivCandleValidatorTests(unittest.TestCase):
    def test_builds_utc_datetime_index_and_ohlc_only_schema(self):
        frame = validate_candles([candle()])
        self.assertEqual(str(frame.index.tz), "UTC")
        self.assertEqual(list(frame.columns), ["open", "high", "low", "close"])
        self.assertEqual(len(frame), 1)

    def test_rejects_duplicate_timestamps(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CANDLE_TIMESTAMPS"):
            validate_candles([candle(), candle()])

    def test_rejects_minute_misaligned_epoch(self):
        with self.assertRaisesRegex(ValueError, "CANDLE_EPOCH_NOT_MINUTE_ALIGNED"):
            validate_candles([candle(epoch=1_760_000_041)])

    def test_rejects_inconsistent_high_low(self):
        with self.assertRaisesRegex(ValueError, "OHLC_BAR_INCONSISTENT"):
            validate_candles([candle(high=100, low=99, open_=101, close=101)])


if __name__ == "__main__":
    unittest.main()
