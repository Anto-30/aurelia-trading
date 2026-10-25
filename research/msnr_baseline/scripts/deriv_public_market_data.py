#!/usr/bin/env python3
"""Deriv current-API public market-data client; intentionally cannot trade or authenticate.

Only active_symbols, ticks_history and ticks are supported. This module does not
accept credentials, connect to authenticated WebSocket URLs, use OTPs, inspect an
account, request balances, or submit trading actions.
"""
from __future__ import annotations

import asyncio
import json
import math
from typing import Any, AsyncIterator

import websockets

PUBLIC_WS = "wss://api.derivws.com/trading/v1/options/ws/public"
PUBLIC_OPERATIONS = frozenset({"active_symbols", "ticks_history", "ticks"})
FORBIDDEN_KEYS = frozenset({
    "authorization", "authorize", "token", "auth_token", "loginid", "otp",
    "buy", "sell", "proposal", "balance", "portfolio", "statement", "transaction",
    "contract_update", "contract_update_history", "cancel", "forget", "proposal_open_contract",
    "account", "account_id", "accountid", "trading_platform_accounts", "password", "secret",
})
COMMON_KEYS = frozenset({"req_id", "passthrough"})
CANDLE_FIELDS = ("open", "high", "low", "close", "epoch")


class PublicMarketDataError(RuntimeError):
    """Public data request or response failed validation."""


def _check_no_forbidden_nested_keys(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise PublicMarketDataError(f"Forbidden auth/account/trading key at {path}.{key}.")
            _check_no_forbidden_nested_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _check_no_forbidden_nested_keys(child, f"{path}[{i}]")


def validate_public_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict) or not payload:
        raise PublicMarketDataError("Request payload must be a non-empty JSON object.")
    _check_no_forbidden_nested_keys(payload)
    operations = PUBLIC_OPERATIONS.intersection(payload.keys())
    if len(operations) != 1:
        raise PublicMarketDataError(f"Exactly one public operation is required: {sorted(PUBLIC_OPERATIONS)}")
    operation = next(iter(operations))
    operation_keys = {
        "active_symbols": {"active_symbols", "contract_type"},
        "ticks": {"ticks", "subscribe"},
        # ticks_history remains the request field; do not rename it globally.
        "ticks_history": {"ticks_history", "start", "end", "style", "granularity", "count", "subscribe", "adjust_start_time"},
    }[operation]
    unknown = set(payload) - operation_keys - COMMON_KEYS
    if unknown:
        raise PublicMarketDataError(f"Unsupported fields in public request: {sorted(unknown)}")
    if operation == "active_symbols":
        if payload[operation] not in ("brief", "full"):
            raise PublicMarketDataError("active_symbols must be 'brief' or 'full'.")
        if "contract_type" in payload and not isinstance(payload["contract_type"], list):
            raise PublicMarketDataError("active_symbols contract_type, when provided, must be an array.")
    elif operation == "ticks":
        symbols = payload[operation]
        valid_symbols = (isinstance(symbols, str) and bool(symbols)) or (
            isinstance(symbols, list) and bool(symbols) and all(isinstance(x, str) and x for x in symbols)
        )
        if not valid_symbols:
            raise PublicMarketDataError("ticks must name a symbol or non-empty list of symbols.")
        if "subscribe" in payload and payload["subscribe"] != 1:
            raise PublicMarketDataError("Current ticks subscriptions accept subscribe=1 only.")
    elif operation == "ticks_history":
        if not isinstance(payload[operation], str) or not payload[operation]:
            raise PublicMarketDataError("ticks_history requires its short symbol as a string value.")
        if payload.get("style", "ticks") not in ("ticks", "candles"):
            raise PublicMarketDataError("ticks_history style must be 'ticks' or 'candles'.")
        if "start" in payload and (not isinstance(payload["start"], int) or payload["start"] < 0):
            raise PublicMarketDataError("ticks_history start must be a non-negative integer epoch.")
        if "end" in payload and not (payload["end"] == "latest" or str(payload["end"]).isdigit()):
            raise PublicMarketDataError("ticks_history end must be 'latest' or a numeric epoch string.")
        if "count" in payload and (not isinstance(payload["count"], int) or not 1 <= payload["count"] <= 5000):
            raise PublicMarketDataError("ticks_history count must be between 1 and 5000.")
        if "granularity" in payload:
            # Current API removes the legacy fixed enum. A positive integer candle width is accepted.
            if isinstance(payload["granularity"], bool) or not isinstance(payload["granularity"], int) or payload["granularity"] <= 0:
                raise PublicMarketDataError("ticks_history granularity must be a positive integer.")
        # Current API accepts 0 or 1 for these optional flags; for one-shot requests
        # this client omits subscribe rather than relying on either value.
        for key in ("subscribe", "adjust_start_time"):
            if key in payload and (isinstance(payload[key], bool) or payload[key] not in (0, 1)):
                raise PublicMarketDataError(f"{key} must be 0 or 1.")


