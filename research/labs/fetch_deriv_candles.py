"""Fetch and freeze Deriv 1-minute candles for research only.

This collector has no account authentication, trading, or order-submission path.
It writes the exact WebSocket response text into an append-only JSONL record,
an OHLC-only Parquet file, and a manifest with SHA-256 digests and coverage checks.
Deriv candle payloads do not include trade volume; do not infer it from OHLC.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import time as time_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import websockets

WS_URL = "wss://ws.derivws.com/websockets/v3"
DEFAULT_APP_ID = "1089"  # Deriv documents this ID for testing, not production releases.
DEFAULT_SYMBOL = "1HZ75V"
GRANULARITY_SECONDS = 60
MAX_BARS_PER_PAGE = 4000
REQUEST_TIMEOUT_SECONDS = 30


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and require an explicit UTC offset."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"TIMESTAMP_MUST_INCLUDE_TIMEZONE:{value}")
    return parsed.astimezone(timezone.utc)


def minute_epoch(value: datetime) -> int:
    seconds = int(value.timestamp())
    return seconds - seconds % GRANULARITY_SECONDS


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_candles(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["open", "high", "low", "close"],
                            index=pd.DatetimeIndex([], tz="UTC", name="timestamp"))
    frame = pd.DataFrame(records)
    required = {"epoch", "open", "high", "low", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("CANDLE_FIELDS_MISSING:" + ",".join(sorted(missing)))
    frame["epoch"] = pd.to_numeric(frame["epoch"], errors="raise").astype("int64")
    if (frame["epoch"] % GRANULARITY_SECONDS != 0).any():
        raise ValueError("CANDLE_EPOCH_NOT_MINUTE_ALIGNED")
    frame["timestamp"] = pd.to_datetime(frame["epoch"], unit="s", utc=True)
    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any() or not frame[column].map(
            lambda value: math.isfinite(float(value))
        ).all():
            raise ValueError(f"OHLC_NONFINITE_OR_MISSING:{column}")
        if (frame[column] <= 0).any():
            raise ValueError(f"OHLC_NONPOSITIVE:{column}")
    if ((frame["high"] < frame[["open", "close", "low"]].max(axis=1)) |
            (frame["low"] > frame[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("OHLC_BAR_INCONSISTENT")
    frame = frame.set_index("timestamp")[["open", "high", "low", "close"]]
    if frame.index.has_duplicates:
        duplicate_sample = frame.index[frame.index.duplicated()].astype(str).tolist()[:10]
        raise ValueError("DUPLICATE_CANDLE_TIMESTAMPS:" + ",".join(duplicate_sample))
    return frame.sort_index()


async def fetch_deriv_candles(
    symbol: str,
    app_id: str,
    start_epoch: int,
    end_epoch: int,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / f"{symbol}_1m_raw.jsonl"
    parquet_path = output_dir / f"{symbol}_1m.parquet"
    manifest_path = output_dir / f"{symbol}_1m_manifest.json"

    if end_epoch < start_epoch:
        raise ValueError("END_BEFORE_START")
    if start_epoch % 60 or end_epoch % 60:
        raise ValueError("START_AND_END_MUST_BE_MINUTE_ALIGNED")

    raw_records: list[dict[str, Any]] = []
    all_candles: list[dict[str, Any]] = []
    req_id = 1

    async with websockets.connect(
        f"{WS_URL}?app_id={app_id}",
        open_timeout=REQUEST_TIMEOUT_SECONDS,
        close_timeout=5,
        ping_interval=20,
        ping_timeout=20,
        max_size=16 * 1024 * 1024,
    ) as socket:
        async def request(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            nonlocal req_id
            request_id = req_id
            req_id += 1
            payload = {**payload, "req_id": request_id}
            await socket.send(json.dumps(payload, separators=(",", ":"), sort_keys=True))
            deadline = asyncio.get_running_loop().time() + REQUEST_TIMEOUT_SECONDS
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError(f"DERIV_REQUEST_TIMEOUT:req_id={request_id}")
                raw_text = await asyncio.wait_for(socket.recv(), timeout=remaining)
                message = json.loads(raw_text)
                if message.get("req_id") == request_id:
                    return raw_text, message
                # Ignore unrelated unsolicited messages; no subscription is requested.

        symbol_raw, symbol_response = await request({
            "active_symbols": "brief",
            "product_type": "basic",
        })
        raw_records.append({
            "kind": "active_symbols",
            "request": {"active_symbols": "brief", "product_type": "basic"},
            "response_raw": symbol_raw,
        })
        if "error" in symbol_response:
            raise RuntimeError("ACTIVE_SYMBOLS_API_ERROR:" +
                               str(symbol_response["error"].get("message", symbol_response["error"])))
        active_symbols = symbol_response.get("active_symbols", [])
        match = next((entry for entry in active_symbols if entry.get("symbol") == symbol), None)
        if match is None:
            available_sample = [entry.get("symbol") for entry in active_symbols[:20]]
            raise ValueError(f"SYMBOL_NOT_RETURNED_BY_ACTIVE_SYMBOLS:{symbol};sample={available_sample}")

        page_start = start_epoch
        page_number = 0
        while page_start <= end_epoch:
            page_end = min(end_epoch, page_start + (MAX_BARS_PER_PAGE - 1) * GRANULARITY_SECONDS)
            request_payload = {
                "ticks_history": symbol,
                "start": page_start,
                "end": page_end,
                "count": MAX_BARS_PER_PAGE,
                "style": "candles",
                "granularity": GRANULARITY_SECONDS,
                "subscribe": 0,
            }
            raw_text, response = await request(request_payload)
            raw_records.append({
                "kind": "candles",
                "page": page_number,
                "request": request_payload,
                "response_raw": raw_text,
            })
            if "error" in response:
                error = response["error"]
                raise RuntimeError(f"DERIV_CANDLE_API_ERROR:{error.get('code')}:{error.get('message')}")
            page_candles = response.get("candles", [])
            for candle in page_candles:
                epoch = int(candle["epoch"])
                if not page_start <= epoch <= page_end:
                    raise ValueError(
                        f"CANDLE_OUTSIDE_REQUESTED_PAGE:epoch={epoch},start={page_start},end={page_end}"
                    )
            all_candles.extend(page_candles)
            page_number += 1
            page_start = page_end + GRANULARITY_SECONDS
            # Keep the unauthenticated public endpoint below bursty request rates.
            await asyncio.sleep(0.1)

    frame = validate_candles(all_candles)
    if frame.empty:
        raise ValueError("NO_CANDLES_RETURNED")

    expected_index = pd.date_range(
        start=pd.to_datetime(start_epoch, unit="s", utc=True),
        end=pd.to_datetime(end_epoch, unit="s", utc=True),
        freq="min",
        name="timestamp",
    )
    missing_index = expected_index.difference(frame.index)
    unexpected_index = frame.index.difference(expected_index)
    if len(unexpected_index):
        raise ValueError("CANDLE_OUTSIDE_REQUESTED_RANGE_AFTER_COMBINE")

    # Persist exact response text as strings inside JSONL. Hash the resulting byte
    # stream, not a re-serialized parsed payload, so this digest is reproducible.
    with raw_path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in raw_records:
            stream.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
    frame.to_parquet(parquet_path, engine="pyarrow", compression="zstd", index=True)

    manifest: dict[str, Any] = {
        "schema": "aurelia.deriv_candles_manifest.v1",
        "source": "Deriv public WebSocket API",
        "websocket_url": f"{WS_URL}?app_id={app_id}",
        "authentication_used": False,
        "app_id_note": "1089 is documented by Deriv for testing; do not use as a production release ID.",
        "symbol": symbol,
        "display_name": match.get("display_name"),
        "granularity_seconds": GRANULARITY_SECONDS,
        "timezone": "UTC",
        "timestamp_representation": "Unix epoch seconds converted to timezone-aware UTC",
        "bar_timestamp_semantics": "Candle epoch treated as candle-open time; confirm against API schema before using as signal timestamps.",
        "data_columns": list(frame.columns),
        "volume_available": "volume" in frame.columns,
        "requested_start_utc": pd.to_datetime(start_epoch, unit="s", utc=True).isoformat(),
        "requested_end_utc": pd.to_datetime(end_epoch, unit="s", utc=True).isoformat(),
        "actual_start_utc": frame.index[0].isoformat(),
        "actual_end_utc": frame.index[-1].isoformat(),
        "expected_bar_count": int(len(expected_index)),
        "actual_bar_count": int(len(frame)),
        "duplicate_timestamps": 0,
        "missing_bar_count_in_requested_range": int(len(missing_index)),
        "first_missing_timestamps_utc": [value.isoformat() for value in missing_index[:50]],
        "raw_payload_file": raw_path.name,
        "raw_payload_sha256": sha256_file(raw_path),
        "parquet_file": parquet_path.name,
        "parquet_sha256": sha256_file(parquet_path),
        "raw_response_count_including_symbol_list": len(raw_records),
        "validation_status": "PASS" if len(missing_index) == 0 else "FAIL_MISSING_MINUTE_BARS",
        "research_only": True,
        "capital_authority": False,
        "live_execution": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, allow_nan=False))
    if len(missing_index):
        raise ValueError(f"MISSING_MINUTE_BARS:{len(missing_index)}")
    return manifest


async def async_main(args: argparse.Namespace) -> int:
    start = minute_epoch(parse_utc(args.start))
    if args.end:
        end = minute_epoch(parse_utc(args.end))
        # Never include the currently forming candle, even if the supplied end is recent.
        latest_closed_start = minute_epoch(datetime.now(timezone.utc)) - GRANULARITY_SECONDS
        end = min(end, latest_closed_start)
    else:
        end = minute_epoch(datetime.now(timezone.utc)) - GRANULARITY_SECONDS
    try:
        await fetch_deriv_candles(args.symbol, args.app_id, start, end, args.output_dir)
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "ABORTED",
            "reason": type(exc).__name__,
            "detail": str(exc),
            "research_only": True,
            "capital_authority": False,
            "live_execution": False,
        }, indent=2))
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--app-id", default=DEFAULT_APP_ID)
    parser.add_argument("--start", default="2025-10-01T00:00:00Z",
                        help="UTC ISO-8601 time aligned to the minute; default is 2025-10-01")
    parser.add_argument("--end", default=None, help="Optional UTC ISO-8601 upper bound, floored to minute")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/deriv"))
    args = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
