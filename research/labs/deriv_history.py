"""Public historical OHLC ingestion for ATOS research.

Deriv market data uses the unauthenticated public WebSocket. This module never
requests authorize, balance, portfolio, proposal, buy, sell, or account endpoints.
"""
from __future__ import annotations

import asyncio
import json
import os
from math import isfinite
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import websockets

from .atos_smc_v2 import ResearchDataError, validate_ohlc

DERIV_PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
DEFAULT_PAGE_SIZE = 5000
DEFAULT_MAX_HISTORY_PAGES = 600

# Yahoo Finance intraday interval identifiers used by the retained window validator.
YFINANCE_INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}


class DerivHistoryError(RuntimeError):
    pass


def _normalize_deriv_pip_size(value: Any) -> float:
    """Validate active_symbols.pip_size as the provider-published price increment."""
    try:
        pip_size = float(value)
    except (TypeError, ValueError) as exc:
        raise DerivHistoryError("DERIV_PIP_SIZE_UNKNOWN") from exc
    if not isfinite(pip_size) or pip_size <= 0:
        raise DerivHistoryError("DERIV_PIP_SIZE_INVALID")
    return pip_size


def _epoch(value: datetime | pd.Timestamp) -> int:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError("HISTORY_BOUNDARY_MUST_BE_TIMEZONE_AWARE")
    return int(stamp.tz_convert("UTC").timestamp())


async def _request(ws: Any, payload: dict[str, Any], *, timeout_seconds: float = 30.0) -> dict[str, Any]:
    await ws.send(json.dumps(payload, separators=(",", ":")))
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
        response = json.loads(raw)
        if not isinstance(response, dict):
            raise DerivHistoryError("DERIV_RESPONSE_NOT_OBJECT")
        if response.get("req_id") == payload.get("req_id"):
            if response.get("error"):
                error = response["error"]
                code = error.get("code", "UNKNOWN") if isinstance(error, dict) else "UNKNOWN"
                message = error.get("message", "") if isinstance(error, dict) else ""
                raise DerivHistoryError(f"DERIV_API_ERROR:{code}:{message}")
            return response
        # Public history requests are non-subscribing. Ignore unrelated server
        # messages only while waiting for this request id.
        if response.get("error"):
            raise DerivHistoryError("DERIV_UNCORRELATED_API_ERROR")


async def fetch_deriv_symbol_metadata(
    symbol: str,
) -> dict[str, Any]:
    """Resolve the exact active Deriv symbol and its published pip-size metadata."""
    if not symbol or not symbol.strip():
        raise ValueError("DERIV_SYMBOL_REQUIRED")
    async with websockets.connect(
        DERIV_PUBLIC_WS_URL, ping_interval=20, close_timeout=10, max_size=5_000_000
    ) as ws:
        response = await _request(ws, {"active_symbols": "brief", "req_id": 1})
    rows = response.get("active_symbols")
    if not isinstance(rows, list):
        raise DerivHistoryError("DERIV_ACTIVE_SYMBOLS_MISSING")
    matches = [
        row for row in rows
        if isinstance(row, dict)
        and str(row.get("underlying_symbol") or row.get("symbol") or "").upper() == symbol.strip().upper()
    ]
    if len(matches) != 1:
        raise DerivHistoryError("DERIV_SYMBOL_NOT_UNIQUELY_ACTIVE")
    row = matches[0]
    pip_value = row.get("pip_size", row.get("pip"))
    pip_size = _normalize_deriv_pip_size(pip_value)
    return {
        "symbol": str(row.get("underlying_symbol") or row.get("symbol")),
        "display_name": str(row.get("underlying_symbol_name") or row.get("display_name") or ""),
        "market": row.get("market"),
        "submarket": row.get("submarket"),
        "pip_size": pip_size,
        "price_increment": pip_size,
        "price_increment_source": "Deriv active_symbols.pip_size",
        "price_increment_status": "PROVIDER_PUBLISHED_PIP_SIZE",
        "tick_size_source_field": "pip_size" if "pip_size" in row else "pip",
        "metadata_observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "metadata_source": "Deriv public active_symbols",
        "authenticated": False,
        "endpoint": DERIV_PUBLIC_WS_URL,
    }


