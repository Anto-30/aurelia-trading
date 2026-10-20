"""Research-only public Deriv historical candle downloader.

This utility reads public market data only. It does not authenticate, request a
proposal, place/manage trades, or connect to AURELIA's production execution path.
It uses the documented public ticks_history WebSocket message strictly to create
an offline CSV for research; it must not be used as a production API fallback.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import websockets

PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
MAX_CANDLES_PER_REQUEST = 5000


async def _request(ws: Any, payload: dict[str, Any], req_id: int) -> dict[str, Any]:
    request = dict(payload)
    request["req_id"] = req_id
    await ws.send(json.dumps(request))
    while True:
        raw = await ws.recv()
        try:
            response = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Deriv returned invalid JSON for market-data request") from exc
        response_id = response.get("req_id")
        if response_id is not None and response_id != req_id:
            continue
        if "error" in response:
            error = response.get("error") or {}
            raise RuntimeError(f"Deriv market-data error: {error.get('message', 'unknown error')}")
        return response


async def collect_history(
    ws: Any,
    symbol: str,
    start_epoch: int,
    *,
    granularity: int = 60,
    count: int = MAX_CANDLES_PER_REQUEST,
    pause_seconds: float = 0.25,
    max_pages: int = 1000,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fetch backward-paginated candles on an injected WebSocket-like object.

    The symbol must be returned by active_symbols. Pagination moves to the
    second before the oldest candle in the previous response and stops when
    the requested start boundary is reached. Repeated pages fail closed.
    """
    if not symbol or start_epoch < 0:
        raise ValueError("symbol and non-negative start_epoch are required")
    if granularity < 60 or count < 1 or count > MAX_CANDLES_PER_REQUEST:
        raise ValueError("granularity must be >=60 and count must be in [1, 5000]")
    if pause_seconds < 0 or max_pages < 1:
        raise ValueError("pause_seconds must be non-negative and max_pages positive")

    active_response = await _request(
        ws, {"active_symbols": "brief", "product_type": "basic"}, req_id=1
    )
    active = active_response.get("active_symbols")
    if not isinstance(active, list):
        raise RuntimeError("active_symbols response did not contain a symbol list")
    available = {str(item.get("symbol", "")) for item in active if isinstance(item, dict)}
    if symbol not in available:
        raise ValueError(f"Symbol {symbol!r} was not returned by active_symbols; verify the current symbol code")

    rows: dict[int, dict[str, Any]] = {}
    volume_defaulted = 0
    request_end: str | int = "latest"
    previous_oldest: int | None = None
    page_count = 0
    for page in range(max_pages):
        page_count += 1
        response = await _request(
            ws,
            {
                "ticks_history": symbol,
                "style": "candles",
                "granularity": granularity,
                "count": count,
                "end": request_end,
                "adjust_start_time": 1,
            },
            req_id=page + 2,
        )
        candles = response.get("candles")
        if not isinstance(candles, list) or not candles:
            break
        epochs: list[int] = []
        for candle in candles:
            if not isinstance(candle, dict) or "epoch" not in candle:
                raise RuntimeError("Deriv candles response contains a malformed candle")
            epoch = int(candle["epoch"])
            epochs.append(epoch)
            if epoch < start_epoch:
                continue
            vol = candle.get("volume")
            if vol is None:
                volume_defaulted += 1
                vol = 1.0  # explicit bar-count proxy, not traded volume
            row = {
                "timestamp": pd.to_datetime(epoch, unit="s", utc=True).isoformat(),
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(vol),
            }
            if not all(math.isfinite(row[k]) for k in ("open", "high", "low", "close", "volume")):
                raise RuntimeError("Deriv candles response contains non-finite numeric values")
            if (row["high"] < max(row["open"], row["close"])
                    or row["low"] > min(row["open"], row["close"])
                    or row["high"] < row["low"] or row["volume"] < 0):
                raise RuntimeError("Deriv candles response contains invalid OHLCV values")
            rows[epoch] = row

        oldest = min(epochs)
        if oldest <= start_epoch:
            break
        if previous_oldest is not None and oldest >= previous_oldest:
            raise RuntimeError("Historical pagination made no backward progress; refusing a duplicate/gapped dataset")
        previous_oldest = oldest
        request_end = oldest - 1
        if pause_seconds:
            await asyncio.sleep(pause_seconds)
    else:
        raise RuntimeError(f"Historical pagination exceeded max_pages={max_pages}")

    if not rows:
        raise RuntimeError("No candles returned for the requested range")
    df = pd.DataFrame(rows.values()).sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    actual_start = pd.to_datetime(df["timestamp"], utc=True).min()
    actual_end = pd.to_datetime(df["timestamp"], utc=True).max()
    report = {
        "symbol": symbol,
        "granularity_seconds": granularity,
        "requested_start_utc": datetime.fromtimestamp(start_epoch, tz=timezone.utc).isoformat(),
        "actual_start_utc": actual_start.isoformat(),
        "actual_end_utc": actual_end.isoformat(),
        "candles_written": len(df),
        "pages_requested": page_count,
        "rows_without_source_volume_replaced_by_unit_proxy": volume_defaulted,
        "source": "public Deriv ticks_history candle response; research-only",
    }
    if actual_start.timestamp() > start_epoch + granularity:
        report["coverage_warning"] = "Returned history starts after requested boundary; inspect retained history depth/gaps."
    return df, report


async def fetch_history(symbol: str, days: int, granularity: int, pause_seconds: float):
    """Fetch public history with bounded retries for transient connection failures.

    Retries never fabricate or reuse market data. Once connected, protocol,
    symbol, pagination, and data-validation failures still fail immediately.
    """
    if days < 1:
        raise ValueError("days must be >=1")
    start_epoch = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    attempts = 5
    for attempt in range(attempts):
        try:
            async with websockets.connect(
                PUBLIC_WS_URL, ping_interval=20, close_timeout=5, open_timeout=20
            ) as ws:
                return await collect_history(
                    ws, symbol, start_epoch, granularity=granularity,
                    count=MAX_CANDLES_PER_REQUEST, pause_seconds=pause_seconds,
                )
        except websockets.exceptions.InvalidStatus as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is None or status < 500 or attempt == attempts - 1:
                raise
        except (OSError, asyncio.TimeoutError, websockets.exceptions.ConnectionClosedError):
            if attempt == attempts - 1:
                raise
        delay = min(2 ** attempt, 16)
        print(
            json.dumps({
                "event": "transient_public_history_connection_failure",
                "attempt": attempt + 1,
                "max_attempts": attempts,
                "retry_delay_seconds": delay,
            }),
            flush=True,
        )
        await asyncio.sleep(delay)
    raise RuntimeError("Public history connection retries exhausted")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, help="Exact current symbol code, verified by active_symbols")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--granularity", type=int, default=60, help="Candle interval in seconds; 60 = one minute")
    parser.add_argument("--pause-seconds", type=float, default=0.25)
    parser.add_argument("--out", default="R75_6months_1min.csv")
    args = parser.parse_args()

    df, report = asyncio.run(fetch_history(args.symbol, args.days, args.granularity, args.pause_seconds))
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    report["output_path"] = str(path)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
