from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd

from research.labs.deriv_history import (
    DerivHistoryError,
    _normalize_deriv_pip_size,
    _epoch,
    _validate_yfinance_window,
    fetch_deriv_candles,
    fetch_yfinance_ohlc,
)


class DerivHistoryContractTests(unittest.TestCase):
    def test_history_boundaries_require_timezone(self):
        with self.assertRaisesRegex(ValueError, "TIMEZONE_AWARE"):
            _epoch(datetime(2026, 11, 10, 12, 0))

    def test_aware_boundaries_are_normalized_to_epoch(self):
        expected = int(datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc).timestamp())
        self.assertEqual(_epoch(datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)), expected)

    def test_deriv_active_symbols_pip_size_is_preserved_as_provider_price_increment(self):
        self.assertAlmostEqual(_normalize_deriv_pip_size(0.01), 0.01)
        self.assertAlmostEqual(_normalize_deriv_pip_size(0.0001), 0.0001)
        self.assertAlmostEqual(_normalize_deriv_pip_size(5), 5.0)

    def test_deriv_pip_size_rejects_non_positive_non_finite_or_invalid_values(self):
        for value in (-1, 0, float("inf"), None, "invalid"):
            with self.subTest(value=value):
                with self.assertRaises(DerivHistoryError):
                    _normalize_deriv_pip_size(value)

    def test_deriv_history_request_delay_rejects_unpaced_or_excessive_values_before_network(self):
        start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        end = datetime(2026, 11, 2, tzinfo=timezone.utc)
        for delay in (-0.1, 10.1, float("inf")):
            with self.subTest(delay=delay):
                with self.assertRaisesRegex(ValueError, "REQUEST_DELAY_OUT_OF_RANGE"):
                    asyncio.run(fetch_deriv_candles(
                        "R_100", start, end, request_delay_seconds=delay
                    ))

    def test_yfinance_rejects_ninety_day_intraday_request_before_network(self):
        end = datetime(2026, 11, 10, tzinfo=timezone.utc)
        start = end - timedelta(days=90)
        with self.assertRaisesRegex(ValueError, "60_DAYS"):
            fetch_yfinance_ohlc("AAPL", start, end, interval="1m")

    def test_yfinance_accepts_up_to_sixty_day_intraday_request_contract(self):
        end = datetime(2026, 11, 10, tzinfo=timezone.utc)
        start = end - timedelta(days=60)
        start_ts, end_ts = _validate_yfinance_window(start, end, "1m")
        self.assertEqual(end_ts - start_ts, pd.Timedelta(days=60))


if __name__ == "__main__":
    unittest.main()
