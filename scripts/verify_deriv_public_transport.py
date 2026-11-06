from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.adapters.deriv_adapter import DerivAdapter, PUBLIC_WS_URL
from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport
from runtime.core.events import sha256


async def verify_tick_subscription(
    *,
    transport_factory=None,
    timeout_seconds: float = 25.0,
) -> dict[str, Any]:
    factory = transport_factory or DerivWebSocketTransport
    transport = factory(PUBLIC_WS_URL, timeout_seconds=10.0)
    stream = None
    try:
        await transport.connect()
        stream = transport.subscribe("ticks:R_100", {"ticks": "R_100"})
        message = await asyncio.wait_for(stream.__anext__(), timeout=timeout_seconds)
        tick = message.get("tick") or {}
        if tick.get("symbol") != "R_100":
            raise DerivTransportError("R100_TICK_SUBSCRIPTION_SYMBOL_MISMATCH")
        return {
            "verified": True,
            "observation_count": 1,
            "symbol": tick.get("symbol"),
            "quote": tick.get("quote"),
            "epoch": tick.get("epoch"),
            "msg_type": message.get("msg_type"),
            "error_type": None,
            "error_code": None,
            "error_details": {},
        }
    except Exception as exc:
        return {
            "verified": False,
            "observation_count": 0,
            "symbol": "R_100",
            "quote": None,
            "epoch": None,
            "msg_type": None,
            "error_type": type(exc).__name__,
            "error_code": getattr(exc, "code", None),
            "error_details": getattr(exc, "details", {}) or {},
            "reader_error": getattr(transport, "last_reader_error", None),
        }
    finally:
        try:
            if stream is not None:
                await stream.aclose()
        finally:
            await transport.close()


async def main() -> int:
    adapter = DerivAdapter()
    count = await adapter.connect_public()
    tick_probe = await verify_tick_subscription()
    source_sha = os.getenv("GITHUB_SHA", "").strip() or os.getenv("AURELIA_SOURCE_SHA", "").strip() or "LOCAL_UNPINNED"
    evidence = {
        "schema": "aurelia.deriv_public_transport.v2",
        "source_sha": source_sha,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": PUBLIC_WS_URL,
        "active_symbol_count": count,
        "tick_subscription": tick_probe,
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }
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
        "active_symbol_count": count,
        "tick_subscription_verified": tick_probe["verified"],
        "tick_error_type": tick_probe["error_type"],
        "tick_error_code": tick_probe["error_code"],
        "tick_error_details": tick_probe["error_details"],
        "evidence_path": str(output),
        "source_sha": source_sha,
        "record_hash": evidence["record_hash"],
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }, sort_keys=True))
    return 0 if tick_probe["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
