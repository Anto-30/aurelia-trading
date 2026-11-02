from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from runtime.adapters.deriv_ws import DerivWebSocketTransport

DEFAULT_PUBLIC_APP_ID = 1089
PUBLIC_RESEARCH_WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DEFAULT_PUBLIC_APP_ID}"
PUBLIC_RESEARCH_ACTIONS = frozenset({
    "active_symbols",
    "contracts_for",
    "contracts_list",
    "proposal",
    "ticks",
    "ticks_history",
})

# A research worker must not inherit account credentials, even if it promises
# not to use them. Rejecting the environment is safer than silently ignoring
# credentials that have crossed the process boundary.
ACCOUNT_CREDENTIAL_ENV_NAMES = (
    "DERIV_AUTH_TOKEN",
    "DERIV_PAT",
    "DERIV_OAUTH_ACCESS_TOKEN",
    "DERIV_OAUTH_REFRESH_TOKEN",
    "DERIV_REFRESH_TOKEN",
)

class SecurityError(RuntimeError):
    """Raised when a Deriv authentication-plane security invariant is violated."""

class AuthModeMismatchError(RuntimeError):
    """Raised when credential configuration does not match the requested plane."""

class DerivPublicClient:
    """Unauthenticated Deriv market-data client for the Layer 9 research plane."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        env = os.environ if environ is None else environ
        present = [
            name for name in ACCOUNT_CREDENTIAL_ENV_NAMES
            if str(env.get(name, "")).strip()
        ]
        if present:
            raise SecurityError("RESEARCH_PLANE_ACCOUNT_CREDENTIALS_PRESENT")
        raw_app_id = str(env.get("DERIV_PUBLIC_APP_ID", str(DEFAULT_PUBLIC_APP_ID))).strip()
        if not raw_app_id.isdecimal() or int(raw_app_id) <= 0:
            raise SecurityError("DERIV_PUBLIC_APP_ID_INVALID")
        # Classic market-data WebSocket is public and supports ticks_history.
        # It is intentionally confined to research/ and never used for orders.
        self.app_id = int(raw_app_id)
        self.endpoint = f"wss://ws.derivws.com/websockets/v3?app_id={self.app_id}"
        self.timeout_seconds = timeout_seconds
        self._transport: DerivWebSocketTransport | None = None

    def validate_request(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise SecurityError("PUBLIC_RESEARCH_REQUEST_INVALID")
        action_keys = set(payload) - {"req_id", "passthrough"}
        if len(action_keys) != 1 or not action_keys.issubset(PUBLIC_RESEARCH_ACTIONS):
            raise SecurityError("PUBLIC_RESEARCH_ACTION_NOT_ALLOWED")

    async def connect(self) -> None:
        if self._transport is not None:
            return
        # No headers, bearer token, PAT, cookie, or app-id parameter is passed.
        transport = DerivWebSocketTransport(
            self.endpoint,
            timeout_seconds=self.timeout_seconds,
        )
        await transport.connect()
        self._transport = transport

    def _connected_transport(self) -> DerivWebSocketTransport:
        if self._transport is None:
            raise RuntimeError("PUBLIC_RESEARCH_TRANSPORT_NOT_CONNECTED")
        return self._transport

    async def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.validate_request(payload)
        return await self._connected_transport().request(payload)

    async def historical_candles(
        self,
        symbol: str,
        *,
        granularity: int = 60,
        count: int = 500,
        end: str = "latest",
    ) -> list[dict[str, Any]]:
        allowed_granularities = {
            60, 120, 180, 300, 600, 900, 1800, 3600, 7200,
            14400, 28800, 86400,
        }
        if not symbol or not symbol.replace("_", "").isalnum():
            raise ValueError("DERIV_PUBLIC_SYMBOL_INVALID")
        if granularity not in allowed_granularities:
            raise ValueError("DERIV_PUBLIC_GRANULARITY_UNSUPPORTED")
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 5000:
            raise ValueError("DERIV_PUBLIC_CANDLE_COUNT_INVALID")
        response = await self.request({
            "ticks_history": symbol,
            "end": end,
            "style": "candles",
            "granularity": granularity,
            "count": count,
        })
        candles = response.get("candles")
        if not isinstance(candles, list):
            raise RuntimeError("DERIV_PUBLIC_CANDLE_RESPONSE_INVALID")
        return [dict(row) for row in candles if isinstance(row, dict)]

    def subscribe(self, key: str, payload: dict[str, Any]):
        if set(payload) != {"ticks"} or not str(payload["ticks"]).strip():
            raise SecurityError("PUBLIC_RESEARCH_SUBSCRIPTION_NOT_ALLOWED")
        return self._connected_transport().subscribe(key, payload)

    async def close(self) -> None:
        if self._transport is not None:
            await self._transport.close()
        self._transport = None

class DerivAuthenticationGate:
    """Selects an explicit Deriv plane and fails closed on account credentials."""

    def __init__(
        self,
        plane: str = "account",
        *,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        if plane not in {"research", "account"}:
            raise ValueError("UNKNOWN_DERIV_AUTH_PLANE")
        self.plane = plane
        self.environ = os.environ if environ is None else environ

    def get_client(self):
        if self.plane == "research":
            return DerivPublicClient(environ=self.environ)
        return self._get_account_client()

    def _get_account_client(self):
        env = self.environ
        mode = str(env.get("ACCOUNT_DERIV_AUTH_MODE", "none")).strip().lower()
        if mode != "oauth":
            raise AuthModeMismatchError("ACCOUNT_PLANE_REQUIRES_EXPLICIT_OAUTH_MODE")
        oauth_token = str(env.get("DERIV_OAUTH_ACCESS_TOKEN", "")).strip()
        pat_token = str(env.get("DERIV_PAT", "")).strip()
        generic_token = str(env.get("DERIV_AUTH_TOKEN", "")).strip()
        refresh_token = str(env.get("DERIV_OAUTH_REFRESH_TOKEN", "")).strip() or str(
            env.get("DERIV_REFRESH_TOKEN", "")
        ).strip()
        if oauth_token and pat_token and oauth_token == pat_token:
            raise SecurityError("OAUTH_TOKEN_EQUALS_PAT")
        if pat_token:
            raise SecurityError("ACCOUNT_PLANE_PAT_PRESENT")
        if generic_token:
            raise AuthModeMismatchError("GENERIC_TOKEN_FALLBACK_BLOCKED")
        if refresh_token:
            raise SecurityError("DERIV_OAUTH_REFRESH_TOKEN_UNSUPPORTED")
        if not oauth_token:
            raise AuthModeMismatchError("DERIV_OAUTH_ACCESS_TOKEN_MISSING")
        if not self._verify_read_only_boundary(oauth_token):
            raise SecurityError("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")
        raise SecurityError("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")

    @staticmethod
    def _verify_read_only_boundary(token: str) -> bool:
        """Return False until Deriv documents a read-only scope for account APIs.

        Token inequality, JWT decoding, or OAuth app registration is not proof
        of a read-only permission boundary. Current Deriv documentation lists
        trade for the account-list and OTP endpoints and has no read scope for them.
        """
        return False
