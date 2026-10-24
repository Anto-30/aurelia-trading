from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

from research.atos_validation.deriv_data import DerivHistoryClient


def fake_candles(start: int, end: int, granularity: int = 60) -> pd.DataFrame:
    rows = []
    for i, epoch in enumerate(range(start, end + 1, granularity)):
        rows.append({"timestamp": pd.Timestamp(epoch, unit="s", tz="UTC"), "epoch": epoch,
                     "open": 100.0 + i, "high": 102.0 + i, "low": 99.0 + i,
                     "close": 101.0 + i, "volume": np.nan})
    return pd.DataFrame(rows)[["timestamp", "epoch", "open", "high", "low", "close", "volume"]]


class BackfillPacingTests(unittest.TestCase):
    def test_pauses_between_nonoverlapping_pages(self):
        client = DerivHistoryClient("12345")
        client.candles = Mock(side_effect=lambda symbol, start, end, granularity=60, count=5000: fake_candles(start, end, granularity))
        with patch("research.atos_validation.deriv_data.time.sleep") as sleep:
            end = 60 + 204 * 60
            frame = client.backfill("R_100", 60, end, 60, bars_per_request=100, request_delay_seconds=1.5)
        self.assertEqual(len(frame), 205)
        self.assertEqual(client.candles.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_any_call(1.5)

    def test_rejects_aggressive_or_invalid_delay_before_network(self):
        client = DerivHistoryClient("12345")
        client.candles = Mock()
        for delay in (0, 0.1, 1.0, float("nan"), True):
            with self.subTest(delay=delay), self.assertRaises(ValueError):
                client.backfill("R_100", 60, 120, 60, bars_per_request=100, request_delay_seconds=delay)
        client.candles.assert_not_called()


if __name__ == "__main__":
    unittest.main()
