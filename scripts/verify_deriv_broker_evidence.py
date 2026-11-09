from __future__ import annotations


def fail(reason: str) -> int:
    print("DERIV_BROKER_EVIDENCE=BLOCKED")
    print(f"REASON={reason}")
    print("ORDERS_SUBMITTED=0")
    print("CAPITAL_AUTHORITY_GRANTED=false")
    print("LIVE_EXECUTION=BLOCKED")
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    return 2


async def run() -> int:
    """Broker account statements/balances are unavailable without read-only scope."""
    return fail("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(run()))
