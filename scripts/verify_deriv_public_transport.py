from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.adapters.deriv_adapter import PUBLIC_WS_URL
from runtime.adapters.deriv_ws import DerivWebSocketTransport

R100_SYMBOL = "R_100"


async def probe_public_transport(
    transport_factory: Callable[..., Any] = DerivWebSocketTransport,
    *,
    tick_timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    """Verify public symbol discovery and at least one real R_100 tick.

    A successful connection or active-symbol response alone does not prove the
    streaming path works. This probe performs only public, read-only requests;
    it does not authorize or submit trades.
    """
    if not math.isfinite(tick_timeout_seconds) or tick_timeout_seconds <= 0:
        raise ValueError("tick_timeout_seconds must be positive and finite")

    transport = transport_factory(PUBLIC_WS_URL, timeout_seconds=min(10.0, tick_timeout_seconds))
    stream = None
    try:
        await transport.connect()
        reply = await transport.request({"active_symbols": "brief"})
        rows = reply.get("active_symbols") or []
        if not isinstance(rows, list):
            raise RuntimeError("PUBLIC_ACTIVE_SYMBOLS_RESPONSE_INVALID")
        available = {
            str(row.get("underlying_symbol") or row.get("symbol") or "")
            for row in rows
            if isinstance(row, dict)
        }
        if R100_SYMBOL not in available:
            raise RuntimeError("PUBLIC_R100_SYMBOL_UNAVAILABLE")

        stream = transport.subscribe(f"ticks:{R100_SYMBOL}", {"ticks": R100_SYMBOL})
        started = time.perf_counter_ns()
        deadline = asyncio.get_running_loop().time() + tick_timeout_seconds
        tick: dict[str, Any] | None = None
        while tick is None:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError("PUBLIC_R100_TICK_TIMEOUT")
            message = await asyncio.wait_for(anext(stream), timeout=remaining)
            candidate = message.get("tick") if isinstance(message, dict) else None
            if isinstance(candidate, dict):
                tick = candidate

        try:
            quote = float(tick["quote"])
            epoch = int(tick["epoch"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("PUBLIC_R100_TICK_PAYLOAD_INVALID") from exc
        if not math.isfinite(quote) or quote <= 0 or epoch <= 0:
            raise RuntimeError("PUBLIC_R100_TICK_VALUES_INVALID")

        return {
            "endpoint": PUBLIC_WS_URL,
            "active_symbol_count": len(rows),
            "r100_symbol_available": True,
            "tick_stream_verified": True,
            "first_tick_epoch": epoch,
            "tick_quote_finite_positive": True,
            "tick_probe_latency_ms": (time.perf_counter_ns() - started) / 1_000_000,
        }
    finally:
        if stream is not None:
            await stream.aclose()
        await transport.close()


async def main() -> int:
    probe = await probe_public_transport()
    source_sha = (
        os.getenv("GITHUB_SHA", "").strip()
        or os.getenv("AURELIA_SOURCE_SHA", "").strip()
        or "LOCAL_UNPINNED"
    )
    evidence = {
        "schema": "aurelia.deriv_public_transport.v1",
        "source_sha": source_sha,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        **probe,
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }
    from runtime.core.events import sha256

    evidence["record_hash"] = sha256(evidence)
    output = Path(
        os.getenv("DERIV_PUBLIC_TRANSPORT_EVIDENCE_PATH", "").strip()
        or os.getenv("DERIV_PUBLIC_TRANSPORT_EVIDENCE_OUT", "").strip()
        or "artifacts/deriv_public_transport.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    temp.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temp.replace(output)
    print(json.dumps({
        "component": "AURELIA",
        "probe": "DERIV_PUBLIC_MARKET_DATA",
        "active_symbol_count": probe["active_symbol_count"],
        "r100_symbol_available": probe["r100_symbol_available"],
        "tick_stream_verified": probe["tick_stream_verified"],
        "tick_probe_latency_ms": probe["tick_probe_latency_ms"],
        "evidence_path": str(output),
        "source_sha": source_sha,
        "record_hash": evidence["record_hash"],
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
