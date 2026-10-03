from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.adapters.session_manager import (
    DerivSessionManager,
    DerivSessionManagerError,
    redact_ws_url,
)


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name}_MISSING")
    return value


async def verify() -> dict[str, object]:
    token = _required("DERIV_AUTH_TOKEN")
    mode = os.getenv("DERIV_AUTH_MODE", "oauth").strip().lower()
    app_id = os.getenv("DERIV_APP_ID", "").strip()

    environment = os.getenv("DERIV_ENVIRONMENT", "real").strip().lower()
    expected_loginid = os.getenv("DERIV_EXPECTED_LOGINID", "").strip()
    expected_currency = os.getenv("DERIV_EXPECTED_CURRENCY", "USD").strip()

    if mode not in {"oauth", "pat"}:
        raise RuntimeError("DERIV_AUTH_MODE_INVALID")
    if environment not in {"real", "demo"}:
        raise RuntimeError("DERIV_ENVIRONMENT_INVALID")
    if environment == "real" and not expected_loginid:
        raise RuntimeError("DERIV_EXPECTED_LOGINID_REQUIRED_FOR_REAL")
    if mode == "pat" and not app_id:
        raise RuntimeError("DERIV_APP_ID_REQUIRED_FOR_PAT")

    manager = DerivSessionManager(
        expected_loginid=expected_loginid,
        expected_environment=environment,
        expected_currency=expected_currency,
    )

    session = manager.bootstrap(
        bearer_token=token,
        app_id=app_id or None,
    )

    adapter = DerivAdapter(
        ws_url=session.websocket.url,
        expected_loginid=session.binding.loginid,
        expected_currency=session.binding.currency,
        environment=session.binding.environment,
    )
    try:
        identity = await adapter.connect()
        balance = await adapter.get_balance()
        if not balance.is_valid():
            raise RuntimeError("DERIV_CAPITAL_SNAPSHOT_INVALID")

        captured_at = datetime.now(timezone.utc).isoformat()
        result = {
            "status": "DERIV_AUTHENTICATED_SESSION_VERIFIED",
            "verified_at_utc": captured_at,
            "account": {
                "loginid": identity.loginid,
                "environment": identity.environment,
                "account_type": identity.account_type,
                "currency": identity.currency,
            },
            "session": {
                "source": session.websocket.source,
                "websocket": redact_ws_url(session.websocket.url),
            },
            "capital": {
                "balance_verified": True,
                "snapshot_source": balance.source,
                "snapshot_currency": balance.currency,
                "snapshot_captured_at": balance.captured_at.isoformat(),
            },
            "capital_authorization": {
                "FINAL_EXECUTION_AUTHORIZATION": False,
                "LIVE_EXECUTION": "BLOCKED",
            },
        }
        return result
    finally:
        await adapter.close()


if __name__ == "__main__":
    import asyncio

    try:
        result = asyncio.run(verify())
    except (DerivSessionManagerError, RuntimeError) as exc:
        print(
            json.dumps(
                {
                    "status": "DERIV_AUTHENTICATED_SESSION_NOT_VERIFIED",
                    "reason": str(exc),
                    "FINAL_EXECUTION_AUTHORIZATION": False,
                    "LIVE_EXECUTION": "BLOCKED",
                },
                sort_keys=True,
            )
        )
        sys.exit(2)

    print(json.dumps(result, sort_keys=True))
