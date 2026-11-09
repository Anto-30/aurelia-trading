from __future__ import annotations

"""Read-only probe of Deriv ticks_history time-boundary semantics.

Compares a historical tick request, a historical candle request and a latest
control request. It stores only request/response hashes and timestamp ranges;
no account credentials or trading actions are used.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.adapters.deriv_ws import DerivWebSocketTransport

PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def _safe_error(response: Any) -> str | None:
    if not isinstance(response, dict):
        return "RESPONSE_SHAPE_INVALID"
    error = response.get("error")
    if error is None:
        return None
    code = error.get("code") if isinstance(error, dict) else None
    if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", code):
        code = "UNKNOWN"
    return "API_REJECTED:" + code


def _epochs(response: dict[str, Any]) -> list[int]:
    candles = response.get("candles")
    if isinstance(candles, list):
        return [
            row["epoch"] for row in candles
            if isinstance(row, dict)
            and isinstance(row.get("epoch"), int)
            and not isinstance(row.get("epoch"), bool)
        ]
    history = response.get("history")
    times = history.get("times") if isinstance(history, dict) else None
    if isinstance(times, list):
        return [
            value for value in times
            if isinstance(value, int) and not isinstance(value, bool)
        ]
    return []


async def probe(
    *, symbol: str = "R_100", historical_start: int = 1666310400,
    historical_end: int = 1666313940,
    transport_factory: Any = DerivWebSocketTransport,
) -> dict[str, Any]:
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9_]{2,30}", symbol):
        raise ValueError("SYMBOL_INVALID")
    if (
        type(historical_start) is not int
        or type(historical_end) is not int
        or historical_start < 0
        or historical_end <= historical_start
    ):
        raise ValueError("HISTORICAL_WINDOW_INVALID")

    transport = transport_factory(PUBLIC_WS_URL, timeout_seconds=15.0)
    result: dict[str, Any] = {
        "schema": "aurelia.deriv.history_semantics_probe.v1",
        "symbol": symbol,
        "source_sha": os.getenv("GITHUB_SHA", "") or "LOCAL_UNPINNED",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "authentication_used": False,
        "capital_authority": False,
        "order_submission_permitted": False,
        "status": "FAIL",
        "requests": {},
        "blockers": [],
    }
    try:
        await transport.connect()
        requests = {
            "historical_ticks": {
                "ticks_history": symbol,
                "style": "ticks",
                "start": 0,
                "end": str(historical_end),
                "count": 1,
            },
            "historical_candles": {
                "ticks_history": symbol,
                "style": "candles",
                "granularity": 60,
                "start": historical_start,
                "end": str(historical_start + 60),
                "count": 1,
            },
            "historical_ticks_adjusted": {
                "ticks_history": symbol,
                "style": "ticks",
                "start": 0,
                "end": str(historical_end),
                "count": 1,
                "adjust_start_time": 1,
            },
            "historical_candles_adjusted": {
                "ticks_history": symbol,
                "style": "candles",
                "granularity": 60,
                "start": historical_start,
                "end": str(historical_start + 60),
                "count": 1,
                "adjust_start_time": 1,
            },
            "latest_control": {
                "ticks_history": symbol,
                "style": "ticks",
                "end": "latest",
                "count": 1,
            },
        }
        responses: dict[str, dict[str, Any]] = {}
        for name, request in requests.items():
            response = await transport.request(request)
            if not isinstance(response, dict):
                result["blockers"].append(name.upper() + "_RESPONSE_SHAPE_INVALID")
                continue
            echo = response.get("echo_req")
            echo_matches = isinstance(echo, dict) and all(
                echo.get(key) == value for key, value in request.items()
            )
            error = _safe_error(response)
            epochs = _epochs(response)
            result["requests"][name] = {
                "request": request,
                "request_sha256": _hash(request),
                "response_sha256": _hash(response),
                "echo_matches": echo_matches,
                "api_error": error,
                "msg_type": response.get("msg_type"),
                "epoch_count": len(epochs),
                "first_epoch": min(epochs) if epochs else None,
                "last_epoch": max(epochs) if epochs else None,
            }
            if error:
                result["blockers"].append(name.upper() + "_" + error)
            elif not echo_matches:
                result["blockers"].append(name.upper() + "_ECHO_MISMATCH")
            elif not epochs:
                result["blockers"].append(name.upper() + "_NO_EPOCHS")
            else:
                responses[name] = response

        tick_epochs = _epochs(responses["historical_ticks"]) if "historical_ticks" in responses else []
        candle_epochs = _epochs(responses["historical_candles"]) if "historical_candles" in responses else []
        adjusted_tick_epochs = (
            _epochs(responses["historical_ticks_adjusted"])
            if "historical_ticks_adjusted" in responses else []
        )
        adjusted_candle_epochs = (
            _epochs(responses["historical_candles_adjusted"])
            if "historical_candles_adjusted" in responses else []
        )
        latest_epochs = _epochs(responses["latest_control"]) if "latest_control" in responses else []
        tick_respects_end = bool(tick_epochs) and max(tick_epochs) <= historical_end
        candle_respects_window = bool(candle_epochs) and (
            min(candle_epochs) >= historical_start
            and max(candle_epochs) < historical_start + 60
        )
        adjusted_tick_respects_end = (
            bool(adjusted_tick_epochs) and max(adjusted_tick_epochs) <= historical_end
        )
        adjusted_candle_respects_window = (
            bool(adjusted_candle_epochs)
            and min(adjusted_candle_epochs) >= historical_start
            and max(adjusted_candle_epochs) < historical_start + 60
        )
        latest_control_present = bool(latest_epochs)
        result["historical_ticks_respect_end"] = tick_respects_end
        result["historical_candles_respect_window"] = candle_respects_window
        result["adjusted_ticks_respect_end"] = adjusted_tick_respects_end
        result["adjusted_candles_respect_window"] = adjusted_candle_respects_window
        result["latest_control_present"] = latest_control_present

        if tick_respects_end and candle_respects_window and latest_control_present:
            result["status"] = "HISTORICAL_BOUNDARIES_VERIFIED"
        elif adjusted_tick_respects_end and adjusted_candle_respects_window:
            result["status"] = "ADJUST_START_TIME_RECOVERS_HISTORY_BUT_EXACT_WINDOW_UNVERIFIED"
            result["blockers"].append("ADJUSTED_INTERVAL_REQUIRES_EXACT_DATASET_VALIDATION")
        elif not tick_respects_end and not candle_respects_window:
            result["status"] = "HISTORICAL_BOUNDARIES_IGNORED_OR_UNAVAILABLE"
            result["blockers"].append("BOTH_HISTORICAL_REQUESTS_RETURNED_OUTSIDE_WINDOW")
        elif tick_respects_end and not candle_respects_window:
            result["status"] = "TICK_HISTORY_OK_CANDLE_HISTORY_MISMATCH"
            result["blockers"].append("CANDLE_HISTORY_BOUNDARY_MISMATCH")
        elif not tick_respects_end and candle_respects_window:
            result["status"] = "CANDLE_HISTORY_OK_TICK_HISTORY_MISMATCH"
            result["blockers"].append("TICK_HISTORY_END_BOUNDARY_MISMATCH")
        else:
            result["status"] = "INCOMPLETE_HISTORY_SEMANTICS_EVIDENCE"
        return result
    except Exception as exc:
        reason = str(exc)
        if not re.fullmatch(r"[A-Z0-9_:-]{1,120}", reason):
            reason = type(exc).__name__.upper()
        result["blockers"].append(reason)
        return result
    finally:
        await transport.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default=os.getenv("DERIV_SYMBOL", "R_100"))
    parser.add_argument("--start-epoch", type=int, default=1666310400)
    parser.add_argument("--end-epoch", type=int, default=1666313940)
    parser.add_argument(
        "--output", type=Path,
        default=Path("artifacts/r100-history-semantics.json"),
    )
    args = parser.parse_args()
    result = asyncio.run(probe(
        symbol=args.symbol,
        historical_start=args.start_epoch,
        historical_end=args.end_epoch,
    ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({
        "status": result["status"],
        "historical_ticks_respect_end": result.get("historical_ticks_respect_end", False),
        "historical_candles_respect_window": result.get("historical_candles_respect_window", False),
        "latest_control_present": result.get("latest_control_present", False),
        "blockers": result["blockers"],
        "evidence_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "authentication_used": False,
        "order_submission_permitted": False,
    }, sort_keys=True))
    return 0 if result["status"] == "HISTORICAL_BOUNDARIES_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
