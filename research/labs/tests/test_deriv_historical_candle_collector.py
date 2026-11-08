from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

from research.labs.deriv_historical_candle_collector import (
    LEGACY_PUBLIC_WS_URL, PUBLIC_WS_URL, collect_historical_dataset, collect_timeframe,
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
        response = self.responses.pop(0)
        if isinstance(response, dict) and "echo_req" not in response:
            response = {**response, "echo_req": dict(payload)}
        return response

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

    async def test_source_returning_latest_data_for_old_window_fails_as_out_of_range(self):
        transport = FakeTransport([
            {"msg_type": "candles", "candles": [candle(1794144780 + i * 60) for i in range(60)]},
        ])
        with self.assertRaisesRegex(RuntimeError, "SOURCE_RETURNED_OUT_OF_RANGE_CANDLES"):
            await collect_timeframe(
                transport, symbol="R_100", start_epoch=1666310400,
                end_epoch=1666314000, granularity=60,
                chunk_bars=900, request_delay_seconds=0,
            )

    async def test_echo_request_mismatch_fails_closed(self):
        transport = FakeTransport([
            {
                "msg_type": "candles",
                "candles": [candle(600), candle(660), candle(720)],
                "echo_req": {
                    "ticks_history": "R_100", "style": "candles",
                    "granularity": 60, "start": 600, "end": "780", "count": 3
                },
            },
        ])
        with self.assertRaisesRegex(RuntimeError, "ECHO_REQUEST_MISMATCH"):
            await collect_timeframe(
                transport, symbol="R_100", start_epoch=600, end_epoch=780,
                granularity=60, chunk_bars=3, request_delay_seconds=0,
            )

    async def test_reversed_response_order_is_normalized_only_if_complete(self):
        transport = FakeTransport([
            {"msg_type": "candles", "candles": [candle(720), candle(660), candle(600)]},
        ])
        bars = await collect_timeframe(
            transport, symbol="R_100", start_epoch=600, end_epoch=780,
            granularity=60, chunk_bars=3, request_delay_seconds=0,
        )
        self.assertEqual(
            [int(datetime.fromisoformat(x.timestamp_utc).timestamp()) for x in bars],
            [600, 660, 720],
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
        with self.assertRaisesRegex(RuntimeError, "API_REJECTED:InvalidSymbol"):
            await collect_timeframe(
                transport, symbol="R_100", start_epoch=600, end_epoch=660,
                granularity=60, chunk_bars=3, request_delay_seconds=0,
            )

    def test_safe_diagnostics_preserve_only_fixed_reason_codes(self):
        from research.labs.deriv_historical_candle_collector import safe_historical_error_reason

        self.assertEqual(
            safe_historical_error_reason(RuntimeError("HISTORICAL_WINDOW_INVALID")),
            "HISTORICAL_WINDOW_INVALID",
        )
        self.assertEqual(
            safe_historical_error_reason(RuntimeError("DERIV_HISTORICAL_API_REJECTED:InvalidSymbol")),
            "DERIV_HISTORICAL_API_REJECTED:InvalidSymbol",
        )

    def test_safe_diagnostics_preserve_source_range_failure_evidence(self):
        from research.labs.deriv_historical_candle_collector import safe_historical_error_reason

        reason = (
            "DERIV_HISTORICAL_SOURCE_RETURNED_OUT_OF_RANGE_CANDLES:"
            "requested_start=1666310400:requested_end=1666313940:"
            "actual_first=1794144780:actual_last=1794148320"
        )
        self.assertEqual(safe_historical_error_reason(RuntimeError(reason)), reason)

    def test_safe_diagnostics_preserve_timestamp_only_gap_evidence(self):
        from research.labs.deriv_historical_candle_collector import safe_historical_error_reason

        reason = (
            "DERIV_HISTORICAL_GAP_OR_TRUNCATION_DETECTED:"
            "expected_count=60:actual_count=2:expected_first=1666310400:"
            "expected_last=1666313940:actual_first=1666310460:actual_last=1666310520"
        )
        self.assertEqual(safe_historical_error_reason(RuntimeError(reason)), reason)

    def test_safe_diagnostics_mask_arbitrary_exception_text(self):
        from research.labs.deriv_historical_candle_collector import safe_historical_error_reason

        private = "SYNTHETIC_TOKEN_OR_ACCOUNT_DATA"
        result = safe_historical_error_reason(RuntimeError(private))
        self.assertEqual(result, "UNCLASSIFIED_RUNTIMEERROR")
        self.assertNotIn(private, result)

    async def test_legacy_public_endpoint_is_explicit_and_unauthenticated(self):
        responses = [
            {"msg_type": "candles", "candles": [candle(600), candle(660), candle(720)]},
        ]
        created = []

        def factory(url, **kwargs):
            created.append((url, kwargs))
            return FakeTransport(responses)

        with tempfile.TemporaryDirectory() as directory:
            manifest = await collect_historical_dataset(
                symbol="R_100", start_epoch=600, end_epoch=780,
                granularities=(60,), output_dir=directory,
                source_commit="a" * 40, chunk_bars=3,
                request_delay_seconds=0, api_variant="legacy",
                transport_factory=factory,
            )
        self.assertEqual(created[0][0], LEGACY_PUBLIC_WS_URL)
        self.assertEqual(manifest["datasets"][0]["source_endpoint"], LEGACY_PUBLIC_WS_URL)
        self.assertEqual(manifest["api_variant"], "legacy")
        self.assertFalse(manifest["authentication_used"])
        self.assertFalse(manifest["capital_authority"])
        self.assertFalse(manifest["order_submission_permitted"])

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
            self.assertTrue(all(x["source_endpoint"] == PUBLIC_WS_URL for x in manifest["datasets"]))
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
