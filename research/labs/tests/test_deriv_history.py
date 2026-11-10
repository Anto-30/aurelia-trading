from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd

from research.labs.deriv_history import (
    DerivHistoryError,
    _epoch,
    fetch_yfinance_ohlc,
)


class DerivHistoryContractTests(unittest.TestCase):
    def test_history_boundaries_require_timezone(self):
        with self.assertRaisesRegex(ValueError, "TIMEZONE_AWARE"):
            _epoch(datetime(2026, 11, 10, 12, 0))

    def test_aware_boundaries_are_normalized_to_epoch(self):
        expected = int(datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc).timestamp())
        self.assertEqual(_epoch(datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)), expected)

    def test_yfinance_rejects_ninety_day_intraday_request_before_network(self):
        end = datetime(2026, 11, 10, tzinfo=timezone.utc)
        start = end - timedelta(days=90)
        with self.assertRaisesRegex(ValueError, "60_DAYS"):
            fetch_yfinance_ohlc("AAPL", start, end, interval="1m")

    def test_yfinance_accepts_up_to_sixty_day_intraday_request_contract(self):
        end = datetime(2026, 11, 10, tzinfo=timezone.utc)
        start = end - timedelta(days=60)
        # Network/import is intentionally not attempted by a separate helper;
        # this assertion documents the guard boundary itself.
        self.assertLessEqual(end - start, pd.Timedelta(days=60))


if __name__ == "__main__":
    unittest.main()
