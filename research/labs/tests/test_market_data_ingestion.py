from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.labs.market_data_ingestion import (
    MarketDataIngestionError,
    ingest_deriv_candle_payload,
    ingest_deriv_json_file,
    ingest_deriv_tick_payload,
    ingest_standard_csv,
)


class StandardCSVIngestionTests(unittest.TestCase):
    def _csv(self, content: str) -> Path:
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False)
        temp.write(content)
        temp.close()
        self.addCleanup(Path(temp.name).unlink, missing_ok=True)
        return Path(temp.name)

    def test_standard_csv_accepts_aware_utc_and_preserves_missing_volume(self):
        path = self._csv(
            "DateTime,Open,High,Low,Close\n"
            "2026-01-01T00:00:00Z,100,102,99,101\n"
            "2026-01-01T00:01:00Z,101,103,100,102\n"
        )
        result = ingest_standard_csv(
            path, symbol="frxEURUSD", asset_class="financial",
            granularity_seconds=60,
        )
        self.assertTrue(result.eligible_for_research)
        self.assertEqual(len(result.bars), 2)
        self.assertIsNone(result.bars[0].volume)
        self.assertEqual(result.audit.volume_kind, "UNAVAILABLE")
        self.assertEqual(result.audit.timestamp_basis, "EXPLICIT_OFFSET_OR_UTC")
        self.assertFalse(result.audit.capital_authority_granted)

    def test_naive_source_time_requires_explicit_iana_timezone(self):
        path = self._csv(
            "datetime,open,high,low,close\n"
            "2026-01-01 00:00:00,100,102,99,101\n"
        )
        result = ingest_standard_csv(
            path, symbol="EURUSD", asset_class="financial",
            granularity_seconds=60,
        )
        self.assertFalse(result.eligible_for_research)
        self.assertIn("NAIVE_TIMESTAMP_REQUIRES_SOURCE_TIMEZONE", result.audit.issue_codes)
        self.assertEqual(result.bars, ())

    def test_naive_timestamp_converts_from_explicit_iana_zone(self):
        path = self._csv(
            "datetime,open,high,low,close\n"
            "2026-01-01 09:00:00,100,102,99,101\n"
        )
        result = ingest_standard_csv(
            path, symbol="EURUSD", asset_class="financial",
            granularity_seconds=60, source_timezone="America/New_York",
        )
        self.assertTrue(result.eligible_for_research)
        self.assertEqual(result.bars[0].timestamp_utc, "2026-01-01T14:00:00Z")
        self.assertEqual(result.audit.timestamp_basis, "IANA_SOURCE_TIMEZONE_CONVERTED")

    def test_dst_ambiguous_and_nonexistent_local_times_are_quarantined(self):
        ambiguous = self._csv(
            "datetime,open,high,low,close\n"
            "2026-11-01 01:30:00,100,102,99,101\n"
        )
        result_a = ingest_standard_csv(
            ambiguous, symbol="EURUSD", asset_class="financial",
            granularity_seconds=60, source_timezone="America/New_York",
        )
        self.assertIn("AMBIGUOUS_LOCAL_TIMESTAMP_DST", result_a.audit.issue_codes)

        nonexistent = self._csv(
            "datetime,open,high,low,close\n"
            "2026-03-08 02:30:00,100,102,99,101\n"
        )
        result_n = ingest_standard_csv(
            nonexistent, symbol="EURUSD", asset_class="financial",
            granularity_seconds=60, source_timezone="America/New_York",
        )
        self.assertIn("NONEXISTENT_LOCAL_TIMESTAMP_DST", result_n.audit.issue_codes)

    def test_duplicate_and_out_of_order_rows_are_not_silently_dropped(self):
        path = self._csv(
            "datetime,open,high,low,close\n"
            "2026-01-01T00:01:00Z,100,102,99,101\n"
            "2026-01-01T00:00:00Z,101,103,100,102\n"
            "2026-01-01T00:00:00Z,101,103,100,102\n"
        )
        result = ingest_standard_csv(
            path, symbol="R_100", asset_class="synthetic",
            granularity_seconds=60,
        )
        self.assertFalse(result.eligible_for_research)
        self.assertEqual(result.audit.rows_seen, 3)
        self.assertEqual(result.audit.out_of_order_count, 1)
        self.assertEqual(result.audit.duplicate_timestamp_count, 1)
        self.assertIn("OUT_OF_ORDER_TIMESTAMP", result.audit.issue_codes)
        self.assertIn("DUPLICATE_TIMESTAMP", result.audit.issue_codes)

    def test_inconsistent_ohlc_is_quarantined_not_repaired(self):
        path = self._csv(
            "datetime,open,high,low,close\n"
            "2026-01-01T00:00:00Z,100,99,98,101\n"
        )
        result = ingest_standard_csv(
            path, symbol="R_100", asset_class="synthetic",
            granularity_seconds=60,
        )
        self.assertFalse(result.eligible_for_research)
        self.assertIn("OHLC_HIGH_INCONSISTENT", result.audit.issue_codes)
        self.assertEqual(result.bars, ())

    def test_missing_volume_is_not_replaced_by_one_for_synthetics(self):
        path = self._csv(
            "timestamp,o,h,l,c,volume\n"
            "2026-01-01T00:00:00Z,100,102,99,101,\n"
        )
        result = ingest_standard_csv(
            path, symbol="R_75", asset_class="synthetic",
            granularity_seconds=60,
        )
        self.assertTrue(result.eligible_for_research)
        self.assertIsNone(result.bars[0].volume)
        self.assertEqual(result.audit.volume_kind, "SOURCE_REPORTED_UNVERIFIED")

    def test_epoch_timestamp_csv_is_accepted_as_utc(self):
        path = self._csv(
            "epoch,open,high,low,close\n"
            "1767225600,100,102,99,101\n"
        )
        result = ingest_standard_csv(
            path, symbol="R_75", asset_class="synthetic",
            granularity_seconds=60,
        )
        self.assertTrue(result.eligible_for_research)
        self.assertEqual(result.bars[0].timestamp_utc, "2026-01-01T00:00:00Z")

    def test_gap_is_reported_without_assuming_weekend_is_corruption(self):
        path = self._csv(
            "datetime,open,high,low,close\n"
            "2026-01-02T21:00:00Z,100,102,99,101\n"
            "2026-01-05T00:00:00Z,101,103,100,102\n"
        )
        result = ingest_standard_csv(
            path, symbol="frxEURUSD", asset_class="financial",
            granularity_seconds=900,
        )
        self.assertTrue(result.eligible_for_research)
        self.assertEqual(result.audit.gap_count, 1)
        self.assertGreater(result.audit.maximum_gap_seconds, 900)

    def test_unknown_timezone_fails_as_configuration_error(self):
        path = self._csv(
            "datetime,open,high,low,close\n"
            "2026-01-01 09:00:00,100,102,99,101\n"
        )
        with self.assertRaisesRegex(MarketDataIngestionError, "SOURCE_TIMEZONE_NOT_IANA"):
            ingest_standard_csv(
                path, symbol="EURUSD", asset_class="financial",
                granularity_seconds=60, source_timezone="Not/AZone",
            )


