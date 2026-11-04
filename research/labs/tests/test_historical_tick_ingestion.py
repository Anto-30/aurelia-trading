from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.data.deriv_tick_ingestor import (
    DerivTickIngestionError,
    DerivTickIngestor,
    Tick,
    parse_history_response,
    validate_ticks,
)


class FakeWebSocket:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def send(self, payload):
        self.requests.append(json.loads(payload))

    async def recv(self):
        return json.dumps(self.responses.pop(0))


class FakeWebSocketContext:
    def __init__(self, ws):
        self.ws = ws

    async def __aenter__(self):
        return self.ws

    async def __aexit__(self, exc_type, exc, tb):
        return False


class HistoricalTickIngestionTests(unittest.IsolatedAsyncioTestCase):
    def test_history_response_parses_equal_arrays_and_preserves_same_second_ticks(self):
        page = parse_history_response({
            "msg_type": "history",
            "req_id": 7,
            "history": {"times": [100, 100, 101], "prices": [10.0, 10.1, 10.2]},
        }, symbol="R_100", expected_req_id=7)
        self.assertEqual(
            [(x.epoch, x.quote) for x in page.ticks],
            [(100, 10.0), (100, 10.1), (101, 10.2)],
        )

    def test_history_response_rejects_mismatched_times_and_prices(self):
        with self.assertRaisesRegex(DerivTickIngestionError, "HISTORY_ARRAY_LENGTH_MISMATCH"):
            parse_history_response({
                "msg_type": "history", "req_id": 1,
                "history": {"times": [100, 101], "prices": [10.0]},
            }, symbol="R_100", expected_req_id=1)

    def test_history_response_rejects_nonfinite_or_negative_quotes(self):
        for bad_quote in (float("nan"), float("inf"), -1.0):
            with self.subTest(quote=bad_quote):
                with self.assertRaisesRegex(DerivTickIngestionError, "TICK_QUOTE_INVALID"):
                    parse_history_response({
                        "msg_type": "history", "req_id": 1,
                        "history": {"times": [100], "prices": [bad_quote]},
                    }, symbol="R_100", expected_req_id=1)

    def test_history_response_rejects_request_id_mismatch_and_api_error(self):
        with self.assertRaisesRegex(DerivTickIngestionError, "REQUEST_ID_MISMATCH"):
            parse_history_response({
                "msg_type": "history", "req_id": 9,
                "history": {"times": [100], "prices": [10.0]},
            }, symbol="R_100", expected_req_id=1)
        with self.assertRaisesRegex(DerivTickIngestionError, "DERIV_API_ERROR"):
            parse_history_response({
                "msg_type": "error", "req_id": 1,
                "error": {"code": "RateLimit", "message": "retry"},
            }, symbol="R_100", expected_req_id=1)

    def test_validation_preserves_distinct_same_second_ticks_and_reports_gaps(self):
        ticks = [
            Tick("R_100", 100, 10.0),
            Tick("R_100", 100, 10.1),
            Tick("R_100", 101, 10.2),
            Tick("R_100", 250, 10.3),
        ]
        report = validate_ticks(ticks, max_gap_seconds=120)
        self.assertEqual(report.input_count, 4)
        self.assertEqual(report.unique_count, 4)
        self.assertEqual(report.duplicate_count, 0)
        self.assertEqual(report.max_gap_seconds, 149)
        self.assertEqual(report.gaps_over_threshold, 1)

    def test_validation_removes_only_exact_duplicate_ticks(self):
        ticks = [
            Tick("R_100", 100, 10.0),
            Tick("R_100", 100, 10.0),
            Tick("R_100", 100, 10.1),
        ]
        report = validate_ticks(ticks, max_gap_seconds=120)
        self.assertEqual(report.unique_count, 2)
        self.assertEqual(report.duplicate_count, 1)

    async def test_ingestor_pages_backward_with_explicit_count_and_no_subscription(self):
        responses = [
            {"msg_type": "history", "req_id": 1,
             "history": {"times": [8, 9, 10], "prices": [10.8, 10.9, 11.0]}},
            {"msg_type": "history", "req_id": 2,
             "history": {"times": [6, 7, 8], "prices": [10.6, 10.7, 10.8]}},
            {"msg_type": "history", "req_id": 3,
             "history": {"times": [5, 6], "prices": [10.5, 10.6]}},
        ]
        ws = FakeWebSocket(responses)
        ingestor = DerivTickIngestor(
            ws_connect=lambda _: FakeWebSocketContext(ws),
            page_size=3,
            rate_limit_seconds=0,
        )
        result = await ingestor.fetch_ticks(
            "R_100", start_epoch=5, end_epoch=10
        )
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.pages_fetched, 3)
        self.assertEqual(result.tick_count, 6)
        self.assertEqual([x.epoch for x in result.ticks], [5, 6, 7, 8, 9, 10])
        self.assertEqual(
            [x["end"] for x in ws.requests],
            ["10", "8", "6"],
        )
        for request in ws.requests:
            self.assertEqual(request["count"], 3)
            self.assertEqual(request["style"], "ticks")
            self.assertEqual(request.get("subscribe", 0), 0)
            self.assertEqual(request["ticks_history"], "R_100")

    async def test_ingestor_fails_closed_on_unavailable_or_incomplete_pages(self):
        ws = FakeWebSocket([
            {"msg_type": "history", "req_id": 1,
             "history": {"times": [8, 9, 10], "prices": [10.8, 10.9, 11.0]}},
        ])
        ingestor = DerivTickIngestor(
            ws_connect=lambda _: FakeWebSocketContext(ws),
            page_size=3,
            rate_limit_seconds=0,
            max_pages=1,
        )
        with self.assertRaisesRegex(DerivTickIngestionError, "PAGE_LIMIT_REACHED"):
            await ingestor.fetch_ticks("R_100", start_epoch=5, end_epoch=10)

    def test_tick_resampling_builds_closed_one_minute_ohlc_without_fake_volume(self):
        from research.data.pipeline import resample_ticks_to_strategy_bars

        bars = resample_ticks_to_strategy_bars(
            [
                Tick("R_100", 600001, 10.0),
                Tick("R_100", 600002, 10.2),
                Tick("R_100", 600002, 10.25),
                Tick("R_100", 600059, 9.8),
                Tick("R_100", 600060, 9.9),
                Tick("R_100", 600119, 10.1),
            ],
            timeframe_seconds=60,
            data_end_epoch=600120,
        )
        self.assertEqual(len(bars), 2)
        self.assertEqual((bars[0].open, bars[0].high, bars[0].low, bars[0].close),
                         (10.0, 10.25, 9.8, 9.8))
        self.assertEqual((bars[1].open, bars[1].high, bars[1].low, bars[1].close),
                         (9.9, 10.1, 9.9, 10.1))
        self.assertEqual(bars[0].timestamp_utc, "1970-01-07T22:41:00+00:00")
        self.assertIsNone(bars[0].volume)
        self.assertIsNone(bars[1].session_id)

    def test_tick_resampling_excludes_incomplete_last_bar_and_does_not_fill_gaps(self):
        from research.data.pipeline import resample_ticks_to_strategy_bars

        bars = resample_ticks_to_strategy_bars(
            [
                Tick("R_100", 600001, 10.0),
                Tick("R_100", 600059, 10.1),
                Tick("R_100", 600121, 10.2),
                Tick("R_100", 600179, 10.3),
            ],
            timeframe_seconds=60,
            data_end_epoch=600150,
        )
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].close, 10.1)

    def test_tick_resampling_supports_fifteen_minute_bars(self):
        from research.data.pipeline import resample_ticks_to_strategy_bars

        bars = resample_ticks_to_strategy_bars(
            [
                Tick("R_100", 900001, 100.0),
                Tick("R_100", 900899, 101.0),
            ],
            timeframe_seconds=900,
            data_end_epoch=900900,
        )
        self.assertEqual(len(bars), 1)
        self.assertEqual((bars[0].open, bars[0].high, bars[0].low, bars[0].close),
                         (100.0, 101.0, 100.0, 101.0))

    def test_tick_resampling_rejects_unsupported_timeframe_and_no_closed_bars(self):
        from research.data.pipeline import resample_ticks_to_strategy_bars

        with self.assertRaisesRegex(ValueError, "TIMEFRAME_SECONDS_UNSUPPORTED"):
            resample_ticks_to_strategy_bars(
                [Tick("R_100", 600001, 10.0)],
                timeframe_seconds=300,
                data_end_epoch=600600,
            )
        with self.assertRaisesRegex(ValueError, "NO_COMPLETE_BARS_AVAILABLE"):
            resample_ticks_to_strategy_bars(
                [Tick("R_100", 600001, 10.0)],
                timeframe_seconds=60,
                data_end_epoch=600030,
            )

    def test_tick_record_rejects_invalid_fields(self):
        for tick in (
            Tick("", 100, 10.0),
            Tick("R_100", 0, 10.0),
            Tick("R_100", 100, -1.0),
            Tick("R_100", 100, float("nan")),
        ):
            with self.subTest(tick=tick):
                with self.assertRaises(ValueError):
                    tick.validate()


class ParquetTickStoreTests(unittest.TestCase):
    def test_write_page_creates_partitioned_parquet_and_provenance(self):
        try:
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow is installed by the research requirements")
        with tempfile.TemporaryDirectory() as directory:
            store = __import__(
                "research.data.parquet_store", fromlist=["ParquetTickStore"]
            ).ParquetTickStore(directory)
            ticks = [
                Tick("R_100", 1790000000, 10.0),
                Tick("R_100", 1790000001, 10.1),
            ]
            written = store.write_page(
                symbol="R_100",
                run_id="run-fixture",
                page_number=1,
                ticks=ticks,
                request={"ticks_history": "R_100", "count": 2, "end": "1790000001"},
                source_sha="fixture-sha",
                page_sha256="a" * 64,
            )
            parquet_path = Path(written.parquet_paths[0])
            self.assertTrue(parquet_path.is_file())
            self.assertEqual(pq.read_table(parquet_path).num_rows, 2)
            manifest = Path(written.provenance_paths[0])
            self.assertTrue(manifest.is_file())
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["symbol"], "R_100")
            self.assertEqual(payload["source_sha"], "fixture-sha")
            self.assertEqual(len(payload["parquet_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
