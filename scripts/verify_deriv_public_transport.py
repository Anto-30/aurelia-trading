from __future__ import annotations

import asyncio
import json

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
