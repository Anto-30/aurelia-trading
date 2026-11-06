from __future__ import annotations

import asyncio

from research.utils.deriv_auth_gate import (
    AuthModeMismatchError,
    DerivAuthenticationGate,
    SecurityError,
)


def fail(reason: str) -> int:
    print("DERIV_TRANSACTION_LIFECYCLE=BLOCKED")
    print(f"REASON={reason}")
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    print("LIVE_EXECUTION=BLOCKED")
    print("ORDERS_SUBMITTED=0")
    print("CAPITAL_AUTHORITY_GRANTED=false")
    return 2


async def run() -> int:
    try:
        DerivAuthenticationGate(plane="account").get_client()
    except (AuthModeMismatchError, SecurityError) as exc:
        return fail(str(exc))
    return fail("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
