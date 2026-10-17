"""Read-only schema probe for public Deriv historical tick data.

No login, token, account OTP, or order endpoints are used. The program emits a
small schema/quality report, not a trading signal and not raw market history.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.adapters.deriv_adapter import PUBLIC_WS_URL
from research.labs.deriv_order_flow import OrderFlowDataError, parse_ticks_history_response


def _volume_paths(value: Any, prefix: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if str(key).lower() in {"volume", "tick_volume", "trade_volume"}:
                paths.append(path)
            paths.extend(_volume_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_volume_paths(child, f"{prefix}[{index}]"))
    return paths


async def request_history(symbol: str, count: int) -> dict[str, Any]:
    request = {
        "ticks_history": symbol,
        "end": "latest",
        "count": count,
        "style": "ticks",
        "req_id": 781731,
    }
    async with connect(PUBLIC_WS_URL, open_timeout=10, close_timeout=3) as websocket:
        await websocket.send(json.dumps(request))
        for _ in range(10):
            raw = await asyncio.wait_for(websocket.recv(), timeout=10)
            response = json.loads(raw)
            if not isinstance(response, dict):
                continue
            if response.get("error") is not None:
                raise RuntimeError("DERIV_API_REQUEST_FAILED")
            if response.get("msg_type") == "history" or isinstance(response.get("history"), dict):
                return response
    raise RuntimeError("DERIV_HISTORY_RESPONSE_NOT_RECEIVED")


def build_report(symbol: str, response: dict[str, Any]) -> dict[str, Any]:
    ticks = parse_ticks_history_response(response)
    history = response.get("history")
    if not isinstance(history, dict):
        raise OrderFlowDataError("DERIV_HISTORY_OBJECT_MISSING")
    times = [tick.timestamp for tick in ticks]
    prices = [tick.price for tick in ticks]
    monotonic = all(left <= right for left, right in zip(times, times[1:]))
    volume_paths = _volume_paths(response)
    history_keys = set(history)
    return {
        "schema": "aurelia.deriv_tick_schema_audit.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "endpoint": PUBLIC_WS_URL,
        "request_type": "ticks_history",
        "response_msg_type": response.get("msg_type"),
        "response_keys": sorted(str(key) for key in response),
        "history_keys": sorted(str(key) for key in history_keys),
        "tick_count": len(ticks),
        "price_count": len(prices),
        "timestamp_count": len(times),
        "timestamps_monotonic_non_decreasing": monotonic,
        "first_epoch": times[0] if times else None,
        "last_epoch": times[-1] if times else None,
        "minimum_price": min(prices) if prices else None,
        "maximum_price": max(prices) if prices else None,
        "pip_size_present": "pip_size" in response,
        "volume_field_paths_observed": sorted(set(volume_paths)),
        "volume_field_observed": bool(volume_paths),
        "historical_bid_ask_fields_observed": any(key in history_keys for key in ("bid", "ask")),
        "feature_policy": (
            "INSPECT_VOLUME_FIELD_SEMANTICS_BEFORE_USE" if volume_paths
            else "PRICE_TIME_ONLY_NO_TRADE_VOLUME_FEATURES"
        ),
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, help="Deriv symbol, e.g. R_100 or frxEURUSD")
    parser.add_argument("--count", type=int, default=500, help="History sample size (1..5000)")
    parser.add_argument("--output", help="Optional path for the JSON report; defaults to stdout")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_]{2,30}", args.symbol):
        print(json.dumps({"status": "BLOCKED", "reason": "SYMBOL_FORMAT_INVALID"}))
        return 2
    if isinstance(args.count, bool) or not 1 <= args.count <= 5000:
        print(json.dumps({"status": "BLOCKED", "reason": "COUNT_OUT_OF_RANGE"}))
        return 2

    try:
        response = await request_history(args.symbol, args.count)
        report = build_report(args.symbol, response)
    except Exception:
        print(json.dumps({"status": "BLOCKED", "reason": "DATA_AUDIT_FAILED",
                          "capital_authority_granted": False}))
        return 2

    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_name(output.name + ".tmp")
        temp.write_text(rendered, encoding="utf-8")
        temp.replace(output)
    print(rendered, end="")
    return 0 if report["tick_count"] > 0 and report["timestamps_monotonic_non_decreasing"] else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