async def fetch_deriv_candles(
    symbol: str,
    start: datetime | pd.Timestamp,
    end: datetime | pd.Timestamp,
    *,
    granularity_seconds: int = 60,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_HISTORY_PAGES,
    request_delay_seconds: float = 1.25,
) -> pd.DataFrame:
    """Refuse legacy historical candle ingestion under ATOS v2.0 data controls."""
    if not symbol or not symbol.strip():
        raise ValueError("DERIV_SYMBOL_REQUIRED")
    if granularity_seconds != 60:
        raise ValueError("ATOS_PRIMARY_HISTORY_GRANULARITY_MUST_BE_60_SECONDS")
    if not 100 <= page_size <= 5000:
        raise ValueError("DERIV_PAGE_SIZE_MUST_BE_100_TO_5000")
    if max_pages < 1 or max_pages > DEFAULT_MAX_HISTORY_PAGES:
        raise ValueError("DERIV_MAX_PAGES_OUT_OF_RANGE")
    if not isfinite(float(request_delay_seconds)) or not 0.0 <= request_delay_seconds <= 10.0:
        raise ValueError("DERIV_REQUEST_DELAY_OUT_OF_RANGE")
    start_epoch, end_epoch = _epoch(start), _epoch(end)
    if end_epoch <= start_epoch:
        raise ValueError("DERIV_HISTORY_WINDOW_INVALID")
    raise DerivHistoryError(
        "DERIV_HISTORICAL_INGESTION_QUARANTINED: current legacy downloader is not an "
        "approved ephemeral cross-source calibrator and must not persist raw API content"
    )


def _validate_yfinance_window(
    start: datetime | pd.Timestamp,
    end: datetime | pd.Timestamp,
    interval: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    if start_ts.tzinfo is None or end_ts.tzinfo is None:
        raise ValueError("YFINANCE_BOUNDARIES_MUST_BE_TIMEZONE_AWARE")
    if end_ts <= start_ts:
        raise ValueError("YFINANCE_HISTORY_WINDOW_INVALID")
    if interval in YFINANCE_INTRADAY_INTERVALS and (end_ts - start_ts) > pd.Timedelta(days=60):
        raise ValueError("YFINANCE_INTRADAY_HISTORY_LIMIT_EXCEEDED_60_DAYS")
    return start_ts, end_ts


def fetch_yfinance_ohlc(
    symbol: str,
    start: datetime | pd.Timestamp,
    end: datetime | pd.Timestamp,
    *,
    interval: str = "1m",
) -> pd.DataFrame:
    """Fetch Yahoo OHLC for Yahoo-listed instruments, not Deriv synthetic indices.

    Yahoo documents a 60-day maximum for intraday intervals. A 90-day 1m request
    is rejected instead of silently returning a shorter sample.
    """
    start_ts, end_ts = _validate_yfinance_window(start, end, interval)
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("YFINANCE_DEPENDENCY_NOT_INSTALLED") from exc

    data = yf.download(
        tickers=symbol,
        start=start_ts.to_pydatetime(),
        end=end_ts.to_pydatetime(),
        interval=interval,
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
        keepna=True,
        multi_level_index=False,
    )
    if data is None or data.empty:
        raise RuntimeError("YFINANCE_HISTORY_EMPTY")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data.columns = [str(column).lower() for column in data.columns]
    if not isinstance(data.index, pd.DatetimeIndex) or data.index.tz is None:
        raise ResearchDataError("YFINANCE_RETURNED_NAIVE_OR_INVALID_TIMESTAMPS")
    data.index = data.index.tz_convert("UTC")
    frame = validate_ohlc(data, expected_minutes=1 if interval == "1m" else 0)
    frame.attrs["symbol"] = symbol
    frame.attrs["provider"] = "Yahoo Finance via yfinance"
    frame.attrs["authenticated"] = False
    frame.attrs["interval"] = interval
    return frame


def fetch_deriv_candles_sync(*args: Any, **kwargs: Any) -> pd.DataFrame:
    """Synchronous CLI wrapper around fetch_deriv_candles."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(fetch_deriv_candles(*args, **kwargs))
    raise RuntimeError("SYNC_WRAPPER_CANNOT_RUN_INSIDE_ACTIVE_EVENT_LOOP; AWAIT_ASYNC_FUNCTION")
