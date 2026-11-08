from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

from research.labs.deriv_historical_candle_collector import (
    PUBLIC_WS_URL, collect_historical_dataset, collect_timeframe,
    normalized_bars_sha256,
)
from research.labs.deterministic_intraday_strategies import StrategyBar


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.connected = False
        self.closed = False

    async def connect(self):
        self.connected = True

    async def request(self, payload):
        self.requests.append(dict(payload))
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)

    async def close(self):
        self.closed = True


def candle(epoch, opened=100.0, high=101.0, low=99.0, close=100.5):
    return {"epoch": epoch, "open": opened, "high": high, "low": low, "close": close}


class HistoricalCandleCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_exact_chunks_and_advances_without_overlap(self):
        transport = FakeTransport([
            {"msg_type": "candles", "candles": [candle(600), candle(660), candle(720)]},
            {"msg_type": "candles", "candles": [candle(780), candle(840), candle(900)]},
        ])
        bars = await collect_timeframe(
            transport, symbol="R_100", start_epoch=600, end_epoch=960,
            granularity=60, chunk_bars=3, request_delay_seconds=0,
        )
        self.assertEqual(len(bars), 6)
        self.assertEqual(
            [int(datetime.fromisoformat(x.timestamp_utc).timestamp()) for x in bars],
            [600, 660, 720, 780, 840, 900],
        )
        self.assertEqual(transport.requests[0]["count"], 3)
        self.assertEqual(transport.requests[0]["end"], "720")
        self.assertEqual(transport.requests[1]["start"], 780)
        self.assertEqual(transport.requests[1]["end"], "900")
        self.assertNotIn("subscribe", transport.requests[0])

    async def test_missing_bar_fails_closed_instead_of_interpolating(self):
        transport = FakeTransport([
            {"msg_type": "candles", "candles": [candle(600), candle(720)]},
        ])
        with self.assertRaisesRegex(RuntimeError, "GAP_OR_TRUNCATION"):
            await collect_timeframe(
                transport, symbol="R_100", start_epoch=600, end_epoch=780,
                granularity=60, chunk_bars=3, request_delay_seconds=0,
            )

    async def test_invalid_candle_ohlc_fails_closed(self):
        transport = FakeTransport([
            {"msg_type": "candles", "candles": [candle(600, high=99.0)]},
        ])
        with self.assertRaisesRegex(ValueError, "OHLC_INVARIANT"):
            await collect_timeframe(
                transport, symbol="R_100", start_epoch=600, end_epoch=660,
                granularity=60, chunk_bars=3, request_delay_seconds=0,
            )

    async def test_api_error_response_fails_without_echoing_payload(self):
        transport = FakeTransport([
            {"msg_type": "error", "error": {"code": "InvalidSymbol", "message": "SYNTHETIC_SECRET"}},
        ])
        with self.assertRaisesRegex(RuntimeError, "RESPONSE_TYPE_INVALID"):
            await collect_timeframe(
                transport, symbol="R_100", start_epoch=600, end_epoch=660,
                granularity=60, chunk_bars=3, request_delay_seconds=0,
            )

    async def test_public_collection_writes_manifest_and_hashes(self):
        responses = [
            {"msg_type": "candles", "candles": [candle(x) for x in range(0, 1800, 60)]},
            {"msg_type": "candles", "candles": [candle(0), candle(900)]},
        ]
        created = []
        instances = []

        def factory(url, **kwargs):
            created.append((url, kwargs))
            instance = FakeTransport(responses)
            instances.append(instance)
            return instance

        with tempfile.TemporaryDirectory() as directory:
            manifest = await collect_historical_dataset(
                symbol="R_100", start_epoch=0, end_epoch=1800,
                granularities=(60, 900), output_dir=directory,
                source_commit="a" * 40, chunk_bars=100,
                request_delay_seconds=0, transport_factory=factory,
            )
            self.assertFalse(manifest["authentication_used"])
            self.assertFalse(manifest["capital_authority"])
            self.assertFalse(manifest["order_submission_permitted"])
            self.assertEqual(created[0][0], PUBLIC_WS_URL)
            self.assertEqual(created[0][1]["application_ping_interval_seconds"], 30.0)
            self.assertTrue(instances[0].connected)
            self.assertTrue(instances[0].closed)
            loaded = json.loads((Path(directory) / "manifest.json").read_text())
            self.assertEqual(len(loaded["datasets"]), 2)
            self.assertEqual(
                [x["timeframe"] for x in loaded["datasets"]], ["M1", "M15"]
            )
            self.assertTrue(all(
                len(x["normalized_bars_sha256"]) == 64 and len(x["csv_sha256"]) == 64
                for x in loaded["datasets"]
            ))

    def test_normalized_hash_is_stable_and_sensitive_to_bar_changes(self):
        first = StrategyBar("2026-01-01T00:00:00+00:00", 100.0, 101.0, 99.0, 100.5)
        changed = StrategyBar("2026-01-01T00:00:00+00:00", 100.0, 102.0, 99.0, 100.5)
        self.assertEqual(normalized_bars_sha256([first]), normalized_bars_sha256([first]))
        self.assertNotEqual(normalized_bars_sha256([first]), normalized_bars_sha256([changed]))


if __name__ == "__main__":
    unittest.main()
