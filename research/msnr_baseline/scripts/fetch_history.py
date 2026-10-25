#!/usr/bin/env python3
"""Fetch public R_100 OHLC candles using Deriv's current unauthenticated Options API.

This program is market-data-only: no account token, OTP, balance request, proposal,
buy, sell, contract purchase, or order placement is implemented.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import sys
from datetime import date, datetime, time as dtime, timezone
from pathlib import Path
from typing import Any

import websockets

PUBLIC_WS = "wss://api.derivws.com/trading/v1/options/ws/public"
UNDERLYING_SYMBOL = "R_100"
INTERVALS = {"1m": 60, "15m": 900}
DEFAULT_START = "2022-10-21"
DEFAULT_END = "2024-10-21"  # Exclusive UTC midnight boundary; bars on this date are excluded.
CHUNK_DAYS = 3
PACING_SECONDS = 1.5
REQUIRED_CANDLE_FIELDS = ("open", "high", "low", "close", "epoch")
CSV_FIELDS = ("epoch", "open", "high", "low", "close")

class FetchError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def utc_epoch(day: date) -> int:
    return int(datetime.combine(day, dtime.min, tzinfo=timezone.utc).timestamp())


def utc_window_epochs(start_day_inclusive: date, end_day_exclusive: date) -> tuple[int, int]:
    """Convert a UTC calendar window to [start, end) epoch bounds.

    The end date is an exclusive midnight boundary. For example,
    2022-10-21 through 2024-10-21 means end_epoch=2024-10-21T00:00:00Z;
    no bars from 2024-10-21 itself are included.
    """
    if end_day_exclusive <= start_day_inclusive:
        raise FetchError("End date is an exclusive UTC boundary and must be after start date.")
    return utc_epoch(start_day_inclusive), utc_epoch(end_day_exclusive)


def validate_active_symbols_pip_size(pip_size: Any) -> float:
    """Validate active_symbols.pip_size as the API's price-unit increment.

    Important: active_symbols.pip_size is the renamed legacy `pip` value. The
    similarly named pip_size in some tick/history response objects describes
    display precision; that is a distinct field in a different response shape.
    This value is not a measured bid/ask spread.
    """
    if isinstance(pip_size, bool) or not isinstance(pip_size, (int, float)):
        raise FetchError("active_symbols.pip_size must be a numeric price-unit increment.")
    value = float(pip_size)
    if not math.isfinite(value) or value <= 0:
        raise FetchError(f"Invalid active_symbols pip_size price unit: {pip_size!r}")
    return value


def normalize_candles(candles: Any, start_epoch: int, end_exclusive: int,
                      granularity: int) -> list[dict[str, int | float]]:
    if any(isinstance(value, bool) or not isinstance(value, int)
           for value in (start_epoch, end_exclusive, granularity)):
        raise FetchError("Requested start, exclusive end, and granularity must be JSON-compatible integers.")
    if not 0 <= start_epoch < end_exclusive <= 9999999999:
        raise FetchError("Requested half-open epoch window is invalid or outside the supported range.")
    if granularity not in (60, 900):
        raise FetchError("Unsupported granularity; only 60-second and 900-second bars are in scope.")
    if start_epoch % granularity or end_exclusive % granularity or (end_exclusive - start_epoch) % granularity:
        raise FetchError("Requested half-open epoch window must be aligned to the chosen granularity.")
    if not isinstance(candles, list) or not candles:
        raise FetchError("Response has no non-empty candles array; dataset cannot be declared complete.")
    out: list[dict[str, int | float]] = []
    for candle in candles:
        if not isinstance(candle, dict):
            raise FetchError("Candle entry is not an object.")
        missing = [key for key in REQUIRED_CANDLE_FIELDS if key not in candle]
        if missing:
            raise FetchError(f"Current API candle response is missing required fields: {missing}")
        epoch_raw = candle["epoch"]
        if isinstance(epoch_raw, bool) or not isinstance(epoch_raw, int):
            raise FetchError("Candle epoch must be a JSON integer; strings, floats, and booleans are rejected.")
        if not 0 <= epoch_raw <= 9999999999:
            raise FetchError(f"Candle epoch is outside the supported range: {epoch_raw!r}")
        raw_prices = tuple(candle[k] for k in ("open", "high", "low", "close"))
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in raw_prices):
            raise FetchError("Candle OHLC values must be JSON numbers; strings and booleans are rejected.")
        try:
            epoch = epoch_raw
            px = {k: float(candle[k]) for k in ("open", "high", "low", "close")}
        except (TypeError, ValueError, OverflowError) as exc:
            raise FetchError("Candle contains an invalid numeric value.") from exc
        if not all(math.isfinite(v) and v > 0 for v in px.values()):
            raise FetchError(f"Non-positive or non-finite R_100 price at epoch {epoch}.")
        if px["high"] < max(px["open"], px["close"]) or px["low"] > min(px["open"], px["close"]) or px["high"] < px["low"]:
            raise FetchError(f"OHLC invariant failed at epoch {epoch}.")
        if epoch % granularity != 0:
            raise FetchError(f"Candle epoch {epoch} is not aligned to {granularity}s interval.")
        if not start_epoch <= epoch < end_exclusive:
            raise FetchError(
                f"Candle epoch {epoch} is outside requested half-open range "
                f"[{start_epoch}, {end_exclusive}); refusing out-of-window data."
            )
        out.append({"epoch": epoch, **px})
    out.sort(key=lambda r: int(r["epoch"]))
    epochs = [int(r["epoch"]) for r in out]
    if len(set(epochs)) != len(epochs):
        raise FetchError("Duplicate candle epochs returned inside a chunk.")
    expected = list(range(start_epoch, end_exclusive, granularity))
    if epochs != expected:
        if not epochs:
            detail = (
                f"no candle epochs returned; requested [{start_epoch}, {end_exclusive}) "
                f"at {granularity}s"
            )
        else:
            missing_count = len(set(expected).difference(epochs))
            extra_count = len(set(epochs).difference(expected))
            detail = f"expected {len(expected)} aligned candles, got {len(epochs)}; missing={missing_count}, extra={extra_count}"
        raise FetchError(f"Chunk continuity failure: {detail}.")
    return out


def build_candle_payload(start_epoch: int, end_exclusive: int, granularity: int) -> dict[str, int | str]:
    """Build a current-API, bounded history request without legacy/invalid fields."""
    if any(isinstance(value, bool) or not isinstance(value, int)
           for value in (start_epoch, end_exclusive, granularity)):
        raise FetchError("Candle request start, exclusive end, and granularity must be integers.")
    if not 0 <= start_epoch < end_exclusive <= 9999999999:
        raise FetchError("Candle request half-open epoch window is invalid or outside the supported range.")
    if granularity not in (60, 900):
        raise FetchError("Invalid candle request granularity.")
    if (start_epoch % granularity or end_exclusive % granularity or
            (end_exclusive - start_epoch) % granularity):
        raise FetchError("Candle request half-open epoch window must be aligned to the chosen granularity.")
    count = (end_exclusive - start_epoch) // granularity
    if count < 1 or count > 5000:
        raise FetchError(f"Requested chunk has {count} candles; current cap is 5000.")
    # Deriv's own SmartCharts request builder removes count whenever start is set.
    # With start+end bounds, count=5000 can make this gateway return the latest
    # default window rather than the requested interval. The bounded request
    # therefore omits count and verifies the complete returned epoch sequence.
    return {
        "ticks_history": UNDERLYING_SYMBOL,
        "start": int(start_epoch),
        # Use an explicit end epoch so each three-day chunk is strictly bounded.
        "end": str(end_exclusive - granularity),
        "style": "candles",
        "granularity": int(granularity),
        "req_id": 1,
    }


async def request_chunk(start_epoch: int, end_exclusive: int, granularity: int,
                        timeout: float, retries: int, retry_delay: float) -> tuple[list[dict[str, int | float]], int]:
    last_error = "unknown error"
    for attempt in range(1, retries + 2):
        try:
            async with websockets.connect(
                PUBLIC_WS, open_timeout=timeout, close_timeout=5,
                ping_interval=20, ping_timeout=20, max_size=8 * 1024 * 1024,
            ) as ws:
                # Explicit epoch end bounds make each three-day chunk independent;
                # end="latest" would not bound each historical chunk.
                payload = build_candle_payload(start_epoch, end_exclusive, granularity)
                await ws.send(json.dumps(payload, separators=(",", ":")))
                response_raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                try:
                    response = json.loads(response_raw)
                except json.JSONDecodeError as exc:
                    raise FetchError("Server returned non-JSON WebSocket data.") from exc
                if not isinstance(response, dict):
                    raise FetchError("Response was not a JSON object.")
                if response.get("error"):
                    err = response["error"]
                    raise FetchError(f"API error {err.get('code', 'unknown')}: {err.get('message', err)}")
                # Current API docs do not guarantee echo_req; no logic depends on it.
                if response.get("msg_type") not in ("candles", "history"):
                    raise FetchError(f"Unexpected response message type: {response.get('msg_type')!r}")
                try:
                    rows = normalize_candles(response.get("candles"), start_epoch, end_exclusive, granularity)
                except FetchError as exc:
                    # Keep diagnostics limited to the public history request shape;
                    # never dump arbitrary responses, credentials, or unrelated fields.
                    if (
                        "outside requested half-open range" in str(exc)
                        or "no epochs inside requested interval" in str(exc)
                    ):
                        echo = response.get("echo_req")
                        allowed = ("ticks_history", "start", "end", "style", "granularity", "count",
                                   "adjust_start_time", "subscribe", "req_id")
                        echo_summary = (
                            {key: echo[key] for key in allowed if key in echo}
                            if isinstance(echo, dict) else None
                        )
                        raise FetchError(
                            f"{exc}; response_msg_type={response.get('msg_type')!r}; "
                            f"response_req_id={response.get('req_id')!r}; "
                            f"echo_req_subset={json.dumps(echo_summary, sort_keys=True, separators=(',', ':'))}"
                        ) from exc
                    raise
                return rows, attempt
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt <= retries:
                await asyncio.sleep(max(PACING_SECONDS, retry_delay * min(2 ** (attempt - 1), 8)))
    raise FetchError(f"chunk failed after {retries + 1} attempts: {last_error}")


async def fetch_interval(label: str, granularity: int, start_day: date, end_day: date,
                         out_dir: Path, pip_size_price: float, active_symbols_response_sha256: str,
                         active_symbol_row: dict[str, Any], timeout: float, retries: int,
                         retry_delay: float) -> dict[str, Any]:
    start_epoch, end_exclusive = utc_window_epochs(start_day, end_day)
    # Fixed canonical filenames are hashed in the evidence manifest; exact date
    # bounds remain in the manifest so filenames cannot imply unverified coverage.
    stem = f"R_100_{label}"
    csv_path = out_dir / f"{stem}.csv"
    partial_path = out_dir / f"{stem}.csv.partial"
    manifest_path = out_dir / f"{stem}.manifest.json"
    failure_path = out_dir / f"{stem}.failure.json"
    for p in (csv_path, partial_path, manifest_path, failure_path):
        if p.exists():
            raise FetchError(f"Refusing to overwrite existing evidence: {p}")
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[dict[str, Any]] = []
    previous_request = None
    total_rows = 0
    cursor = start_epoch
    chunk_no = 0
    failure: str | None = None
    try:
        with partial_path.open("x", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, lineterminator="\n")
            writer.writeheader()
            while cursor < end_exclusive:
                chunk_no += 1
                chunk_end = min(cursor + CHUNK_DAYS * 86400, end_exclusive)
                if previous_request is not None:
                    elapsed = asyncio.get_running_loop().time() - previous_request
                    if elapsed < PACING_SECONDS:
                        await asyncio.sleep(PACING_SECONDS - elapsed)
                label_start = datetime.fromtimestamp(cursor, timezone.utc).isoformat()
                label_end = datetime.fromtimestamp(chunk_end, timezone.utc).isoformat()
                print(f"[{label}] chunk {chunk_no}: {label_start} → {label_end}", flush=True)
                rows, attempts = await request_chunk(cursor, chunk_end, granularity, timeout, retries, retry_delay)
                previous_request = asyncio.get_running_loop().time()
                writer.writerows(rows)
                f.flush()
                total_rows += len(rows)
                chunks.append({"chunk": chunk_no, "start_epoch": cursor, "end_epoch_inclusive": chunk_end - granularity,
                               "expected_rows": len(range(cursor, chunk_end, granularity)), "actual_rows": len(rows),
                               "status": "OK", "attempts": attempts, "sha256_chunk_rows": hashlib.sha256(
                                   json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()})
                cursor = chunk_end
            f.flush()
            os.fsync(f.fileno())
        os.replace(partial_path, csv_path)
        manifest = {
            "schema": "atos.deriv_history_manifest.v3",
            "status": "FETCHED_AWAITING_INDEPENDENT_VERIFICATION",
            "underlying_symbol": UNDERLYING_SYMBOL,
            "timeframe": label,
            "granularity_seconds": granularity,
            "start_date_utc_inclusive": start_day.isoformat(),
            "end_date_utc_exclusive": end_day.isoformat(),
            "range_end_exclusive_epoch": end_exclusive,
            "endpoint": PUBLIC_WS,
            "transport": "Deriv current Options API public WebSocket",
            "authentication": "none",
            "account_token_used": False,
            "otp_used": False,
            "live_orders_submitted": False,
            "pip_size_price_from_active_symbols": pip_size_price,
            "pip_size_source": "active_symbols.pip_size from the current active_symbols response is a price-unit increment; not a measured spread",
            "pip_size_metadata_available": True,
            "active_symbols_response_file": "R_100_active_symbols_response.json",
            "active_symbols_response_sha256": active_symbols_response_sha256,
            "active_symbol_metadata_row": active_symbol_row,
            "row_count": total_rows,
            "expected_row_count": (end_exclusive - start_epoch) // granularity,
            "first_epoch": start_epoch if total_rows else None,
            "last_epoch": end_exclusive - granularity if total_rows else None,
            "csv_path": str(csv_path),
            "csv_bytes": csv_path.stat().st_size,
            "csv_sha256": sha256_file(csv_path),
            "chunks": chunks,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "caveat": "Source and continuity still require independent verification; hash proves file integrity, not economic validity.",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"WROTE {csv_path} rows={total_rows} sha256={manifest['csv_sha256']}", flush=True)
        print(f"WROTE {manifest_path}", flush=True)
        return {"csv": str(csv_path), "manifest": str(manifest_path), "rows": total_rows,
                "sha256": manifest["csv_sha256"], "status": manifest["status"]}
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        failure_record = {
            "schema": "atos.deriv_history_fetch_failure.v1", "status": "FAILED_CLOSED",
            "underlying_symbol": UNDERLYING_SYMBOL, "timeframe": label,
            "endpoint": PUBLIC_WS, "error": failure, "completed_chunks": chunks,
            "partial_path": str(partial_path) if partial_path.exists() else None,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "live_tokens_used": False, "live_orders_submitted": False,
        }
        failure_path.write_text(json.dumps(failure_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise


async def fetch_active_symbols_pip_size(timeout: float, retries: int, retry_delay: float) -> tuple[float, str, dict[str, Any]]:
    """Use the current active_symbols field names; never look up a legacy symbol field."""
    last_error = "unknown error"
    for attempt in range(1, retries + 2):
        try:
            async with websockets.connect(
                PUBLIC_WS, open_timeout=timeout, close_timeout=5,
                ping_interval=20, ping_timeout=20, max_size=8 * 1024 * 1024,
            ) as ws:
                await ws.send(json.dumps({"active_symbols": "brief", "req_id": 98765}))
                response_raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                response = json.loads(response_raw)
                if not isinstance(response, dict):
                    raise FetchError("active_symbols response was not a JSON object.")
                if response.get("error"):
                    err = response["error"]
                    raise FetchError(f"active_symbols API error {err.get('code', 'unknown')}: {err.get('message', err)}")
                if response.get("msg_type") != "active_symbols":
                    raise FetchError(f"Expected active_symbols response, got {response.get('msg_type')!r}.")
                rows = response.get("active_symbols")
                if not isinstance(rows, list):
                    raise FetchError("active_symbols response has no active_symbols array.")
                matches = [row for row in rows if isinstance(row, dict) and row.get("underlying_symbol") == UNDERLYING_SYMBOL]
                if len(matches) != 1:
                    raise FetchError(f"Expected exactly one active-symbol row for R_100; received {len(matches)}.")
                raw_value = matches[0].get("pip_size")
                return validate_active_symbols_pip_size(raw_value), response_raw, matches[0]
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt <= retries:
                await asyncio.sleep(retry_delay * min(2 ** (attempt - 1), 8))
    raise FetchError(f"Could not verify active_symbols.pip_size price unit through the new public API: {last_error}")


async def async_main(args: argparse.Namespace) -> int:
    start_day = date.fromisoformat(args.start_date)
    end_day = date.fromisoformat(args.end_date)
    if end_day <= start_day:
        raise FetchError("End date is an exclusive UTC boundary and must be after start date.")
    if args.timeout <= 0 or args.retries < 0 or args.retry_delay < 0 or args.chunk_days != CHUNK_DAYS:
        raise FetchError("Timeout/retries invalid, or chunk_days differs from frozen three-day policy.")
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    active_symbols_path = out_dir / "R_100_active_symbols_response.json"
    run_failure_path = out_dir / "fetch_run.failure.json"
    if active_symbols_path.exists() or run_failure_path.exists():
        raise FetchError(f"Refusing to overwrite existing public API evidence in {out_dir}; choose a fresh output directory.")
    try:
        pip_size_price, active_symbols_response_raw, active_symbol_row = await fetch_active_symbols_pip_size(
            args.timeout, args.retries, args.retry_delay)
    except Exception as exc:
        # Preserve failed attempts as evidence, including DNS/connectivity failures
        # before any market-data rows were returned. This record is never eligible data.
        failure_record = {
            "schema": "atos.deriv_history_fetch_run_failure.v1",
            "status": "FAILED_CLOSED",
            "underlying_symbol": UNDERLYING_SYMBOL,
            "endpoint": PUBLIC_WS,
            "output_dir": str(out_dir),
            "requested_start_date_utc_inclusive": args.start_date,
            "requested_end_date_utc_exclusive": args.end_date,
            "granularities_requested_seconds": list(INTERVALS.values()),
            "error": f"{type(exc).__name__}: {exc}",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "authentication": "none",
            "account_token_used": False,
            "otp_used": False,
            "live_orders_submitted": False,
            "market_data_received": False,
        }
        run_failure_path.write_text(json.dumps(failure_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise
    # Preserve the exact UTF-8 message text returned by the public API for audit hashing.
    active_symbols_path.write_bytes(active_symbols_response_raw.encode("utf-8"))
    active_symbols_response_sha256 = sha256_file(active_symbols_path)
    print(f"Current-API active_symbols pip_size price unit for R_100: {pip_size_price}; response_sha256={active_symbols_response_sha256}", flush=True)
    results = []
    # Enforce pacing between the metadata request and the first history request,
    # and again at each timeframe boundary. fetch_interval paces all later chunks.
    for label, granularity in INTERVALS.items():
        await asyncio.sleep(PACING_SECONDS)
        results.append(await fetch_interval(label, granularity, start_day, end_day,
                                            out_dir, pip_size_price, active_symbols_response_sha256,
                                            active_symbol_row, args.timeout, args.retries, args.retry_delay))
    print(json.dumps({"results": results}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument(
        "--end-date",
        default=DEFAULT_END,
        help="Exclusive UTC date boundary at 00:00:00; bars on this date are excluded",
    )
    parser.add_argument("--output-dir", default="data/raw")
    parser.add_argument("--chunk-days", type=int, default=CHUNK_DAYS)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-delay", type=float, default=2.0)
    args = parser.parse_args()
    try:
        return asyncio.run(async_main(args))
    except (FetchError, ValueError, OSError) as exc:
        print(f"HISTORY FETCH FAILED CLOSED: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted; any .partial file is unverified and ineligible for simulation.", file=sys.stderr)
        return 130

if __name__ == "__main__":
    raise SystemExit(main())
