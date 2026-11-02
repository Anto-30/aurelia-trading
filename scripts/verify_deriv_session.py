from __future__ import annotations

import asyncio
import os
from pathlib import Path

from research.utils.deriv_auth_gate import (
    AuthModeMismatchError,
    DerivAuthenticationGate,
    SecurityError,
)

OUTPUT = Path(
    os.getenv("AURELIA_DERIV_EVIDENCE_PATH", "").strip()
    or os.getenv("DERIV_EVIDENCE_OUT", "").strip()
    or "artifacts/deriv_authenticated_session.json"
)


async def run() -> int:
    try:
        DerivAuthenticationGate(plane="account").get_client()
    except (AuthModeMismatchError, SecurityError) as exc:
        print("DERIV_AUTH_SESSION=BLOCKED")
        print(f"DERIV_AUTH_SESSION_REASON={str(exc)}")
        print("DERIV_ORDERS_SUBMITTED=0")
        print("DERIV_CAPITAL_AUTHORITY_GRANTED=false")
        return 3

    # No account client can be issued until Deriv documents a verifiable
    # read-only permission for the account endpoints AURELIA requires.
    print("DERIV_AUTH_SESSION=BLOCKED")
    print("DERIV_AUTH_SESSION_REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")
    print("DERIV_ORDERS_SUBMITTED=0")
    print("DERIV_CAPITAL_AUTHORITY_GRANTED=false")
    return 3


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