def validate_candle_response(message: dict[str, Any]) -> list[dict[str, float | int]]:
    if not isinstance(message, dict):
        raise PublicMarketDataError("Candles response must be a JSON object.")
    if message.get("msg_type") != "candles":
        raise PublicMarketDataError(f"Expected candles response, got {message.get('msg_type')!r}.")
    candles = message.get("candles")
    if not isinstance(candles, list) or not candles:
        raise PublicMarketDataError("Candles response must contain a non-empty candles array.")
    output: list[dict[str, float | int]] = []
    for i, candle in enumerate(candles):
        if not isinstance(candle, dict) or any(field not in candle for field in CANDLE_FIELDS):
            raise PublicMarketDataError(f"Candle {i} is missing a required OHLC/epoch field.")

        # JSON schema types are part of provenance: do not coerce strings, floats,
        # or booleans into integers/prices before validating the raw API response.
        epoch_raw = candle["epoch"]
        if isinstance(epoch_raw, bool) or not isinstance(epoch_raw, int):
            raise PublicMarketDataError(f"Candle {i} epoch must be a JSON integer.")
        if not 0 <= epoch_raw <= 9999999999:
            raise PublicMarketDataError(f"Candle {i} epoch is outside the supported range.")

        raw_prices = tuple(candle[k] for k in ("open", "high", "low", "close"))
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in raw_prices):
            raise PublicMarketDataError(f"Candle {i} OHLC values must be JSON numbers.")
        op, hi, lo, cl = (float(value) for value in raw_prices)
        if not all(math.isfinite(value) and value > 0 for value in (op, hi, lo, cl)):
            raise PublicMarketDataError(f"Candle {i} contains a non-finite or non-positive value.")
        if hi < max(op, cl) or lo > min(op, cl) or hi < lo:
            raise PublicMarketDataError(f"Candle {i} violates OHLC invariants.")
        output.append({"epoch": epoch_raw, "open": op, "high": hi, "low": lo, "close": cl})
    epochs = [int(row["epoch"]) for row in output]
    if any(b <= a for a, b in zip(epochs, epochs[1:])):
        raise PublicMarketDataError("Candle epochs must be strictly increasing with no duplicates.")
    return output


def validate_history_response(message: dict[str, Any]) -> tuple[list[float], list[int]]:
    if not isinstance(message, dict):
        raise PublicMarketDataError("History response must be a JSON object.")
    if message.get("msg_type") != "history":
        raise PublicMarketDataError(f"Expected history response, got {message.get('msg_type')!r}.")
    history = message.get("history")
    if not isinstance(history, dict):
        raise PublicMarketDataError("History response is missing the history object.")
    prices, times = history.get("prices"), history.get("times")
    if not isinstance(prices, list) or not isinstance(times, list):
        raise PublicMarketDataError("Current ticks-history schema requires both prices and times arrays.")
    if len(prices) != len(times):
        raise PublicMarketDataError("history.prices and history.times lengths differ.")
    clean_prices: list[float] = []
    clean_times: list[int] = []
    for price, epoch in zip(prices, times):
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise PublicMarketDataError("History price must be a JSON number, not a string or boolean.")
        if isinstance(epoch, bool) or not isinstance(epoch, int):
            raise PublicMarketDataError("History time must be a JSON integer epoch.")
        px = float(price)
        if not math.isfinite(px) or px <= 0 or not 0 <= epoch <= 9999999999:
            raise PublicMarketDataError("History price/time must be finite, positive price and in-range integer epoch.")
        clean_prices.append(px)
        clean_times.append(epoch)
    if any(b <= a for a, b in zip(clean_times, clean_times[1:])):
        raise PublicMarketDataError("History times must be strictly increasing with no duplicates.")
    return clean_prices, clean_times


