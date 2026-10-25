#!/usr/bin/env python3
"""Fail-closed R_100 historical candle capture with an unauthenticated probe."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import websockets

SYMBOL = "R_100"
STYLE = "candles"
GRANULARITY = 60
START_EPOCH = 1666310400  # 2022-10-21 00:00:00 UTC
END_EPOCH = 1729468800    # 2024-10-21 00:00:00 UTC
MAX_COUNT = 5000
MAX_PAGES = 1000
RESPONSE_TIMEOUT_SECONDS = 30
PROBE_TIMEOUT_SECONDS = 15
RATE_LIMIT_DELAY_SECONDS = 0.5
PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
CANDLE_FIELDS = ("epoch", "open", "high", "low", "close")


class GateFailure(RuntimeError):
    """An empirical gate stopped without fabricating verified evidence."""

    def __init__(self, stage: str, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.details = details or {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise GateFailure("schema", "INVALID_NUMERIC_FIELD", f"Invalid {field} value") from exc
    if not number.is_finite():
        raise GateFailure("schema", "NONFINITE_NUMERIC_FIELD", f"Non-finite {field} value")
    return number


def validate_response(response: dict[str, Any], expected_req_id: int) -> list[dict[str, Any]]:
    response_req_id = response.get("req_id")
    if response_req_id is not None and response_req_id != expected_req_id:
        raise GateFailure(
            "response_correlation",
            "REQ_ID_MISMATCH",
            "Response request identifier does not match the request",
            {"expected_req_id": expected_req_id, "response_req_id": response_req_id},
        )

    if response.get("error") or response.get("errors"):
        error = response.get("error", response.get("errors"))
        raise GateFailure(
            "api",
            "API_ERROR",
            "Deriv returned an API error",
            {"api_error": error},
        )

    candles = response.get("candles")
    if not isinstance(candles, list):
        raise GateFailure(
            "schema",
            "CANDLES_ARRAY_MISSING",
            "Successful response did not contain a candles array",
            {"response_keys": sorted(response.keys())},
        )

    for index, candle in enumerate(candles):
        if not isinstance(candle, dict) or not all(field in candle for field in CANDLE_FIELDS):
            raise GateFailure(
                "schema",
                "MALFORMED_CANDLE",
                "Candle is missing one or more required fields",
                {"candle_index": index, "required_fields": list(CANDLE_FIELDS)},
            )
        try:
            epoch_decimal = Decimal(str(candle["epoch"]))
            if not epoch_decimal.is_finite() or epoch_decimal != epoch_decimal.to_integral_value():
                raise ValueError("epoch is not an integer")
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise GateFailure(
                "schema", "INVALID_CANDLE_EPOCH", "Candle epoch is not an integer"
            ) from exc
        for field in ("open", "high", "low", "close"):
            safe_decimal(candle[field], field)

    return candles


async def request_json(
    ws: Any,
    payload: dict[str, Any],
    req_id: int,
    raw_handle: Any | None = None,
    timeout_seconds: int = RESPONSE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    requested_at = utc_now()
    response: dict[str, Any] | None = None
    try:
        await ws.send(json.dumps(payload, separators=(",", ":"), sort_keys=True))
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            try:
                message = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise GateFailure(
                    "response_decode", "INVALID_JSON", "WebSocket response was not valid JSON"
                ) from exc
            if not isinstance(message, dict):
                raise GateFailure(
                    "response_decode", "INVALID_RESPONSE_TYPE", "WebSocket response was not an object"
                )
            message_req_id = message.get("req_id")
            if message_req_id is not None and message_req_id != req_id:
                # Ignore unrelated messages only until this request's deadline.
                continue
            response = message
            break
    except Exception as exc:
        if raw_handle is not None:
            raw_handle.write(
                json.dumps(
                    {
                        "requested_at_utc": requested_at,
                        "request": payload,
                        "response": response,
                        "transport_error_type": type(exc).__name__,
                        "transport_error": str(exc)[:500],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
            raw_handle.flush()
        if isinstance(exc, asyncio.TimeoutError):
            raise GateFailure(
                "transport", "WEBSOCKET_RESPONSE_TIMEOUT", "No correlated response arrived before timeout",
                {"req_id": req_id, "timeout_seconds": timeout_seconds},
            ) from exc
        raise

    if raw_handle is not None:
        raw_handle.write(
            json.dumps(
                {"requested_at_utc": requested_at, "request": payload, "response": response},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        raw_handle.flush()

    return response


async def bounded_probe(ws: Any, first_req_id: int = 97001) -> dict[str, Any]:
    """Ask for five one-minute candles bracketing the exact 2022 start epoch."""
    probe_end = START_EPOCH + 4 * GRANULARITY
    payload = {
        "ticks_history": SYMBOL,
        "end": str(probe_end),
        "style": STYLE,
        "granularity": GRANULARITY,
        "count": 5,
        "adjust_start_time": 1,
        "req_id": first_req_id,
    }
    print("PROBE_ENDPOINT=" + PUBLIC_WS_URL)
    print("PROBE_SYMBOL=" + SYMBOL)
    print(f"PROBE_TARGET_EPOCH={START_EPOCH}")
    print("PROBE_TARGET_UTC=" + datetime.fromtimestamp(START_EPOCH, timezone.utc).isoformat())
    print("PROBE_REQUEST=" + json.dumps(payload, sort_keys=True))
    response = await request_json(
        ws, payload, first_req_id, raw_handle=None, timeout_seconds=PROBE_TIMEOUT_SECONDS
    )
    candles = validate_response(response, first_req_id)
    epochs = sorted(int(candle["epoch"]) for candle in candles)
    print("PROBE_RESPONSE_KEYS=" + ",".join(sorted(response.keys())))
    print("PROBE_CANDLE_COUNT=" + str(len(candles)))
    print("PROBE_CANDLE_EPOCHS=" + json.dumps(epochs))
    print("PROBE_CANDLE_UTC=" + json.dumps([
        datetime.fromtimestamp(epoch, timezone.utc).isoformat() for epoch in epochs
    ]))
    if START_EPOCH not in epochs:
        raise GateFailure(
            "historical_probe",
            "TARGET_EPOCH_NOT_RETURNED",
            "The bounded probe did not return the exact requested 2022 start candle",
            {"target_epoch": START_EPOCH, "returned_epochs": epochs},
        )
    print("PROBE_RESULT=PASS")
    return {
        "status": "PASS",
        "target_epoch": START_EPOCH,
        "returned_epochs": epochs,
        "probed_at_utc": utc_now(),
        "response_keys": sorted(response.keys()),
    }


def candle_signature(candle: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(safe_decimal(candle[field], field).normalize()) for field in CANDLE_FIELDS[1:])


def ensure_new_output_dir(output_dir: Path) -> None:
    existing = [
        output_dir / "r100_candles_raw.jsonl",
        output_dir / "R_100_60s_verified.csv",
        output_dir / "verification_manifest.json",
        output_dir / "fetch_failure.json",
    ]
    present = [str(path) for path in existing if path.exists()]
    if present:
        raise GateFailure(
            "preflight",
            "OUTPUT_EXISTS",
            "Refusing to overwrite existing capture artifacts; choose a fresh output directory",
            {"existing_paths": present},
        )


async def fetch_all_candles(
    ws: Any,
    raw_handle: Any,
    first_req_id: int = 97002,
) -> tuple[dict[int, dict[str, Any]], int]:
    cursor = END_EPOCH
    page_count = 0
    by_epoch: dict[int, dict[str, Any]] = {}

    while cursor >= START_EPOCH:
        page_count += 1
        if page_count > MAX_PAGES:
            raise GateFailure(
                "pagination",
                "MAX_PAGE_LIMIT",
                "Pagination exceeded the configured safety limit",
                {"max_pages": MAX_PAGES, "cursor": cursor},
            )

        req_id = first_req_id + page_count
        payload = {
            "ticks_history": SYMBOL,
            "end": str(cursor),
            "style": STYLE,
            "granularity": GRANULARITY,
            "count": MAX_COUNT,
            "adjust_start_time": 1,
            "req_id": req_id,
        }
        response = await request_json(ws, payload, req_id, raw_handle=raw_handle)
        candles = validate_response(response, req_id)
        print(
            f"PAGE={page_count} REQ_ID={req_id} REQUEST_END={cursor} "
            f"RETURNED={len(candles)}"
        )
        if not candles:
            raise GateFailure(
                "pagination",
                "EMPTY_PAGE_BEFORE_START",
                "API returned no candles before the requested start epoch was reached",
                {"page": page_count, "cursor": cursor},
            )

        page_epochs = [int(candle["epoch"]) for candle in candles]
        oldest_epoch = min(page_epochs)
        for candle in candles:
            epoch = int(candle["epoch"])
            if START_EPOCH <= epoch <= END_EPOCH:
                previous = by_epoch.get(epoch)
                if previous is not None and candle_signature(previous) != candle_signature(candle):
                    raise GateFailure(
                        "integrity",
                        "CONFLICTING_DUPLICATE_CANDLE",
                        "Overlapping pages returned different OHLC values for the same epoch",
                        {"epoch": epoch},
                    )
                by_epoch[epoch] = candle

        if oldest_epoch <= START_EPOCH:
            break
        if oldest_epoch >= cursor:
            raise GateFailure(
                "pagination",
                "PAGINATION_STALLED",
                "Oldest candle did not move backward; stopping to avoid an infinite loop",
                {"page": page_count, "cursor": cursor, "oldest_epoch": oldest_epoch},
            )
        cursor = oldest_epoch - 1
        await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)

    return by_epoch, page_count


def write_failure(output_dir: Path, stage: str, code: str, message: str,
                  details: dict[str, Any] | None = None, pages: int | None = None) -> Path | None:
    output_dir.mkdir(parents=True, exist_ok=True)
    failure_path = output_dir / "fetch_failure.json"
    if failure_path.exists():
        print("FAILURE_REPORT_NOT_OVERWRITTEN=" + str(failure_path))
        return None
    raw_path = output_dir / "r100_candles_raw.jsonl"
    report = {
        "status": "BLOCKED",
        "stage": stage,
        "error_code": code,
        "message": message,
        "details": details or {},
        "symbol": SYMBOL,
        "style": STYLE,
        "granularity_s": GRANULARITY,
        "start_epoch_inclusive": START_EPOCH,
        "end_epoch_inclusive": END_EPOCH,
        "recorded_at_utc": utc_now(),
        "page_count": pages,
        "raw_jsonl_path": str(raw_path) if raw_path.exists() else None,
        "raw_jsonl_sha256": sha256_file(raw_path) if raw_path.exists() else None,
        "verified_csv_created": False,
    }
    failure_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return failure_path


async def full_capture(output_dir: Path) -> int:
    ensure_new_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "r100_candles_raw.jsonl"

    async with websockets.connect(
        PUBLIC_WS_URL,
        open_timeout=15,
        close_timeout=5,
        ping_interval=20,
        ping_timeout=15,
        max_size=2**24,
    ) as ws:
        probe = await bounded_probe(ws)
        # The raw capture starts only after the target-epoch probe succeeds.
        with raw_path.open("x", encoding="utf-8", newline="\n") as raw_handle:
            by_epoch, page_count = await fetch_all_candles(ws, raw_handle)

    expected_epochs = list(range(START_EPOCH, END_EPOCH + 1, GRANULARITY))
    if (END_EPOCH - START_EPOCH) % GRANULARITY != 0:
        raise GateFailure(
            "bounds",
            "WINDOW_NOT_ALIGNED",
            "The requested end epoch is not aligned to candle granularity",
        )
    actual_epochs = sorted(by_epoch)
    actual_set = set(actual_epochs)
    expected_set = set(expected_epochs)
    missing = sorted(expected_set - actual_set)
    unexpected = sorted(actual_set - expected_set)
    if missing or unexpected or len(actual_epochs) != len(actual_set):
        details = {
            "expected_candle_count": len(expected_epochs),
            "unique_candle_count": len(actual_set),
            "missing_count": len(missing),
            "missing_first_20_epochs": missing[:20],
            "unexpected_count": len(unexpected),
            "unexpected_first_20_epochs": unexpected[:20],
        }
        write_failure(
            output_dir,
            "continuity",
            "STRICT_CONTINUITY_FAILED",
            "Every expected one-minute epoch must exist exactly once; dataset is not verified",
            details,
            pages=page_count,
        )
        raise GateFailure(
            "continuity",
            "STRICT_CONTINUITY_FAILED",
            "Historical candle continuity check failed; verified CSV was not created",
            details,
        )

    csv_path = output_dir / "R_100_60s_verified.csv"
    with csv_path.open("x", encoding="utf-8", newline="") as csv_handle:
        writer = csv.DictWriter(
            csv_handle,
            fieldnames=["epoch", "open", "high", "low", "close"],
            lineterminator="\n",
        )
        writer.writeheader()
        for epoch in expected_epochs:
            candle = by_epoch[epoch]
            writer.writerow({
                "epoch": epoch,
                "open": str(candle["open"]),
                "high": str(candle["high"]),
                "low": str(candle["low"]),
                "close": str(candle["close"]),
            })

    raw_hash = sha256_file(raw_path)
    csv_hash = sha256_file(csv_path)
    manifest_path = output_dir / "verification_manifest.json"
    manifest = {
        "status": "VERIFIED",
        "continuity_status": "VERIFIED",
        "symbol": SYMBOL,
        "style": STYLE,
        "granularity_s": GRANULARITY,
        "start_epoch_inclusive": START_EPOCH,
        "start_utc": datetime.fromtimestamp(START_EPOCH, timezone.utc).isoformat(),
        "end_epoch_inclusive": END_EPOCH,
        "end_utc": datetime.fromtimestamp(END_EPOCH, timezone.utc).isoformat(),
        "expected_candle_count": len(expected_epochs),
        "total_candles": len(actual_epochs),
        "page_count": page_count,
        "raw_jsonl_path": str(raw_path),
        "raw_jsonl_sha256": raw_hash,
        "verified_csv_path": str(csv_path),
        "verified_csv_sha256": csv_hash,
        "probe": probe,
        "captured_at_utc": utc_now(),
        "verification_rules": {
            "unique_epochs": True,
            "complete_expected_epoch_set": True,
            "conflicting_duplicates_rejected": True,
            "required_fields": list(CANDLE_FIELDS),
            "authenticated_access_used": False,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CAPTURE_RESULT=VERIFIED")
    print(f"TOTAL_CANDLES={len(actual_epochs)}")
    print(f"PAGE_COUNT={page_count}")
    print(f"RAW_JSONL_SHA256={raw_hash}")
    print(f"VERIFIED_CSV_SHA256={csv_hash}")
    print("MANIFEST_PATH=" + str(manifest_path))
    return 0


async def run_probe_only() -> int:
    async with websockets.connect(
        PUBLIC_WS_URL,
        open_timeout=10,
        close_timeout=3,
        ping_interval=20,
        ping_timeout=10,
        max_size=2**20,
    ) as ws:
        await bounded_probe(ws)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--probe-only", action="store_true", help="Run only a bounded 5-candle probe")
    group.add_argument("--full", action="store_true", help="Probe first, then perform the full strict capture")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/r100_historical_2022-2024"),
        help="Fresh output directory; existing capture files are never overwritten",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.probe_only:
            return asyncio.run(run_probe_only())
        return asyncio.run(full_capture(args.output_dir))
    except GateFailure as exc:
        print(f"CAPTURE_RESULT=BLOCKED")
        print(f"BLOCK_STAGE={exc.stage}")
        print(f"BLOCK_CODE={exc.code}")
        print(f"BLOCK_REASON={exc}")
        if exc.details:
            print("BLOCK_DETAILS=" + json.dumps(exc.details, sort_keys=True))
        if args.full:
            failure_path = write_failure(
                args.output_dir, exc.stage, exc.code, str(exc), exc.details
            )
            if failure_path:
                print("FAILURE_REPORT_PATH=" + str(failure_path))
        return 2
    except Exception as exc:
        print("CAPTURE_RESULT=BLOCKED")
        print("BLOCK_STAGE=runtime")
        print("BLOCK_CODE=" + type(exc).__name__)
        print("BLOCK_REASON=" + str(exc)[:1000])
        if args.full:
            failure_path = write_failure(
                args.output_dir, "runtime", type(exc).__name__, str(exc)[:1000]
            )
            if failure_path:
                print("FAILURE_REPORT_PATH=" + str(failure_path))
        return 2


if __name__ == "__main__":
    sys.exit(main())
