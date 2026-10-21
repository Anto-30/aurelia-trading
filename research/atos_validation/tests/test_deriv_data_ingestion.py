from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

from research.atos_validation.deriv_data import (
    DerivHistoryClient,
    LatencyTelemetry,
    persist_history,
)


def candle_rows(start: int, end: int, granularity: int = 60) -> list[dict]:
    rows = []
    for i, epoch in enumerate(range(start, end + 1, granularity)):
        rows.append({
            "epoch": epoch,
            "open": 100.0 + i,
            "high": 102.0 + i,
            "low": 99.0 + i,
            "close": 101.0 + i,
        })
    return rows


class FakeWebSocket:
    def __init__(self, response: dict):
        self.response = response
        self.request = None
        self.closed = False

    def send(self, payload: str) -> None:
        self.request = json.loads(payload)

    def recv(self) -> str:
        return json.dumps(self.response)

    def close(self) -> None:
        self.closed = True


class DerivHistoryTests(unittest.TestCase):
    def test_candles_request_validates_exact_coverage_and_does_not_fabricate_volume(self):
        ws = FakeWebSocket({"msg_type": "candles", "candles": candle_rows(60, 180)})
        with patch("research.atos_validation.deriv_data.websocket.create_connection", return_value=ws):
            frame = DerivHistoryClient("12345").candles("R_100", 60, 180, 60, 3)
        self.assertEqual(frame["epoch"].tolist(), [60, 120, 180])
        self.assertTrue(frame["volume"].isna().all())
        self.assertEqual(ws.request["subscribe"], 0)
        self.assertEqual(ws.request["adjust_start_time"], 0)
        self.assertTrue(ws.closed)

    def test_gap_duplicate_and_nonfinite_prices_are_rejected(self):
        cases = [
            candle_rows(120, 180),
            [candle_rows(60, 120)[0], candle_rows(60, 120)[0], candle_rows(60, 120)[1]],
            [{**candle_rows(60, 120)[0], "close": float("nan")}, candle_rows(60, 120)[1]],
        ]
        for rows in cases:
            ws = FakeWebSocket({"msg_type": "candles", "candles": rows})
            with self.subTest(rows=rows), patch("research.atos_validation.deriv_data.websocket.create_connection", return_value=ws):
                with self.assertRaises(ValueError):
                    DerivHistoryClient("12345").candles("R_100", 60, 120, 60, 2)

    def test_rejects_misaligned_range_and_count_truncation_before_network(self):
        client = DerivHistoryClient("12345")
        with patch("research.atos_validation.deriv_data.websocket.create_connection") as connect:
            with self.assertRaises(ValueError):
                client.candles("R_100", 61, 181, 60, 3)
            with self.assertRaises(ValueError):
                client.candles("R_100", 60, 600, 60, 3)
            connect.assert_not_called()

    def test_backfill_chunks_without_overlap_and_covers_all_bars(self):
        client = DerivHistoryClient("12345")
        calls = []

        def stub(symbol, start, end, granularity=60, count=5000):
            calls.append((start, end, count))
            return pd.DataFrame(candle_rows(start, end, granularity)).assign(
                timestamp=lambda df: pd.to_datetime(df["epoch"], unit="s", utc=True),
                volume=np.nan,
            )[["timestamp", "epoch", "open", "high", "low", "close", "volume"]]

        client.candles = Mock(side_effect=stub)
        end = 60 + 104 * 60
        frame = client.backfill("R_100", 60, end, 60, bars_per_request=100)
        self.assertEqual(len(frame), 105)
        self.assertEqual(frame["epoch"].tolist(), list(range(60, end + 1, 60)))
        self.assertEqual(calls[0], (60, 60 + 99 * 60, 100))
        self.assertEqual(calls[1][0], calls[0][1] + 60)

    def test_persist_history_writes_checksummed_manifest(self):
        frame = pd.DataFrame(candle_rows(60, 180)).assign(
            timestamp=lambda df: pd.to_datetime(df["epoch"], unit="s", utc=True),
            volume=np.nan,
        )[["timestamp", "epoch", "open", "high", "low", "close", "volume"]]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "R_100_1m.csv"
            manifest = persist_history(
                frame, path, symbol="R_100", granularity=60, start_epoch=60, end_epoch=180
            )
            raw = path.read_bytes()
            self.assertEqual(manifest["bar_count"], 3)
            self.assertTrue(manifest["coverage_complete"])
            self.assertEqual(manifest["data_sha256"], hashlib.sha256(raw).hexdigest())
            saved = json.loads(path.with_suffix(path.suffix + ".manifest.json").read_text())
            self.assertEqual(saved["manifest_sha256"], manifest["manifest_sha256"])

    def test_latency_telemetry_rejects_unordered_clock_values(self):
        telemetry = LatencyTelemetry()
        row = telemetry.record(1.0, 1.1, 1.25)
        self.assertAlmostEqual(row.inference_ms, 100.0)
        self.assertAlmostEqual(row.end_to_end_ms, 250.0)
        self.assertTrue(row.alert_over_200ms)
        with self.assertRaises(ValueError):
            telemetry.record(2.0, 1.9, 2.1)


if __name__ == "__main__":
    unittest.main()
