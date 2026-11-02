from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.utils.deriv_auth_gate import (
    DerivAuthenticationGate,
    PUBLIC_RESEARCH_WS_URL,
)
from runtime.core.events import sha256


async def main() -> int:
    client = None
    try:
        client = DerivAuthenticationGate(plane="research").get_client()
        await client.connect()
        candles = await client.historical_candles(
            "R_100",
            granularity=60,
            count=10,
            end="latest",
        )
        if not candles:
            raise RuntimeError("DERIV_PUBLIC_R100_M1_HISTORY_EMPTY")
        required = {"epoch", "open", "high", "low", "close"}
        if any(not required.issubset(row) for row in candles):
            raise RuntimeError("DERIV_PUBLIC_R100_M1_SCHEMA_INVALID")
        source_sha = (
            os.getenv("GITHUB_SHA", "").strip()
            or os.getenv("AURELIA_SOURCE_SHA", "").strip()
            or "LOCAL_UNPINNED"
        )
        evidence = {
            "schema": "aurelia.deriv_public_transport.v2",
            "source_sha": source_sha,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "endpoint": PUBLIC_RESEARCH_WS_URL,
            "authentication_mode": "none",
            "authorization_headers_sent": False,
            "account_credentials_loaded": False,
            "symbol": "R_100",
            "granularity_seconds": 60,
            "candle_count": len(candles),
            "first_epoch": candles[0]["epoch"],
            "last_epoch": candles[-1]["epoch"],
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
            json.dumps(evidence, sort_keys=True, indent=2) + "\\n",
            encoding="utf-8",
        )
        temp.replace(output)
        print(json.dumps({
            "component": "AURELIA",
            "probe": "DERIV_PUBLIC_R100_M1_HISTORY",
            "authentication_mode": "none",
            "authorization_headers_sent": False,
            "account_credentials_loaded": False,
            "symbol": "R_100",
            "granularity_seconds": 60,
            "candle_count": len(candles),
            "evidence_path": str(output),
            "source_sha": source_sha,
            "record_hash": evidence["record_hash"],
            "capital_authority_granted": False,
            "order_submission_permitted": False,
        }, sort_keys=True))
        return 0
    except Exception as exc:
        print("DERIV_PUBLIC_R100_M1=FAILED")
        print(f"REASON={type(exc).__name__}")
        return 1
    finally:
        if client is not None:
            await client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
