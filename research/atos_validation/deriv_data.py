"""Deriv WebSocket candle history, reproducible dataset manifests, and latency telemetry.

This module is research-only. It never submits contracts or grants capital authority.
History must cover its exact requested interval; gaps, duplicates, invalid OHLC,
and truncated responses are rejected instead of silently repaired.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import pandas as pd
import websocket

DERIV_WS_BASE = "wss://ws.derivws.com/websockets/v3"
# Current Deriv docs publish ws.derivws.com with app_id; the public market-data
# example also documents ws.binaryws.com without a query-string App ID.
DERIV_WS_FALLBACK_BASE = "wss://ws.binaryws.com/websockets/v3"
OHLC_COLUMNS = ("open", "high", "low", "close")
DATA_COLUMNS = ["timestamp", "epoch", "open", "high", "low", "close", "volume"]


@dataclass(frozen=True)
class LatencyRecord:
    tick_received_monotonic: float
    inference_done_monotonic: float
    order_payload_ready_monotonic: float
    inference_ms: float
    end_to_end_ms: float
    alert_over_200ms: bool


class LatencyTelemetry:
    def __init__(self, threshold_ms: float = 200.0, logger: Callable[[dict], None] | None = None):
        if not math.isfinite(float(threshold_ms)) or threshold_ms <= 0:
            raise ValueError("threshold_ms must be finite and positive")
        self.threshold_ms = float(threshold_ms)
        self.logger = logger or (lambda _: None)

    def record(self, tick_received: float, inference_done: float, payload_ready: float) -> LatencyRecord:
        clocks = (tick_received, inference_done, payload_ready)
        if not all(math.isfinite(float(v)) for v in clocks):
            raise ValueError("latency timestamps must be finite")
        if not tick_received <= inference_done <= payload_ready:
            raise ValueError("latency timestamps must be monotonic and ordered")
        inference = (inference_done - tick_received) * 1000
        total = (payload_ready - tick_received) * 1000
        row = LatencyRecord(
            tick_received, inference_done, payload_ready,
            inference, total, total > self.threshold_ms,
        )
        self.logger({
            "event": "latency",
            "inference_ms": inference,
            "end_to_end_ms": total,
            "alert_over_200ms": row.alert_over_200ms,
        })
        return row


class DerivHistoryClient:
    def __init__(
        self,
        app_id: str | None = None,
        timeout_seconds: float = 20,
        max_attempts: int = 4,
        retry_base_seconds: float = 1.5,
    ):
        # Public market-data calls do not require authorization or an App ID. If an
        # optional legacy App ID is supplied, try that documented endpoint first;
        # otherwise prefer Deriv's currently documented public no-query-string URL.
        self.app_id = app_id or os.getenv("DERIV_APP_ID") or None
        if self.app_id is not None and (not self.app_id.isdigit()):
            raise ValueError("app_id must be numeric when supplied")
        if not math.isfinite(float(timeout_seconds)) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 8:
            raise ValueError("max_attempts must be an integer in 1..8")
        if not math.isfinite(float(retry_base_seconds)) or retry_base_seconds < 1.0:
            raise ValueError("retry_base_seconds must be finite and >= 1 second")
        if self.app_id:
            self.urls = (f"{DERIV_WS_BASE}?app_id={self.app_id}", DERIV_WS_FALLBACK_BASE)
        else:
            self.urls = (DERIV_WS_FALLBACK_BASE, DERIV_WS_BASE)
        self.url = self.urls[0]  # compatibility alias for diagnostics/tests
        self.timeout = float(timeout_seconds)
        self.max_attempts = max_attempts
        self.retry_base_seconds = float(retry_base_seconds)

    def _connect(self):
        """Connect to documented public v3 endpoints in order, failing with bounded diagnostics."""
        failures: list[str] = []
        for url in self.urls:
            try:
                return websocket.create_connection(url, timeout=self.timeout)
            except Exception as exc:
                failures.append(f"{url.split('?')[0]}: {type(exc).__name__}")
        raise ConnectionError("all public Deriv WebSocket endpoints failed: " + "; ".join(failures))

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, (ConnectionError, TimeoutError, OSError, websocket.WebSocketException)):
            return True
        if isinstance(exc, RuntimeError):
            # Only retry explicit transient throttling/server codes. Other API errors
            # (unknown symbol, invalid range, permissions) should fail immediately.
            message = str(exc).lower()
            return any(token in message for token in (
                "ratelimit", "rate limit", "toomanyrequests", "too many requests",
                "servererror", "server error", "temporarily unavailable",
            ))
        return False

    def request_message(self, request: dict, *, expected_msg_type: str) -> dict:
        """Send one public market-data request with bounded retries and exponential backoff."""
        if not isinstance(request, dict) or not request:
            raise ValueError("request must be a non-empty dictionary")
        if not isinstance(expected_msg_type, str) or not expected_msg_type:
            raise ValueError("expected_msg_type must be a non-empty string")
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            ws = None
            try:
                ws = self._connect()
                ws.send(json.dumps(request, separators=(",", ":")))
                deadline = time.monotonic() + self.timeout
                while time.monotonic() < deadline:
                    message = json.loads(ws.recv())
                    if message.get("error"):
                        error = message["error"]
                        raise RuntimeError(
                            f"Deriv API error: {error.get('code', 'unknown')}: {error.get('message', '')}"
                        )
                    if message.get("msg_type") == expected_msg_type:
                        return message
                raise TimeoutError(f"timed out waiting for Deriv {expected_msg_type} response")
            except Exception as exc:
                last_error = exc
                if not self._is_retryable(exc) or attempt + 1 >= self.max_attempts:
                    raise
                delay = min(self.retry_base_seconds * (2 ** attempt), 30.0)
                # The same bounded delay applies to transport failures and explicit
                # transient provider throttling. Never spin/retry immediately.
                time.sleep(delay)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass
        assert last_error is not None
        raise last_error

    @staticmethod
    def _validate_range(start_epoch: int, end_epoch: int, granularity: int) -> tuple[int, int]:
        if isinstance(start_epoch, bool) or isinstance(end_epoch, bool):
            raise ValueError("epochs must be integer UTC seconds")
        if not isinstance(start_epoch, (int, np.integer)) or not isinstance(end_epoch, (int, np.integer)):
            raise ValueError("epochs must be integer UTC seconds")
        if granularity not in (60, 900):
            raise ValueError("granularity must be 60 or 900 seconds")
        start, end = int(start_epoch), int(end_epoch)
        if start < 0 or start >= end:
            raise ValueError("start_epoch must be nonnegative and precede end_epoch")
        if start % granularity or end % granularity:
            raise ValueError("start and end must align exactly to candle boundaries")
        return start, end

    @staticmethod
    def _validate_frame(df: pd.DataFrame, start_epoch: int, end_epoch: int, granularity: int) -> pd.DataFrame:
        missing = set(("epoch", *OHLC_COLUMNS)) - set(df.columns)
        if missing:
            raise ValueError(f"Deriv response missing fields: {sorted(missing)}")
        df = df.copy()
        df["epoch"] = pd.to_numeric(df["epoch"], errors="raise").astype("int64")
        for col in OHLC_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="raise")
        if df["epoch"].duplicated().any():
            raise ValueError("duplicate candle timestamps")
        df = df.sort_values("epoch").reset_index(drop=True)
        prices = df[list(OHLC_COLUMNS)].to_numpy(dtype=float)
        if not np.isfinite(prices).all():
            raise ValueError("candle prices contain missing or non-finite values")
        if (prices <= 0).any():
            raise ValueError("candle prices must be positive")
        if (df["high"] < df[["open", "close", "low"]].max(axis=1)).any():
            raise ValueError("invalid OHLC high")
        if (df["low"] > df[["open", "close", "high"]].min(axis=1)).any():
            raise ValueError("invalid OHLC low")
        expected = list(range(start_epoch, end_epoch + 1, granularity))
        actual = df["epoch"].astype(int).tolist()
        if actual != expected:
            raise ValueError(
                f"history does not exactly cover requested interval: expected {len(expected)} bars, got {len(actual)}"
            )
        df["timestamp"] = pd.to_datetime(df["epoch"], unit="s", utc=True)
        # Deriv synthetic-index candles do not provide exchange-traded volume.
        df["volume"] = np.nan
        return df[DATA_COLUMNS].reset_index(drop=True)

    def candles(
        self, symbol: str, start_epoch: int, end_epoch: int,
        granularity: int = 60, count: int = 5000,
    ) -> pd.DataFrame:
        start, end = self._validate_range(start_epoch, end_epoch, granularity)
        if not isinstance(symbol, str) or not symbol or len(symbol) > 30 or not symbol.replace("_", "").isalnum():
            raise ValueError("symbol must be a short Deriv market symbol")
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 5000:
            raise ValueError("count must be an integer from 1 to 5000")
        expected_count = ((end - start) // granularity) + 1
        if expected_count > count:
            raise ValueError("requested range exceeds count; use backfill() to fetch bounded chunks")

        request = {
            "ticks_history": symbol,
            "start": start,
            "end": end,
            "style": "candles",
            "granularity": int(granularity),
            # Exact start/end bounds define this paginated chunk. subscribe=0 makes
            # the request one-shot; no live stream is opened.
            "adjust_start_time": 0,
            "subscribe": 0,
            "req_id": 1,
        }
        message = self.request_message(request, expected_msg_type="candles")
        frame = pd.DataFrame(message.get("candles", []))
        if frame.empty:
            raise ValueError("Deriv returned no candles")
        return self._validate_frame(frame, start, end, granularity)

    def backfill(
        self, symbol: str, start_epoch: int, end_epoch: int,
        granularity: int = 60, bars_per_request: int = 4500,
        request_delay_seconds: float = 1.5,
    ) -> pd.DataFrame:
        """Chunk a long history interval without overlap, pausing between requests."""
        start, end = self._validate_range(start_epoch, end_epoch, granularity)
        if not 100 <= bars_per_request <= 5000:
            raise ValueError("bars_per_request must be in 100..5000")
        if isinstance(request_delay_seconds, bool) or not math.isfinite(float(request_delay_seconds)) or request_delay_seconds < 1.5:
            raise ValueError("request_delay_seconds must be finite and at least 1.5 seconds")
        chunk_seconds = (bars_per_request - 1) * granularity
        frames: list[pd.DataFrame] = []
        cursor = start
        while cursor <= end:
            if frames:
                time.sleep(float(request_delay_seconds))
            stop = min(cursor + chunk_seconds, end)
            frames.append(self.candles(
                symbol, cursor, stop,
                granularity=granularity,
                count=bars_per_request,
            ))
            cursor = stop + granularity
        if not frames:
            raise ValueError("empty requested interval")
        out = pd.concat(frames, ignore_index=True).sort_values("epoch").reset_index(drop=True)
        expected = list(range(start, end + 1, granularity))
        actual = out["epoch"].astype(int).tolist()
        if len(actual) != len(set(actual)):
            raise ValueError("joined history contains duplicate timestamps")
        if actual != expected:
            raise ValueError("joined history is incomplete or irregular; reject dataset")
        return out[DATA_COLUMNS]


def persist_history(
    frame: pd.DataFrame, csv_path: str | Path, *, symbol: str,
    granularity: int, start_epoch: int, end_epoch: int,
) -> dict:
    """Atomically write normalized bars plus a manifest with exact coverage and SHA-256 hashes."""
    start, end = DerivHistoryClient._validate_range(start_epoch, end_epoch, granularity)
    checked = DerivHistoryClient._validate_frame(frame, start, end, granularity)
    if not symbol or len(symbol) > 30 or not symbol.replace("_", "").isalnum():
        raise ValueError("invalid Deriv symbol")
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    checked.to_csv(temporary, index=False, date_format="%Y-%m-%dT%H:%M:%S%z")
    temporary.replace(path)
    data_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "schema": "atos.deriv_history_manifest.v1",
        "source": "Deriv ticks_history style=candles",
        "source_commit": os.getenv("GITHUB_SHA", "").strip() or "LOCAL_UNPINNED",
        "symbol": symbol,
        "granularity_seconds": granularity,
        "requested_start_epoch": start,
        "requested_end_epoch": end,
        "requested_start_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "requested_end_utc": datetime.fromtimestamp(end, timezone.utc).isoformat(),
        "first_returned_epoch": int(checked.epoch.iloc[0]),
        "last_returned_epoch": int(checked.epoch.iloc[-1]),
        "bar_count": int(len(checked)),
        "missing_intervals": 0,
        "duplicate_timestamps": 0,
        "coverage_complete": True,
        "volume_semantics": "unavailable_not_fabricated",
        "data_sha256": data_hash,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    manifest["manifest_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    tmp_manifest = manifest_path.with_name(manifest_path.name + ".tmp")
    tmp_manifest.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp_manifest.replace(manifest_path)
    return manifest


def time_call(fn: Callable, *args, **kwargs):
    """Measure local monotonic elapsed time; this does not prove broker receipt/execution."""
    start = time.monotonic()
    result = fn(*args, **kwargs)
    return result, (time.monotonic() - start) * 1000
