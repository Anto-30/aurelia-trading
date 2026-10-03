from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from runtime.core.circuit import CircuitBreaker
from runtime.core.events import sha256
from runtime.core.models import AccountIdentity, BrokerOutcome, BrokerResult, CapitalSnapshot, MarketTick
from runtime.adapters.deriv_ws import DerivWebSocketTransport, DerivTransportError


PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"


class DerivProtocolError(RuntimeError):
    pass


class DerivAdapter:
    """Transport-only Deriv adapter using a single-reader WebSocket transport."""

    def __init__(
        self,
        *,
        ws_url: str | None = None,
        auth_token: str | None = None,
        expected_loginid: str | None = None,
        expected_currency: str = "USD",
        environment: str = "real",
        timeout_seconds: float = 10.0,
    ):
        self.ws_url = ws_url or os.getenv("DERIV_WS_URL", "")
        self.auth_token = auth_token if auth_token is not None else os.getenv("DERIV_AUTH_TOKEN", "")
        self.expected_loginid = expected_loginid or os.getenv("DERIV_EXPECTED_LOGINID", "")
        self.expected_currency = expected_currency
        self.environment = environment
        self.timeout_seconds = timeout_seconds
        self.transport: DerivWebSocketTransport | None = None
        self.authorized = False
        self.account: AccountIdentity | None = None
        self.circuit = CircuitBreaker()
        self._subscription_keys: set[str] = set()

    async def connect(self) -> AccountIdentity:
        if not self.ws_url:
            raise DerivProtocolError("DERIV_AUTHENTICATED_WS_URL_MISSING")
        try:
            self.transport = DerivWebSocketTransport(
                self.ws_url,
                timeout_seconds=self.timeout_seconds,
            )
            await self.transport.connect()
            if self.auth_token:
                reply = await self.transport.request({"authorize": self.auth_token})
                auth = reply.get("authorize") or {}
            else:
                # Current OTP-authenticated URLs are already authenticated.
                reply = await self.transport.request({"balance": 1})
                auth = reply.get("balance") or {}
            loginid = str(auth.get("loginid") or auth.get("login_id") or "")
            currency = str(auth.get("currency") or "")
            if not loginid:
                raise DerivProtocolError("ACCOUNT_IDENTITY_UNVERIFIED")
            account_type = "demo" if self.environment.lower() in {"demo", "virtual"} else "real"
            if self.expected_loginid and loginid != self.expected_loginid:
                raise DerivProtocolError("ACCOUNT_IDENTITY_MISMATCH")
            if currency and currency != self.expected_currency:
                raise DerivProtocolError("CURRENCY_MISMATCH")
            self.account = AccountIdentity(
                loginid=loginid,
                account_type=account_type,
                currency=currency or self.expected_currency,
                environment=self.environment,
            )
            self.authorized = True
            self.circuit.record_success()
            return self.account
        except (DerivTransportError, DerivProtocolError):
            await self.close()
            raise

    async def connect_public(self) -> int:
        transport = DerivWebSocketTransport(
            PUBLIC_WS_URL,
            timeout_seconds=self.timeout_seconds,
        )
        await transport.connect()
        try:
            reply = await transport.request({"active_symbols": "brief"})
            return len(reply.get("active_symbols") or [])
        finally:
            await transport.close()

    async def reconnect(self, fresh_ws_url: str | None = None) -> None:
        if self.transport is None:
            raise DerivProtocolError("BROKER_SESSION_NOT_CONNECTED")
        if not fresh_ws_url and not self.ws_url:
            raise DerivProtocolError("FRESH_AUTHENTICATED_WS_URL_REQUIRED")
        try:
            await self.transport.reconnect(fresh_url=fresh_ws_url or self.ws_url)
            # Revalidate account identity after every reconnect.
            await self.get_balance()
        except Exception:
            self.authorized = False
            self.account = None
            await self.close()
            raise

    async def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.transport is None:
            raise DerivProtocolError("BROKER_SESSION_NOT_CONNECTED")
        try:
            return await self.transport.request(payload)
        except DerivTransportError as exc:
            self.circuit.record_failure()
            raise DerivProtocolError(str(exc)) from exc

    async def get_balance(self) -> CapitalSnapshot:
        if not self.account:
            raise DerivProtocolError("ACCOUNT_NOT_VERIFIED")
        result = (await self.request({"balance": 1})).get("balance") or {}
        amount = float(result["balance"])
        currency = str(result.get("currency") or self.account.currency)
        loginid = str(result.get("loginid") or self.account.loginid)
        if loginid != self.account.loginid:
            raise DerivProtocolError("ACCOUNT_IDENTITY_CHANGED")
        if currency != self.account.currency:
            raise DerivProtocolError("CURRENCY_CHANGED")
        return CapitalSnapshot(
            balance=amount,
            currency=currency,
            available_balance=amount,
            captured_at=datetime.now(timezone.utc),
            source="deriv:balance",
            account=self.account,
        )

    async def active_symbols(self) -> list[dict[str, Any]]:
        return list((await self.request({"active_symbols": "brief"})).get("active_symbols") or [])

    async def subscribe_ticks(self, symbol: str) -> AsyncIterator[MarketTick]:
        if self.transport is None:
            raise DerivProtocolError("BROKER_SESSION_NOT_CONNECTED")
        key = f"ticks:{symbol}"
        if key in self._subscription_keys:
            raise DerivProtocolError("DUPLICATE_SUBSCRIPTION")
        self._subscription_keys.add(key)
        try:
            async for message in self.transport.subscribe(key, {"ticks": symbol}):
                tick = message.get("tick")
                if tick:
                    yield MarketTick(
                        symbol=str(tick.get("symbol") or symbol),
                        quote=float(tick["quote"]),
                        epoch=int(tick["epoch"]),
                        received_at=datetime.now(timezone.utc),
                    )
        finally:
            self._subscription_keys.discard(key)

    async def request_proposal(self, parameters: dict[str, Any]) -> str:
        required = ("contract_type", "currency", "underlying_symbol")
        missing = [key for key in required if not parameters.get(key)]
        if missing:
            raise DerivProtocolError("PROPOSAL_PARAMETERS_MISSING:" + ",".join(missing))
        proposal = (await self.request({"proposal": 1, **parameters})).get("proposal") or {}
        proposal_id = str(proposal.get("id") or "")
        if not proposal_id:
            raise DerivProtocolError("PROPOSAL_ID_MISSING_FROM_BROKER")
        return proposal_id

    async def submit_authorized_order(self, payload: dict[str, Any]) -> BrokerResult:
        if not self.authorized:
            raise DerivProtocolError("BROKER_SESSION_NOT_AUTHORIZED")
        if not self.circuit.permit_new_submission():
            raise DerivProtocolError("BROKER_CIRCUIT_OPEN")
        proposal_id = payload.get("proposal_id")
        if not proposal_id:
            raise DerivProtocolError("ORDER_REQUIRES_BROKER_PROPOSAL_ID")
        try:
            reply = await self.request({"buy": str(proposal_id), "price": payload["stake"]})
        except Exception:
            return BrokerResult(
                outcome=BrokerOutcome.UNKNOWN,
                request_id="unknown",
                raw_class="SUBMISSION_RESPONSE_UNKNOWN",
            )
        buy = reply.get("buy") or {}
        transaction_id = str(buy.get("transaction_id") or "") or None
        contract_id = str(buy.get("contract_id") or "") or None
        if not transaction_id and not contract_id:
            return BrokerResult(
                outcome=BrokerOutcome.UNKNOWN,
                request_id="unknown",
                raw_class="BROKER_ACCEPTANCE_UNRESOLVED",
            )
        return BrokerResult(
            outcome=BrokerOutcome.ACCEPTED,
            request_id="buy",
            broker_transaction_id=transaction_id,
            contract_id=contract_id,
            raw_class="BUY_ACCEPTED",
            broker_timestamp=datetime.now(timezone.utc),
        )

    async def get_contract_status(self, contract_id: str) -> dict[str, Any]:
        return dict(
            (await self.request({"proposal_open_contract": 1, "contract_id": int(contract_id)}))
            .get("proposal_open_contract")
            or {}
        )

    async def portfolio(self) -> list[dict[str, Any]]:
        reply = await self.request({"portfolio": 1})
        return list(reply.get("portfolio", {}).get("contracts") or [])

    async def statement(self, *, limit: int = 100, action_type: str | None = None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"statement": 1, "limit": limit}
        if action_type:
            payload["action_type"] = action_type
        reply = await self.request(payload)
        return list(reply.get("statement", {}).get("transactions") or [])

    async def close(self) -> None:
        if self.transport is not None:
            await self.transport.close()
        self.transport = None
        self.authorized = False
        self.account = None
        self._subscription_keys.clear()

    @property
    def connection_fingerprint(self) -> str:
        return sha256(
            {
                "ws_url": self.ws_url,
                "expected_loginid": self.expected_loginid,
                "currency": self.expected_currency,
                "environment": self.environment,
            }
        )
