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

from runtime.adapters.deriv_adapter import DerivAdapter, PUBLIC_WS_URL
from runtime.core.events import sha256


async def main() -> int:
    adapter = DerivAdapter()
    count = await adapter.connect_public()
    source_sha = os.getenv("GITHUB_SHA", "").strip() or os.getenv("AURELIA_SOURCE_SHA", "").strip() or "LOCAL_UNPINNED"
    evidence = {
        "schema": "aurelia.deriv_public_transport.v1",
        "source_sha": source_sha,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": PUBLIC_WS_URL,
        "active_symbol_count": count,
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }
    evidence["record_hash"] = sha256(evidence)
    output = Path(os.getenv("DERIV_PUBLIC_TRANSPORT_EVIDENCE_OUT", "artifacts/deriv_public_transport.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    temp.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temp.replace(output)
    print(json.dumps({
        "component": "AURELIA",
        "probe": "DERIV_PUBLIC_MARKET_DATA",
        "active_symbol_count": count,
        "evidence_path": str(output),
        "source_sha": source_sha,
        "record_hash": evidence["record_hash"],
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
