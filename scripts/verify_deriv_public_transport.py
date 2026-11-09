from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.adapters.deriv_ws import DerivWebSocketTransport

PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
DEFAULT_SYMBOL = "1HZ100V"


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def probe(
    *,
    symbol: str = DEFAULT_SYMBOL,
    tick_count: int = 2,
    timeout_seconds: float = 20.0,
    transport_factory: Any = DerivWebSocketTransport,
) -> dict[str, Any]:
    if not isinstance(symbol, str) or not symbol or len(symbol) > 30:
        raise ValueError("PUBLIC_PROBE_SYMBOL_INVALID")
    if isinstance(tick_count, bool) or tick_count < 2 or tick_count > 20:
        raise ValueError("PUBLIC_PROBE_TICK_COUNT_INVALID")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("PUBLIC_PROBE_TIMEOUT_INVALID")

    transport = transport_factory(PUBLIC_WS_URL, timeout_seconds=timeout_seconds)
    source_sha = (
        os.getenv("GITHUB_SHA", "").strip()
        or os.getenv("AURELIA_SOURCE_SHA", "").strip()
        or "LOCAL_UNPINNED"
    )
    evidence: dict[str, Any] = {
        "schema": "aurelia.deriv_public_transport.v2",
        "source_sha": source_sha,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": PUBLIC_WS_URL,
        "symbol": symbol,
        "requested_tick_count": tick_count,
        "ticks": [],
        "active_symbol_count": 0,
        "authentication_used": False,
        "capital_authority_granted": False,
        "order_submission_permitted": False,
        "status": "BLOCKED",
    }
    try:
        await transport.connect()
        active_response = await transport.request({"active_symbols": "brief"})
        if "error" in active_response:
            raise RuntimeError("PUBLIC_ACTIVE_SYMBOLS_REJECTED")
        rows = active_response.get("active_symbols")
        if not isinstance(rows, list):
            raise RuntimeError("PUBLIC_ACTIVE_SYMBOLS_MISSING")
        active_symbols = {
            row.get("underlying_symbol")
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("underlying_symbol"), str)
        }
        evidence["active_symbol_count"] = len(rows)
        evidence["active_symbols_sha256"] = _canonical_hash(active_response)
        if symbol not in active_symbols:
            raise RuntimeError("PUBLIC_PROBE_SYMBOL_NOT_ACTIVE")

        iterator = transport.subscribe("ticks:" + symbol, {"ticks": symbol})
        previous_epoch: int | None = None
        for _ in range(tick_count):
            message = await asyncio.wait_for(
                iterator.__anext__(), timeout=timeout_seconds
            )
            tick = message.get("tick")
            if not isinstance(tick, dict):
                raise RuntimeError("PUBLIC_TICK_PAYLOAD_MISSING")
            tick_symbol = str(tick.get("symbol") or "")
            if tick_symbol != symbol:
                raise RuntimeError("PUBLIC_TICK_SYMBOL_MISMATCH")
            try:
                quote = float(tick["quote"])
                epoch = int(tick["epoch"])
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise RuntimeError("PUBLIC_TICK_FIELDS_INVALID") from exc
            if not math.isfinite(quote) or quote <= 0:
                raise RuntimeError("PUBLIC_TICK_QUOTE_INVALID")
            if previous_epoch is not None and epoch <= previous_epoch:
                raise RuntimeError("PUBLIC_TICK_EPOCH_NOT_INCREASING")
            previous_epoch = epoch
            evidence["ticks"].append({
                "symbol": tick_symbol,
                "quote": format(quote, ".15g"),
                "epoch": epoch,
            })
        evidence["tick_stream_verified"] = len(evidence["ticks"]) == tick_count
        evidence["status"] = (
            "PUBLIC_TICK_STREAM_VERIFIED"
            if evidence["tick_stream_verified"]
            else "PUBLIC_TICK_STREAM_INCOMPLETE"
        )
        return evidence
    except Exception as exc:
        reason = str(exc)
        if not reason.isascii() or not all(ch.isalnum() or ch in "_:-." for ch in reason):
            reason = type(exc).__name__.upper()
        evidence["blocker"] = reason
        return evidence
    finally:
        await transport.close()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Verify public Deriv tick streaming without authentication.")
    parser.add_argument("--symbol", default=os.getenv("DERIV_PUBLIC_PROBE_SYMBOL", DEFAULT_SYMBOL))
    parser.add_argument("--ticks", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            os.getenv("DERIV_PUBLIC_TRANSPORT_EVIDENCE_PATH", "").strip()
            or os.getenv("DERIV_PUBLIC_TRANSPORT_EVIDENCE_OUT", "").strip()
            or "artifacts/deriv_public_transport.json"
        ),
    )
    args = parser.parse_args()
    evidence = await probe(
        symbol=args.symbol,
        tick_count=args.ticks,
        timeout_seconds=args.timeout_seconds,
    )
    evidence["record_hash"] = _canonical_hash(evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_name(args.output.name + ".tmp")
    temp.write_text(json.dumps(evidence, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(args.output)
    print(json.dumps({
        "probe": "DERIV_PUBLIC_TICK_STREAM",
        "status": evidence["status"],
        "symbol": evidence["symbol"],
        "tick_count": len(evidence["ticks"]),
        "active_symbol_count": evidence["active_symbol_count"],
        "source_sha": evidence["source_sha"],
        "record_hash": evidence["record_hash"],
        "authentication_used": False,
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }, sort_keys=True))
    return 0 if evidence["status"] == "PUBLIC_TICK_STREAM_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
