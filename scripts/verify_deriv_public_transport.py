from __future__ import annotations

import asyncio
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Running `python scripts/verify_deriv_public_transport.py` sets sys.path[0]
# to the scripts directory, not the repository root. Bootstrap the project root
# before importing the research and runtime packages.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from research.utils.deriv_auth_gate import DerivAuthenticationGate, PUBLIC_RESEARCH_WS_URL
from runtime.core.events import sha256


class PublicProbeError(RuntimeError):
    """A probe validation failure carrying a bounded, non-sensitive reason code."""

    def __init__(self, code: str) -> None:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code):
            raise ValueError("PUBLIC_PROBE_ERROR_CODE_INVALID")
        super().__init__(code)
        self.code = code


def _safe_reason(exc: BaseException) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code):
        return code
    return type(exc).__name__


async def verify_public_r100(
    *,
    client_factory: Callable[[], Any] | None = None,
    timeout_seconds: float = 25.0,
    minimum_ticks: int = 2,
) -> dict[str, Any]:
    if timeout_seconds <= 0 or minimum_ticks < 2:
        raise ValueError("DERIV_PUBLIC_PROBE_LIMIT_INVALID")
    client = (
        client_factory()
        if client_factory is not None
        else DerivAuthenticationGate(plane="research").get_client()
    )
    stream = None
    try:
        await client.connect()
        symbols_response = await client.request({"active_symbols": "brief"})
        active_symbols = symbols_response.get("active_symbols")
        if not isinstance(active_symbols, list):
            raise PublicProbeError("DERIV_PUBLIC_ACTIVE_SYMBOLS_INVALID")
        active_codes = {
            str(row.get("symbol") or row.get("underlying_symbol") or "")
            for row in active_symbols
            if isinstance(row, dict)
        }
        if "R_100" not in active_codes:
            raise PublicProbeError("DERIV_PUBLIC_R100_SYMBOL_NOT_AVAILABLE")

        candles = await client.historical_candles(
            "R_100", granularity=60, count=10, end="latest"
        )
        if not candles:
            raise PublicProbeError("DERIV_PUBLIC_R100_M1_HISTORY_EMPTY")
        required = {"epoch", "open", "high", "low", "close"}
        if any(not required.issubset(row) for row in candles):
            raise PublicProbeError("DERIV_PUBLIC_R100_M1_SCHEMA_INVALID")
        for row in candles:
            for key in ("open", "high", "low", "close"):
                value = float(row[key])
                if not math.isfinite(value) or value <= 0:
                    raise PublicProbeError("DERIV_PUBLIC_R100_M1_PRICE_INVALID")
            if isinstance(row["epoch"], bool) or not isinstance(row["epoch"], (int, float)):
                raise PublicProbeError("DERIV_PUBLIC_R100_M1_EPOCH_INVALID")

        stream = client.subscribe("ticks:R_100", {"ticks": "R_100"})
        iterator = stream.__aiter__()
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        observed: list[dict[str, Any]] = []
        previous_epoch: int | None = None
        while len(observed) < minimum_ticks:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError("DERIV_PUBLIC_R100_TICK_TIMEOUT")
            message = await asyncio.wait_for(iterator.__anext__(), timeout=remaining)
            tick = message.get("tick") if isinstance(message, dict) else None
            if not isinstance(tick, dict):
                raise PublicProbeError("DERIV_PUBLIC_R100_TICK_SCHEMA_INVALID")
            if str(tick.get("symbol") or "") != "R_100":
                raise PublicProbeError("DERIV_PUBLIC_R100_TICK_SYMBOL_MISMATCH")
            quote = tick.get("quote")
            epoch = tick.get("epoch")
            if isinstance(quote, bool) or not isinstance(quote, (int, float)) or not math.isfinite(float(quote)) or float(quote) <= 0:
                raise PublicProbeError("DERIV_PUBLIC_R100_TICK_QUOTE_INVALID")
            if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch <= 0:
                raise PublicProbeError("DERIV_PUBLIC_R100_TICK_EPOCH_INVALID")
            if previous_epoch is not None and epoch <= previous_epoch:
                raise PublicProbeError("DERIV_PUBLIC_R100_TICK_TIME_REGRESSION")
            previous_epoch = epoch
            observed.append({"quote": float(quote), "epoch": epoch})

        return {
            "verified": True,
            "authentication_mode": "none",
            "authorization_headers_sent": False,
            "account_credentials_loaded": False,
            "symbol": "R_100",
            "active_symbol_count": len(active_symbols),
            "m1_candle_count": len(candles),
            "tick_count": len(observed),
            "first_tick_epoch": observed[0]["epoch"],
            "last_tick_epoch": observed[-1]["epoch"],
            "last_quote": observed[-1]["quote"],
            "error_type": None,
            "error_code": None,
        }
    except Exception as exc:
        return {
            "verified": False,
            "authentication_mode": "none",
            "authorization_headers_sent": False,
            "account_credentials_loaded": False,
            "symbol": "R_100",
            "active_symbol_count": 0,
            "m1_candle_count": 0,
            "tick_count": 0,
            "error_type": type(exc).__name__,
            "error_code": _safe_reason(exc),
        }
    finally:
        try:
            if stream is not None:
                await stream.aclose()
        finally:
            await client.close()


async def main() -> int:
    probe = await verify_public_r100()
    source_sha = (
        os.getenv("GITHUB_SHA", "").strip()
        or os.getenv("AURELIA_SOURCE_SHA", "").strip()
        or "LOCAL_UNPINNED"
    )
    evidence = {
        "schema": "aurelia.deriv_public_transport.v3",
        "source_sha": source_sha,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": PUBLIC_RESEARCH_WS_URL,
        **probe,
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
    temp.write_text(
        json.dumps(evidence, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temp.replace(output)
    print(json.dumps({
        "component": "AURELIA",
        "probe": "DERIV_PUBLIC_R100_TICKS_AND_M1",
        "verified": probe["verified"],
        "authentication_mode": "none",
        "authorization_headers_sent": False,
        "account_credentials_loaded": False,
        "tick_count": probe["tick_count"],
        "error_code": probe["error_code"],
        "evidence_path": str(output),
        "source_sha": source_sha,
        "record_hash": evidence["record_hash"],
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }, sort_keys=True))
    return 0 if probe["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
