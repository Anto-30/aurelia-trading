from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from runtime.adapters.deriv_ws import DerivWebSocketTransport
from runtime.security.deriv_auth_gate import (
    ACCOUNT_CREDENTIAL_ENV_NAMES,
    AuthModeMismatchError,
    DerivAuthenticationGate as AccountAuthenticationGate,
    SecurityError,
)

PUBLIC_RESEARCH_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
PUBLIC_RESEARCH_ACTION_FIELDS = {
    "active_symbols": {"active_symbols", "req_id", "passthrough"},
    "contracts_for": {"contracts_for", "currency", "req_id", "passthrough"},
    "contracts_list": {"contracts_list", "product_type", "req_id", "passthrough"},
    "proposal": {
        "proposal", "amount", "basis", "contract_type", "currency",
        "duration", "duration_unit", "underlying_symbol", "barrier", "date_expiry",
        "req_id", "passthrough",
    },
    "ticks": {"ticks", "subscribe", "req_id", "passthrough"},
    "ticks_history": {
        "ticks_history", "adjust_start_time", "count", "end", "start",
        "style", "granularity", "subscribe", "req_id", "passthrough",
    },
}


class DerivPublicClient:
    """Unauthenticated Deriv market-data client for the Layer 9 research plane."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.environ = os.environ if environ is None else environ
        present = [
            name for name in ACCOUNT_CREDENTIAL_ENV_NAMES
            if name in self.environ
        ]
        if present:
            raise SecurityError("RESEARCH_PLANE_ACCOUNT_CREDENTIALS_PRESENT")
        self.endpoint = PUBLIC_RESEARCH_WS_URL
        self.timeout_seconds = timeout_seconds
        self._transport: DerivWebSocketTransport | None = None

    def _reject_account_credentials(self) -> None:
        if any(name in self.environ for name in ACCOUNT_CREDENTIAL_ENV_NAMES):
            raise SecurityError("RESEARCH_PLANE_ACCOUNT_CREDENTIALS_PRESENT")

    def validate_request(self, payload: dict[str, Any]) -> None:
        self._reject_account_credentials()
        if not isinstance(payload, dict):
            raise SecurityError("PUBLIC_RESEARCH_REQUEST_INVALID")
        actions = set(payload).intersection(PUBLIC_RESEARCH_ACTION_FIELDS)
        if len(actions) != 1:
            raise SecurityError("PUBLIC_RESEARCH_ACTION_NOT_ALLOWED")
        action = next(iter(actions))
        if not set(payload).issubset(PUBLIC_RESEARCH_ACTION_FIELDS[action]):
            raise SecurityError("PUBLIC_RESEARCH_REQUEST_FIELD_NOT_ALLOWED")

    async def connect(self) -> None:
        self._reject_account_credentials()
        if self._transport is not None:
            return
        # No Authorization header, bearer token, PAT, or cookie is passed.
        # The modern public endpoint requires no app ID or auth parameter.
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
        self._reject_account_credentials()
        if set(payload) != {"ticks"} or not str(payload["ticks"]).strip():
            raise SecurityError("PUBLIC_RESEARCH_SUBSCRIPTION_NOT_ALLOWED")
        return self._connected_transport().subscribe(key, payload)

    async def close(self) -> None:
        if self._transport is not None:
            await self._transport.close()
        self._transport = None


class DerivAuthenticationGate:
    """Selects public research or the strictly guarded account evidence plane."""

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
        return AccountAuthenticationGate(
            plane="account",
            environ=self.environ,
        ).get_client()
