#!/usr/bin/env python3
"""One-hour, public, unauthenticated R_100 WebSocket stability soak."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import websockets

URL = "wss://api.derivws.com/trading/v1/options/ws/public"
SYMBOL = "R_100"
REQ_ID = 736001
SAMPLE_INTERVAL_SECONDS = 60
MESSAGE_TIMEOUT_SECONDS = 30
MAX_SILENT_SECONDS = 120
MAX_RSS_GROWTH_BYTES = 64 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def current_rss_bytes() -> int | None:
    try:
        for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
            if line.startswith("VmRSS:"):
                fields = line.split()
                return int(fields[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_epoch(value: Any) -> int:
    number = Decimal(str(value))
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError("INVALID_TICK_EPOCH")
    return int(number)


def parse_quote(value: Any) -> Decimal:
    try:
        quote = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("INVALID_TICK_QUOTE") from exc
    if not quote.is_finite():
        raise ValueError("NONFINITE_TICK_QUOTE")
    return quote


async def run_soak(duration_seconds: int, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("OUTPUT_DIR_NOT_EMPTY")
    output_dir.mkdir(parents=True, exist_ok=True)
    events_path = output_dir / "soak_events.jsonl"
    report_path = output_dir / "soak_report.json"

    started_wall = datetime.now(timezone.utc)
    started_mono = time.monotonic()
    deadline = started_mono + duration_seconds
    events: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    tick_count = 0
    message_count = 0
    non_tick_message_count = 0
    last_message_mono: float | None = None
    last_tick_epoch: int | None = None
    subscription_id: str | None = None
    first_rss = current_rss_bytes()
    last_rss = first_rss
    peak_rss = first_rss
    started = False

    def event(event_type: str, **fields: Any) -> None:
        row = {
            "recorded_at_utc": utc_now(),
            "elapsed_seconds": round(time.monotonic() - started_mono, 3),
            "event_type": event_type,
            **fields,
        }
        events.append(row)
        with events_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    def sample() -> None:
        nonlocal last_rss, peak_rss
        rss = current_rss_bytes()
        last_rss = rss
        if rss is not None:
            peak_rss = max(peak_rss or rss, rss)
        row = {
            "sampled_at_utc": utc_now(),
            "elapsed_seconds": round(time.monotonic() - started_mono, 3),
            "messages_received": message_count,
            "ticks_received": tick_count,
            "non_tick_messages": non_tick_message_count,
            "last_message_age_seconds": (
                round(time.monotonic() - last_message_mono, 3)
                if last_message_mono is not None else None
            ),
            "rss_bytes": rss,
            "rss_growth_from_initial_bytes": (
                rss - first_rss if rss is not None and first_rss is not None else None
            ),
            "connection_state": "CONNECTED",
        }
        sample_rows.append(row)
        event("minute_sample", **row)

    try:
        event(
            "soak_start",
            url=URL,
            symbol=SYMBOL,
            requested_duration_seconds=duration_seconds,
            authenticated=False,
            orders_permitted=False,
            subscribe=1,
        )
        async with websockets.connect(
            URL,
            open_timeout=15,
            close_timeout=5,
            ping_interval=20,
            ping_timeout=20,
            max_size=2**20,
        ) as ws:
            connected_mono = time.monotonic()
            started = True
            event("connected", protocol=str(ws.subprotocol or "none"))
            await ws.send(json.dumps({
                "ticks": SYMBOL,
                "subscribe": 1,
                "req_id": REQ_ID,
            }, separators=(",", ":"), sort_keys=True))
            last_sample_at = connected_mono

            while True:
                now = time.monotonic()
                if now >= deadline:
                    break
                timeout = min(MESSAGE_TIMEOUT_SECONDS, max(0.1, deadline - now))
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError:
                    now = time.monotonic()
                    silence = now - (last_message_mono or connected_mono)
                    if silence >= MAX_SILENT_SECONDS:
                        raise RuntimeError("SILENT_WEBSOCKET_EXCEEDED_THRESHOLD")
                    event("receive_timeout", timeout_seconds=timeout, silent_seconds=round(silence, 3))
                    continue

                received_mono = time.monotonic()
                message_count += 1
                last_message_mono = received_mono
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("INVALID_JSON_MESSAGE") from exc
                if not isinstance(message, dict):
                    raise RuntimeError("INVALID_MESSAGE_TYPE")
                if message.get("error") or message.get("errors"):
                    api_error = message.get("error") or message.get("errors")
                    code = None
                    if isinstance(api_error, dict):
                        code = api_error.get("code")
                    raise RuntimeError("API_ERROR:" + re.sub(r"[^A-Za-z0-9_.-]", "_", str(code or "UNKNOWN"))[:100])

                msg_type = message.get("msg_type")
                if msg_type != "tick":
                    non_tick_message_count += 1
                    event(
                        "non_tick_message",
                        msg_type=str(msg_type or "unknown")[:80],
                        response_keys=sorted(message.keys())[:40],
                    )
                    continue

                tick = message.get("tick")
                if not isinstance(tick, dict) or not all(key in tick for key in ("epoch", "quote", "symbol")):
                    raise RuntimeError("MALFORMED_TICK")
                if tick.get("symbol") != SYMBOL:
                    raise RuntimeError("UNEXPECTED_TICK_SYMBOL")
                epoch = parse_epoch(tick["epoch"])
                quote = parse_quote(tick["quote"])
                if last_tick_epoch is not None and epoch < last_tick_epoch:
                    raise RuntimeError("TICK_EPOCH_REGRESSION")
                last_tick_epoch = epoch
                tick_count += 1

                sub = message.get("subscription")
                if isinstance(sub, dict) and sub.get("id") is not None:
                    current_sub = str(sub["id"])
                    if subscription_id is None:
                        subscription_id = current_sub
                        event("subscription_confirmed", subscription_id=subscription_id)
                    elif current_sub != subscription_id:
                        raise RuntimeError("SUBSCRIPTION_ID_CHANGED")

                if tick_count == 1 or tick_count % 100 == 0:
                    event(
                        "tick_progress",
                        tick_count=tick_count,
                        epoch=epoch,
                        quote=str(quote),
                        subscription_id=subscription_id,
                    )

                if received_mono - last_sample_at >= SAMPLE_INTERVAL_SECONDS:
                    sample()
                    last_sample_at = received_mono

        actual_duration = time.monotonic() - started_mono
        event("socket_closed_after_deadline", actual_duration_seconds=round(actual_duration, 3))

    except Exception as exc:
        failures.append({
            "timestamp_utc": utc_now(),
            "error_type": type(exc).__name__,
            "error_code": str(exc)[:160],
            "elapsed_seconds": round(time.monotonic() - started_mono, 3),
        })
        event("soak_failure", **failures[-1])

    ended_mono = time.monotonic()
    actual_duration = ended_mono - started_mono
    if not sample_rows or (ended_mono - (started_mono + (sample_rows[-1]["elapsed_seconds"] or 0)) > 1):
        if started:
            sample()

    rss_growth = (
        last_rss - first_rss
        if last_rss is not None and first_rss is not None else None
    )
    no_connection_failure = len(failures) == 0
    duration_pass = actual_duration >= duration_seconds
    data_pass = tick_count > 0 and subscription_id is not None
    memory_pass = rss_growth is not None and rss_growth <= MAX_RSS_GROWTH_BYTES
    pass_conditions = {
        "duration_met": duration_pass,
        "no_disconnect_or_protocol_failure": no_connection_failure,
        "ticks_received": data_pass,
        "memory_rss_growth_within_threshold": memory_pass,
        "max_silence_within_threshold": (
            last_message_mono is not None
            and ended_mono - last_message_mono < MAX_SILENT_SECONDS
        ),
    }
    status = "PASS" if all(pass_conditions.values()) else "FAILED"

    report = {
        "schema": "aurelia.public_ws_soak.v1",
        "status": status,
        "started_at_utc": started_wall.isoformat(),
        "ended_at_utc": utc_now(),
        "requested_duration_seconds": duration_seconds,
        "actual_duration_seconds": round(actual_duration, 3),
        "url": URL,
        "symbol": SYMBOL,
        "authenticated": False,
        "order_or_trade_requests_sent": 0,
        "messages_received": message_count,
        "ticks_received": tick_count,
        "non_tick_messages": non_tick_message_count,
        "last_tick_epoch": last_tick_epoch,
        "subscription_id_received": subscription_id is not None,
        "disconnect_or_protocol_failures": failures,
        "minute_sample_count": len(sample_rows),
        "first_rss_bytes": first_rss,
        "last_rss_bytes": last_rss,
        "peak_rss_bytes": peak_rss,
        "rss_growth_from_first_sample_bytes": rss_growth,
        "rss_growth_threshold_bytes": MAX_RSS_GROWTH_BYTES,
        "max_silence_threshold_seconds": MAX_SILENT_SECONDS,
        "pass_conditions": pass_conditions,
        "interpretation": (
            "PASS means no instability was observed under this bounded public-feed test; "
            "it does not mathematically prove absence of all memory leaks or satisfy authenticated broker-lifecycle certification."
        ),
        "event_log_path": str(events_path),
        "failures": failures,
    }
    write_json(report_path, report)
    event("soak_finished", status=status, pass_conditions=pass_conditions)
    # Re-write report because the final event log hash is now available.
    report["event_log_sha256"] = sha256_file(events_path)
    report["report_sha256_before_hash_field"] = sha256_file(report_path)
    write_json(report_path, report)

    print("SOAK_RESULT=" + status)
    print("SOAK_DURATION_SECONDS=" + str(round(actual_duration, 3)))
    print("TICKS_RECEIVED=" + str(tick_count))
    print("MESSAGES_RECEIVED=" + str(message_count))
    print("DISCONNECT_OR_PROTOCOL_FAILURES=" + str(len(failures)))
    print("RSS_GROWTH_BYTES=" + str(rss_growth))
    print("EVENT_LOG_SHA256=" + sha256_file(events_path))
    print("SOAK_REPORT_SHA256=" + sha256_file(report_path))
    return 0 if status == "PASS" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=int, default=3600)
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/soak_3600s"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.duration_seconds != 3600:
        print("SOAK_RESULT=BLOCKED")
        print("SOAK_REASON=DURATION_MUST_BE_EXACTLY_3600_SECONDS")
        return 2
    try:
        return asyncio.run(run_soak(args.duration_seconds, args.output_dir))
    except Exception as exc:
        print("SOAK_RESULT=BLOCKED")
        print("SOAK_REASON=" + type(exc).__name__ + ":" + str(exc)[:160])
        return 2


if __name__ == "__main__":
    sys.exit(main())
