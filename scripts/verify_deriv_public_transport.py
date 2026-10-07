from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.adapters.deriv_adapter import DerivAdapter


async def main() -> int:
    adapter = DerivAdapter()
    count = await adapter.connect_public()
    print(json.dumps({
        "component": "AURELIA",
        "probe": "DERIV_PUBLIC_MARKET_DATA",
        "active_symbol_count": count,
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
