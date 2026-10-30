"""Read-only public Deriv candle retrieval.

No account token, OTP, proposal, buy, sell, or account operation is used.
The returned candles are raw market observations and must pass the repository's
data validation gate before strategy research.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import pandas as pd
from websockets.sync.client import connect

PUBLIC_WS_ENDPOINT = "wss://api.derivws.com/trading/v1/options/ws/public"
ALLOWED_GRANULARITIES = {60, 120, 180, 300, 600, 900, 1800, 3600, 7200, 14400, 28800, 86400}


@dataclass(frozen=True)
class CandleBatch:
    frame: pd.DataFrame
    symbol: str
    granularity_seconds: int
    raw_response_sha256: str
    retrieved_at_utc: str
    server_time_epoch: int
    last_bar_closed: bool
    endpoint: str = PUBLIC_WS_ENDPOINT
    authentication: str = "PUBLIC_NO_AUTH"


class DerivPublicDataClient:
    """Small request/response client using the documented public market-data endpoint."""

    def __init__(self, timeout_seconds: float = 20.0, endpoint: str = PUBLIC_WS_ENDPOINT):
        if timeout_seconds <= 0:
            raise ValueError("TIMEOUT_MUST_BE_POSITIVE")
        self.timeout_seconds = float(timeout_seconds)
        self.endpoint = endpoint
        self._next_req_id = 1

    def _request(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        request = dict(payload)
        request["req_id"] = self._next_req_id
        expected_id = self._next_req_id
        self._next_req_id += 1

        try:
            with connect(
                self.endpoint,
                open_timeout=self.timeout_seconds,
                close_timeout=self.timeout_seconds,
            ) as websocket:
                websocket.send(json.dumps(request, separators=(",", ":"), sort_keys=True))
                while True:
                    raw = websocket.recv(timeout=self.timeout_seconds)
                    response = json.loads(raw)
                    if response.get("req_id") != expected_id:
                        continue
                    if "error" in response:
                        detail = response["error"].get("message", "UNKNOWN_DERIV_API_ERROR")
                        raise RuntimeError("DERIV_API_ERROR:" + str(detail))
                    return response, raw
        except TimeoutError as exc:
            raise TimeoutError("DERIV_PUBLIC_API_REQUEST_TIMEOUT") from exc

    def active_symbols(self) -> list[dict[str, Any]]:
        response, _ = self._request({"active_symbols": "brief"})
        symbols = response.get("active_symbols")
        if not isinstance(symbols, list):
            raise RuntimeError("DERIV_ACTIVE_SYMBOLS_RESPONSE_INVALID")
        return symbols

    def server_time_epoch(self) -> int:
        response, _ = self._request({"time": 1})
        value = response.get("time")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError("DERIV_SERVER_TIME_RESPONSE_INVALID")
        return int(value)

    def fetch_candles(
        self,
        symbol: str,
        granularity_seconds: int = 900,
        count: int = 5000,
    ) -> CandleBatch:
        requested_symbol = symbol.strip()
        if not requested_symbol:
            raise ValueError("SYMBOL_REQUIRED")
        if granularity_seconds not in ALLOWED_GRANULARITIES:
            raise ValueError("GRANULARITY_NOT_SUPPORTED_BY_DERIV_TICKS_HISTORY")
        if not isinstance(count, int) or count < 1:
            raise ValueError("CANDLE_COUNT_MUST_BE_POSITIVE")

        symbols = self.active_symbols()
        available = {
            str(item.get("underlying_symbol") or item.get("symbol"))
            for item in symbols
            if item.get("underlying_symbol") or item.get("symbol")
        }
        if requested_symbol not in available:
            raise ValueError("SYMBOL_NOT_RETURNED_BY_ACTIVE_SYMBOLS:" + requested_symbol)

        response, raw_response = self._request({
            "ticks_history": requested_symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "style": "candles",
            "granularity": granularity_seconds,
        })
        candles = response.get("candles")
        if not isinstance(candles, list) or not candles:
            raise RuntimeError("DERIV_CANDLE_RESPONSE_EMPTY_OR_INVALID")

        raw_hash = sha256(raw_response.encode("utf-8")).hexdigest()
        frame = pd.DataFrame(candles)
        required = {"epoch", "open", "high", "low", "close"}
        if not required.issubset(frame.columns):
            raise RuntimeError("DERIV_CANDLE_SCHEMA_INVALID")
        timestamps = pd.to_datetime(pd.to_numeric(frame.pop("epoch"), errors="raise"), unit="s", utc=True)
        frame.index = pd.DatetimeIndex(timestamps, name="timestamp")
        server_time = self.server_time_epoch()
        order_is_valid = frame.index.is_monotonic_increasing and not frame.index.has_duplicates
        last_bar_epoch = int(pd.Timestamp(frame.index[-1]).timestamp())
        last_bar_closed = order_is_valid and last_bar_epoch + granularity_seconds <= server_time
        # Do not sort, deduplicate, forward-fill, or repair observations here.
        frame.attrs["deriv_symbol"] = requested_symbol
        frame.attrs["deriv_granularity_seconds"] = granularity_seconds
        frame.attrs["raw_response_sha256"] = raw_hash

        return CandleBatch(
            frame=frame,
            symbol=requested_symbol,
            granularity_seconds=granularity_seconds,
            raw_response_sha256=raw_hash,
            retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
            server_time_epoch=server_time,
            last_bar_closed=last_bar_closed,
        )
