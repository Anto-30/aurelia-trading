import json
import unittest

from research.labs.deriv_history_fetcher import collect_history


class FakeWebSocket:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []

    async def send(self, payload):
        self.sent.append(json.loads(payload))

    async def recv(self):
        if not self.responses:
            raise AssertionError("unexpected WebSocket read")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return json.dumps(response)


def candle(epoch, close, volume=7):
    return {"epoch": epoch, "open": close, "high": close + 1,
            "low": close - 1, "close": close, "volume": volume}


class DerivHistoryFetcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_backward_pagination_and_coverage_report(self):
        ws = FakeWebSocket([
            {"req_id": 1, "active_symbols": [{"symbol": "R_75"}]},
            {"req_id": 2, "candles": [candle(180, 103), candle(120, 102)]},
            {"req_id": 3, "candles": [candle(60, 101), candle(0, 100)]},
        ])
        df, report = await collect_history(
            ws, "R_75", 100, granularity=60, count=2, pause_seconds=0, max_pages=5
        )
        self.assertEqual(df["timestamp"].tolist(), [
            "1970-01-01T00:02:00+00:00", "1970-01-01T00:03:00+00:00"
        ])
        self.assertEqual(report["candles_written"], 2)
        self.assertEqual(report["pages_requested"], 2)
        self.assertEqual(ws.sent[1]["end"], "latest")
        self.assertEqual(ws.sent[2]["end"], 119)

    async def test_unknown_symbol_fails_closed(self):
        ws = FakeWebSocket([
            {"req_id": 1, "active_symbols": [{"symbol": "R_25"}]},
        ])
        with self.assertRaisesRegex(ValueError, "was not returned"):
            await collect_history(ws, "R_75", 100, pause_seconds=0)

    async def test_repeated_page_fails_closed(self):
        page = [candle(180, 103), candle(120, 102)]
        ws = FakeWebSocket([
            {"req_id": 1, "active_symbols": [{"symbol": "R_75"}]},
            {"req_id": 2, "candles": page},
            {"req_id": 3, "candles": page},
        ])
        with self.assertRaisesRegex(RuntimeError, "no backward progress"):
            await collect_history(ws, "R_75", 100, count=2, pause_seconds=0)

    async def test_missing_volume_is_flagged_as_unit_proxy(self):
        no_volume = {"epoch": 180, "open": 103, "high": 104, "low": 102, "close": 103}
        ws = FakeWebSocket([
            {"req_id": 1, "active_symbols": [{"symbol": "R_75"}]},
            {"req_id": 2, "candles": [no_volume]},
        ])
        df, report = await collect_history(ws, "R_75", 180, pause_seconds=0)
        self.assertEqual(float(df.iloc[0]["volume"]), 1.0)
        self.assertEqual(report["rows_without_source_volume_replaced_by_unit_proxy"], 1)


if __name__ == "__main__":
    unittest.main()
