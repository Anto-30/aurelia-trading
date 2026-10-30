"""Offline tests for Deriv public history request/response behavior."""
import json
import unittest
from unittest.mock import Mock

import pandas as pd

from research.labs.deriv_public_data import DerivPublicDataClient


class DerivPublicDataTests(unittest.TestCase):
    def _client_with_responses(self, server_time_offset):
        client = DerivPublicDataClient(timeout_seconds=1)
        client.active_symbols = Mock(return_value=[
            {"symbol": "frxXAUUSD", "underlying_symbol": "XAUUSD"}
        ])
        epoch = int(pd.Timestamp("2026-01-05T00:00:00Z").timestamp())
        candle_response = {
            "candles": [{
                "epoch": epoch,
                "open": "4300.1",
                "high": "4301.2",
                "low": "4299.8",
                "close": "4300.9",
            }]
        }
        time_response = {"time": epoch + server_time_offset}
        client._request = Mock(side_effect=[
            (candle_response, json.dumps(candle_response)),
            (time_response, json.dumps(time_response)),
        ])
        return client, epoch

    def test_fetch_candles_uses_end_epoch_and_marks_closed_bar(self):
        client, epoch = self._client_with_responses(900)
        batch = client.fetch_candles(
            "frxXAUUSD", granularity_seconds=900, count=1, end=epoch + 900
        )
        request = client._request.call_args_list[0].args[0]
        self.assertEqual(request["end"], epoch + 900)
        self.assertEqual(batch.frame.index[0], pd.Timestamp("2026-01-05T00:00:00Z"))
        self.assertTrue(batch.last_bar_closed)
        self.assertEqual(batch.server_time_epoch, epoch + 900)

    def test_current_open_bar_is_not_marked_closed(self):
        client, epoch = self._client_with_responses(899)
        batch = client.fetch_candles("frxXAUUSD", granularity_seconds=900, count=1)
        self.assertFalse(batch.last_bar_closed)

    def test_rejects_count_over_deriv_limit(self):
        client = DerivPublicDataClient(timeout_seconds=1)
        with self.assertRaisesRegex(ValueError, "CANDLE_COUNT_MUST_BE_BETWEEN_1_AND_5000"):
            client.fetch_candles("frxXAUUSD", count=5001)

    def test_accepts_symbol_code_when_both_symbol_fields_present(self):
        client, _ = self._client_with_responses(900)
        batch = client.fetch_candles("frxXAUUSD", count=1)
        self.assertEqual(batch.symbol, "frxXAUUSD")

    def test_trading_times_requires_iso_date(self):
        client = DerivPublicDataClient(timeout_seconds=1)
        with self.assertRaisesRegex(ValueError, "TRADING_TIMES_DATE_MUST_BE_YYYY_MM_DD"):
            client.trading_times("today")

    def test_trading_times_returns_public_symbol_schedules(self):
        client = DerivPublicDataClient(timeout_seconds=1)
        client._request = Mock(return_value=(
            {"trading_times": {"markets": [{"name": "Forex", "submarkets": []}]}},
            '{"trading_times":{"markets":[{"name":"Forex","submarkets":[]}]}}',
        ))
        result = client.trading_times("2026-10-30")
        self.assertEqual(result["markets"][0]["name"], "Forex")
        self.assertEqual(client._request.call_args.args[0], {"trading_times": "2026-10-30"})


if __name__ == "__main__":
    unittest.main()