class DerivPublicMarketDataClient:
    """One-shot public requests and bounded reconnecting tick observation.

    Deliberately no credential parameters, account state, OTP retrieval, or trade
    operations. The client rejects authenticated endpoint overrides.
    """
    def __init__(self, *, endpoint: str = PUBLIC_WS, connect_timeout: float = 10.0, response_timeout: float = 15.0):
        if endpoint != PUBLIC_WS:
            raise PublicMarketDataError("Client is pinned to the official public Options API endpoint.")
        if connect_timeout <= 0 or response_timeout <= 0:
            raise PublicMarketDataError("Timeouts must be positive.")
        self.endpoint = endpoint
        self.connect_timeout = connect_timeout
        self.response_timeout = response_timeout
        self._req_id = 1000

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def request(self, payload: dict[str, Any], *, expected_msg_type: str | None = None) -> dict[str, Any]:
        validate_public_payload(payload)
        req_id = self._next_id()
        request = {**payload, "req_id": req_id}
        try:
            async with websockets.connect(
                self.endpoint, open_timeout=self.connect_timeout, close_timeout=3,
                ping_interval=20, ping_timeout=20, max_size=8 * 1024 * 1024,
            ) as ws:
                await ws.send(json.dumps(request, separators=(",", ":")))
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=self.response_timeout)
                    try:
                        message = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise PublicMarketDataError("The public WebSocket returned non-JSON data.") from exc
                    if not isinstance(message, dict):
                        raise PublicMarketDataError("The public WebSocket must return a JSON object.")
                    if message.get("error"):
                        error = message["error"]
                        raise PublicMarketDataError(f"Deriv public API error {error.get('code', 'unknown')}: {error.get('message', error)}")
                    if message.get("req_id") not in (None, req_id):
                        continue
                    if expected_msg_type and message.get("msg_type") != expected_msg_type:
                        continue
                    if not isinstance(message.get("msg_type"), str):
                        raise PublicMarketDataError("Current API response must contain msg_type.")
                    if message["msg_type"] == "candles":
                        validate_candle_response(message)
                    elif message["msg_type"] == "history":
                        validate_history_response(message)
                    return message
        except asyncio.CancelledError:
            raise
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as exc:
            raise PublicMarketDataError(f"Public market-data connection failed: {type(exc).__name__}: {exc}") from exc

    async def active_symbols(self, *, full: bool = False) -> dict[str, Any]:
        message = await self.request({"active_symbols": "full" if full else "brief"}, expected_msg_type="active_symbols")
        rows = message.get("active_symbols")
        if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get("underlying_symbol"), str) for row in rows):
            raise PublicMarketDataError("Current active-symbol response must provide underlying_symbol rows.")
        return message

    async def ticks_history(self, *, underlying_symbol: str, start_epoch: int, end_epoch: int,
                            granularity_seconds: int, style: str = "candles", count: int = 5000) -> dict[str, Any]:
        if not underlying_symbol or start_epoch < 0 or end_epoch < start_epoch:
            raise PublicMarketDataError("Invalid history symbol or epoch bounds.")
        if style not in ("candles", "ticks") or not 1 <= count <= 5000:
            raise PublicMarketDataError("Invalid style/count; count must be between 1 and 5000.")
        payload: dict[str, Any] = {
            "ticks_history": underlying_symbol, "start": int(start_epoch), "end": str(int(end_epoch)),
            "style": style, "count": int(count),
        }
        if style == "candles":
            if granularity_seconds <= 0:
                raise PublicMarketDataError("Candle granularity must be positive.")
            payload["granularity"] = int(granularity_seconds)
        return await self.request(payload, expected_msg_type="candles" if style == "candles" else "history")

    async def stream_ticks(self, *, underlying_symbol: str, max_reconnects: int = 5,
                           initial_backoff_seconds: float = 1.0) -> AsyncIterator[dict[str, Any]]:
        if not underlying_symbol or max_reconnects < 0 or initial_backoff_seconds <= 0:
            raise PublicMarketDataError("Invalid stream/reconnect parameters.")
        failures = 0
        while True:
            try:
                async with websockets.connect(
                    self.endpoint, open_timeout=self.connect_timeout, close_timeout=3,
                    ping_interval=20, ping_timeout=20, max_size=8 * 1024 * 1024,
                ) as ws:
                    await ws.send(json.dumps({"ticks": underlying_symbol, "subscribe": 1, "req_id": self._next_id()}))
                    async for raw in ws:
                        try:
                            message = json.loads(raw)
                        except json.JSONDecodeError as exc:
                            raise PublicMarketDataError("Tick stream returned non-JSON data.") from exc
                        if not isinstance(message, dict):
                            raise PublicMarketDataError("Tick stream message is not an object.")
                        if message.get("error"):
                            error = message["error"]
                            raise PublicMarketDataError(f"Deriv tick stream error {error.get('code', 'unknown')}: {error.get('message', error)}")
                        if message.get("msg_type") != "tick":
                            continue
                        tick = message.get("tick")
                        if not isinstance(tick, dict):
                            continue
                        if "quote" not in tick or "epoch" not in tick:
                            raise PublicMarketDataError("Tick observation requires quote and epoch for research use.")
                        quote, epoch_f = float(tick["quote"]), float(tick["epoch"])
                        if not math.isfinite(quote) or quote <= 0 or not math.isfinite(epoch_f) or int(epoch_f) != epoch_f:
                            raise PublicMarketDataError("Tick quote/epoch is invalid.")
                        yield {"msg_type": "tick", "underlying_symbol_requested": underlying_symbol,
                               "epoch": int(epoch_f), "quote": quote, "raw": message}
                failures += 1
            except asyncio.CancelledError:
                raise
            except (OSError, asyncio.TimeoutError, websockets.WebSocketException, PublicMarketDataError):
                failures += 1
            if failures > max_reconnects:
                raise PublicMarketDataError(f"Tick stream exceeded max reconnect count ({max_reconnects}).")
            await asyncio.sleep(min(initial_backoff_seconds * (2 ** (failures - 1)), 30.0))
