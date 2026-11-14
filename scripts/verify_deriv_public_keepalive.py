from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport
from runtime.core.events import sha256


PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
PUBLIC_SYMBOL = "1HZ100V"
KEEPALIVE_INTERVAL_SECONDS = 30
MINIMUM_TWO_PING_WINDOW_SECONDS = 61


def build_keepalive_record(
    *,
    source_sha: str,
    started_at_utc: str,
    ended_at_utc: str,
    requested_duration_seconds: int,
    actual_elapsed_seconds: float,
    tick_count: int,
    keepalive_attempts: int,
    keepalive_successes: int,
    failure_type: str | None,
) -> dict[str, Any]:
    """Build a CI diagnostic record; it is not production certification evidence."""
    if not isinstance(requested_duration_seconds, int) or isinstance(requested_duration_seconds, bool):
        raise ValueError("KEEPALIVE_REQUESTED_DURATION_INVALID")
    numeric_values = (actual_elapsed_seconds,)
    if any(not math.isfinite(float(value)) or float(value) < 0 for value in numeric_values):
        raise ValueError("KEEPALIVE_ELAPSED_TIME_INVALID")
    counters = (tick_count, keepalive_attempts, keepalive_successes)
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counters):
        raise ValueError("KEEPALIVE_COUNTER_INVALID")

    passed = (
        requested_duration_seconds >= MINIMUM_TWO_PING_WINDOW_SECONDS
        and actual_elapsed_seconds >= MINIMUM_TWO_PING_WINDOW_SECONDS
        and actual_elapsed_seconds >= requested_duration_seconds - 1
        and tick_count > 0
        and keepalive_attempts >= 2
        and keepalive_successes >= 2
        and keepalive_successes == keepalive_attempts
        and failure_type is None
    )
    record: dict[str, Any] = {
        "schema": "aurelia.deriv_public_keepalive_smoke.v1",
        "evidence_type": "PUBLIC_WEBSOCKET_KEEPALIVE_SMOKE",
        "classification": "CI_TRANSPORT_DIAGNOSTIC_ONLY",
        "source_sha": source_sha,
        "started_at_utc": started_at_utc,
        "ended_at_utc": ended_at_utc,
        "endpoint": PUBLIC_WS_URL,
        "symbol": PUBLIC_SYMBOL,
        "requested_duration_seconds": requested_duration_seconds,
        "actual_elapsed_seconds": round(float(actual_elapsed_seconds), 3),
        "tick_count": tick_count,
        "keepalive_interval_seconds": KEEPALIVE_INTERVAL_SECONDS,
        "keepalive_attempts": keepalive_attempts,
        "keepalive_successes": keepalive_successes,
        "failure_type": failure_type,
        "status": "PASS" if passed else "FAIL",
        "authentication_used": False,
        "account_metadata_accessed": False,
        "orders_submitted": 0,
        "capital_authority_granted": False,
        "order_submission_permitted": False,
        "live_execution": "BLOCKED",
    }
    record["record_hash"] = sha256(record)
    return record


async def run() -> int:
    raw_duration = os.getenv("AURELIA_PUBLIC_KEEPALIVE_DURATION_SECONDS", "65").strip()
    try:
        duration_seconds = int(raw_duration)
    except ValueError:
        print("PUBLIC_KEEPALIVE=BLOCKED")
        print("REASON=INVALID_DURATION")
        return 2
    if duration_seconds < MINIMUM_TWO_PING_WINDOW_SECONDS:
        print("PUBLIC_KEEPALIVE=BLOCKED")
        print("REASON=DURATION_TOO_SHORT_FOR_TWO_JSON_PINGS")
        return 2

    source_sha = os.getenv("GITHUB_SHA", "").strip() or os.getenv("AURELIA_SOURCE_SHA", "").strip() or "LOCAL_UNPINNED"
    started = datetime.now(timezone.utc)
    monotonic_start = time.monotonic()
    transport = DerivWebSocketTransport(
        PUBLIC_WS_URL,
        timeout_seconds=10.0,
        keepalive_interval=float(KEEPALIVE_INTERVAL_SECONDS),
    )
    stream = None
    tick_count = 0
    failure_type: str | None = None

    try:
        await transport.connect()
        stream = transport.subscribe(
            f"public-keepalive:{PUBLIC_SYMBOL}",
            {"ticks": PUBLIC_SYMBOL},
        )
        iterator = stream.__aiter__()
        deadline = monotonic_start + duration_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                message = await asyncio.wait_for(iterator.__anext__(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            tick = message.get("tick")
            if not isinstance(tick, dict):
                continue
            quote = tick.get("quote")
            epoch = tick.get("epoch")
            if (
                isinstance(quote, (int, float))
                and not isinstance(quote, bool)
                and math.isfinite(float(quote))
                and float(quote) > 0
                and isinstance(epoch, int)
                and not isinstance(epoch, bool)
                and epoch > 0
            ):
                tick_count += 1
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        failure_type = (
            transport._terminal_error_code
            or type(exc).__name__
        )
    finally:
        if failure_type is None and transport._terminal_error_code is not None:
            failure_type = transport._terminal_error_code
        attempts = transport.keepalive_attempts
        successes = transport.keepalive_successes
        if stream is not None:
            try:
                await stream.aclose()
            except Exception:
                pass
        await transport.close()

    ended = datetime.now(timezone.utc)
    actual_elapsed = time.monotonic() - monotonic_start
    record = build_keepalive_record(
        source_sha=source_sha,
        started_at_utc=started.isoformat(),
        ended_at_utc=ended.isoformat(),
        requested_duration_seconds=duration_seconds,
        actual_elapsed_seconds=actual_elapsed,
        tick_count=tick_count,
        keepalive_attempts=attempts,
        keepalive_successes=successes,
        failure_type=failure_type,
    )
    output = Path(
        os.getenv("DERIV_PUBLIC_KEEPALIVE_EVIDENCE_OUT", "artifacts/deriv_public_keepalive.json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    temp.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temp.replace(output)
    print(json.dumps({
        "PUBLIC_KEEPALIVE": record["status"],
        "DURATION_SECONDS": record["actual_elapsed_seconds"],
        "TICK_COUNT": tick_count,
        "KEEPALIVE_ATTEMPTS": attempts,
        "KEEPALIVE_SUCCESSES": successes,
        "FAILURE_TYPE": failure_type,
        "RECORD_HASH": record["record_hash"],
        "AUTHENTICATION_USED": False,
        "CAPITAL_AUTHORITY_GRANTED": False,
        "LIVE_EXECUTION": "BLOCKED",
    }, sort_keys=True))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