class DerivIngestionTests(unittest.TestCase):
    def test_deriv_candle_response_binds_symbol_and_keeps_volume_unavailable(self):
        payload = {
            "echo_req": {"ticks_history": "R_100", "style": "candles", "granularity": 60},
            "candles": [
                {"epoch": 1767225600, "open": 100, "high": 102, "low": 99, "close": 101},
                {"epoch": 1767225660, "open": 101, "high": 103, "low": 100, "close": 102},
            ],
        }
        result = ingest_deriv_candle_payload(
            payload, symbol="R_100", asset_class="synthetic", granularity_seconds=60,
        )
        self.assertTrue(result.eligible_for_research)
        self.assertEqual(result.audit.source_type, "DERIV_CANDLES_HISTORY_RESPONSE")
        self.assertIsNone(result.bars[0].volume)
        self.assertEqual(result.audit.volume_kind, "UNAVAILABLE_DERIV_CANDLE_PAYLOAD_HAS_NO_VOLUME")

    def test_deriv_candle_symbol_mismatch_fails(self):
        payload = {"echo_req": {"ticks_history": "R_100"}, "candles": []}
        with self.assertRaisesRegex(MarketDataIngestionError, "SYMBOL_BINDING_MISMATCH"):
            ingest_deriv_candle_payload(
                payload, symbol="R_75", asset_class="synthetic", granularity_seconds=60,
            )

    def test_deriv_history_tick_arrays_resample_and_keep_tick_count_separate(self):
        payload = {
            "echo_req": {"ticks_history": "R_100", "style": "ticks", "count": 3},
            "history": {
                "times": [1767225601, 1767225610, 1767225661],
                "prices": [100.0, 102.0, 101.0],
            },
        }
        result = ingest_deriv_tick_payload(
            payload, symbol="R_100", asset_class="synthetic", granularity_seconds=60,
        )
        self.assertTrue(result.eligible_for_research)
        self.assertEqual(len(result.bars), 2)
        self.assertEqual(result.bars[0].timestamp_utc, "2026-01-01T00:00:00Z")
        self.assertEqual(
            (result.bars[0].open, result.bars[0].high, result.bars[0].low, result.bars[0].close),
            (100.0, 102.0, 100.0, 102.0),
        )
        self.assertEqual(result.tick_counts_by_bar, (2, 1))
        self.assertIsNone(result.bars[0].volume)
        self.assertEqual(result.audit.volume_kind, "UNAVAILABLE_TICK_COUNT_PROXY_SEPARATE")

    def test_exporter_datetime_quote_schema_from_previous_prompt_is_supported(self):
        payload = [
            {"datetime": "2026-01-01T00:00:01Z", "quote": 100.0},
            {"datetime": "2026-01-01T00:00:20Z", "quote": 102.0},
            {"datetime": "2026-01-01T00:01:02Z", "quote": 101.0},
        ]
        result = ingest_deriv_tick_payload(
            payload, symbol="R_100", asset_class="synthetic", granularity_seconds=60,
        )
        self.assertTrue(result.eligible_for_research)
        self.assertEqual(result.audit.source_type, "DERIV_TICK_EXPORT_RECORDS")
        self.assertEqual(result.tick_counts_by_bar, (2, 1))

    def test_json_file_source_hash_is_exact_file_hash(self):
        payload = [
            {"epoch": 1767225601, "quote": 100.0},
            {"epoch": 1767225610, "quote": 102.0},
        ]
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        temp.write(json.dumps(payload, separators=(",", ":")))
        temp.close()
        path = Path(temp.name)
        self.addCleanup(path.unlink, missing_ok=True)
        raw = path.read_bytes()
        result = ingest_deriv_json_file(
            path, symbol="R_100", asset_class="synthetic", granularity_seconds=60,
        )
        import hashlib
        self.assertEqual(result.audit.source_sha256, hashlib.sha256(raw).hexdigest())
        self.assertTrue(result.eligible_for_research)

    def test_json_file_candle_response_is_dispatched_to_candle_parser(self):
        payload = {
            "echo_req": {"ticks_history": "R_100", "style": "candles", "granularity": 60},
            "candles": [
                {"epoch": 1767225600, "open": 100, "high": 102, "low": 99, "close": 101}
            ],
        }
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        temp.write(json.dumps(payload, separators=(",", ":")))
        temp.close()
        path = Path(temp.name)
        self.addCleanup(path.unlink, missing_ok=True)
        import hashlib
        raw = path.read_bytes()
        result = ingest_deriv_json_file(
            path, symbol="R_100", asset_class="synthetic", granularity_seconds=60,
        )
        self.assertEqual(result.audit.source_type, "DERIV_CANDLES_HISTORY_RESPONSE")
        self.assertEqual(result.audit.source_sha256, hashlib.sha256(raw).hexdigest())
        self.assertTrue(result.eligible_for_research)

    def test_empty_standard_csv_is_quarantined_with_explicit_reason(self):
        path = self._csv("datetime,open,high,low,close\\n")
        result = ingest_standard_csv(
            path, symbol="R_100", asset_class="synthetic", granularity_seconds=60,
        )
        self.assertFalse(result.eligible_for_research)
        self.assertIn("NO_VALID_ROWS", result.audit.issue_codes)

    def test_out_of_order_ticks_quarantine_resampled_output(self):
        payload = [
            {"epoch": 1767225610, "quote": 100.0},
            {"epoch": 1767225601, "quote": 102.0},
        ]
        result = ingest_deriv_tick_payload(
            payload, symbol="R_100", asset_class="synthetic", granularity_seconds=60,
        )
        self.assertFalse(result.eligible_for_research)
        self.assertIn("OUT_OF_ORDER_TICK", result.audit.issue_codes)
        self.assertEqual(result.bars, ())

    def test_deriv_response_requires_echo_request_symbol_binding(self):
        payload = {"history": {"times": [1767225600], "prices": [100.0]}}
        with self.assertRaisesRegex(MarketDataIngestionError, "DERIV_ECHO_REQUEST_MISSING"):
            ingest_deriv_tick_payload(
                payload, symbol="R_100", asset_class="synthetic", granularity_seconds=60,
            )


if __name__ == "__main__":
    unittest.main()
