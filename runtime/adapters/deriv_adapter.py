from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from runtime.adapters.deriv_session import DerivSessionError, get_authenticated_ws_url, validate_modern_options_ws_url
from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport
from runtime.core.circuit import CircuitBreaker
from runtime.core.events import sha256
from runtime.core.request_ledger import RequestLedger, RequestState
from runtime.core.secrets import get_optional_secret
from runtime.core.models import (
    AccountIdentity,
    BrokerOutcome,
    BrokerResult,
    CapitalSnapshot,
    MarketTick,
)


PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"


class DerivProtocolError(RuntimeError):
    pass


class DerivAdapter:
    """Transport-only Deriv Options API boundary for AURELIA."""

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
        self.auth_token = (
            auth_token if auth_token is not None else os.getenv("DERIV_AUTH_TOKEN", "")
        )
        self.expected_loginid = (
            expected_loginid or get_optional_secret("DERIV_EXPECTED_LOGINID")
        )
        self.expected_currency = expected_currency
        self.environment = environment
        self.timeout_seconds = timeout_seconds
        self.transport: DerivWebSocketTransport | None = None
        self.authorized = False
        self.account: AccountIdentity | None = None
        self.circuit = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout_seconds=60.0,
            half_open_max_requests=1,
        )
        self.ledger = RequestLedger(max_pending_age_seconds=30.0)
        self._subscription_keys: set[str] = set()

    def _validate_environment_url(self, url: str) -> None:
        try:
            validate_modern_options_ws_url(
                url,
                expected_environment=self.environment,
            )
        except DerivSessionError as exc:
            raise DerivProtocolError(str(exc)) from exc

    async def connect(self) -> AccountIdentity:
        if not self.ws_url:
            raise DerivProtocolError("DERIV_AUTHENTICATED_WS_URL_MISSING")
        self._validate_environment_url(self.ws_url)
        try:
            self.transport = DerivWebSocketTransport(
                self.ws_url,
                timeout_seconds=self.timeout_seconds,
            )
            await self.transport.connect()

            if self.auth_token:
                reply = await self._tracked_request("authorize", {"authorize": self.auth_token})
                identity_payload = reply.get("authorize") or {}
            else:
                reply = await self._tracked_request("balance", {"balance": 1})
                identity_payload = reply.get("balance") or {}

            loginid = str(
                identity_payload.get("loginid")
                or identity_payload.get("login_id")
                or ""
            )
            currency = str(identity_payload.get("currency") or "")
            if not loginid:
                raise DerivProtocolError("ACCOUNT_IDENTITY_UNVERIFIED")
            if self.expected_loginid and loginid != self.expected_loginid:
                raise DerivProtocolError("ACCOUNT_IDENTITY_MISMATCH")
            if currency and currency != self.expected_currency:
                raise DerivProtocolError("CURRENCY_MISMATCH")

            account_type = (
                "demo" if self.environment.lower() in {"demo", "virtual"} else "real"
            )
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

    async def connect_from_otp(
        self,
        account_id: str,
        *,
        bearer_token: str | None = None,
        app_id: str | None = None,
    ) -> AccountIdentity:
        try:
            session = get_authenticated_ws_url(
                account_id,
                bearer_token=bearer_token,
                app_id=app_id,
            )
        except DerivSessionError as exc:
            raise DerivProtocolError(str(exc)) from exc
        self.ws_url = session.url
        self.auth_token = ""
        return await self.connect()

    async def connect_public(self) -> int:
        transport = DerivWebSocketTransport(
            PUBLIC_WS_URL,
            timeout_seconds=self.timeout_seconds,
        )
        previous_transport = self.transport
        self.transport = transport
        try:
            reply = await self._tracked_request("active_symbols", {"active_symbols": "brief"})
            return len(reply.get("active_symbols") or [])
        finally:
            await transport.close()
            self.transport = previous_transport

    async def reconnect(self, fresh_ws_url: str | None = None) -> None:
        if self.transport is None:
            raise DerivProtocolError("BROKER_SESSION_NOT_CONNECTED")
        if not fresh_ws_url:
            raise DerivProtocolError("FRESH_AUTHENTICATED_WS_URL_REQUIRED")
        self._validate_environment_url(fresh_ws_url)
        try:
            await self.transport.reconnect(fresh_url=fresh_ws_url)
            self.ws_url = fresh_ws_url
            await self.get_balance()
        except Exception:
            self.authorized = False
            self.account = None
            await self.close()
            raise

    async def _tracked_request(self, request_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a Deriv API request with correlation and circuit enforcement."""
        if self.transport is None:
            raise DerivProtocolError("BROKER_SESSION_NOT_CONNECTED")
        if not self.circuit.allow_request():
            raise DerivProtocolError("CIRCUIT_BREAKER_OPEN")

        tracked = self.ledger.create_request(request_type, dict(payload))
        reserve_request_id = getattr(self.transport, "reserve_request_id", None)
        if callable(reserve_request_id):
            reserve_request_id(tracked.req_id)
        payload_with_id = {**payload, "req_id": tracked.req_id}
        try:
            reply = await self.transport.request(payload_with_id)
            response_req_id = reply.get("req_id", tracked.req_id)
            if response_req_id != tracked.req_id:
                tracked.state = RequestState.TIMEOUT
                self.circuit.record_failure()
                raise DerivProtocolError("REQUEST_ID_MISMATCH")
            if "error" in reply:
                self.ledger.reject(response_req_id, reply)
                self.circuit.record_failure()
            else:
                self.ledger.confirm(response_req_id, reply)
                self.circuit.record_success()
            return reply
        except Exception as exc:
            tracked.state = RequestState.TIMEOUT
            self.circuit.record_failure()
            if isinstance(exc, DerivTransportError):
                raise DerivProtocolError(str(exc)) from exc
            raise

    async def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._tracked_request("request", payload)

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
        rows = list(
            (await self.request({"active_symbols": "brief"})).get("active_symbols") or []
        )
        # The current Options API renamed the legacy `symbol` response field
        # to `underlying_symbol`. Normalize once at the broker boundary so
        # older internal consumers remain stable without sending legacy fields
        # back to Deriv.
        normalized: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            if item.get("underlying_symbol") and not item.get("symbol"):
                item["symbol"] = item["underlying_symbol"]
            normalized.append(item)
        return normalized

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

    async def subscribe_balance(self) -> AsyncIterator[CapitalSnapshot]:
        if self.transport is None or self.account is None:
            raise DerivProtocolError("BROKER_SESSION_NOT_VERIFIED")
        key = "balance"
        async for message in self.transport.subscribe(key, {"balance": 1}):
            result = message.get("balance") or {}
            loginid = str(result.get("loginid") or self.account.loginid)
            currency = str(result.get("currency") or self.account.currency)
            if loginid != self.account.loginid or currency != self.account.currency:
                raise DerivProtocolError("ACCOUNT_IDENTITY_CHANGED")
            yield CapitalSnapshot(
                balance=float(result["balance"]),
                currency=currency,
                available_balance=float(result["balance"]),
                captured_at=datetime.now(timezone.utc),
                source="deriv:balance_subscription",
                account=self.account,
            )

    async def subscribe_transactions(self) -> AsyncIterator[dict[str, Any]]:
        if self.transport is None:
            raise DerivProtocolError("BROKER_SESSION_NOT_CONNECTED")
        async for message in self.transport.subscribe(
            "transactions",
            {"transaction": 1},
        ):
            transaction = message.get("transaction")
            if transaction:
                yield dict(transaction)

    async def request_proposal(self, parameters: dict[str, Any]) -> str:
        required = ("contract_type", "currency", "underlying_symbol")
        missing = [key for key in required if not parameters.get(key)]
        if missing:
            raise DerivProtocolError(
                "PROPOSAL_PARAMETERS_MISSING:" + ",".join(missing)
            )
        proposal = (
            await self.request({"proposal": 1, **parameters})
        ).get("proposal") or {}
        proposal_id = str(proposal.get("id") or "")
        if not proposal_id:
            raise DerivProtocolError("PROPOSAL_ID_MISSING_FROM_BROKER")
        return proposal_id

    async def submit_authorized_order(self, payload: dict[str, Any]) -> BrokerResult:
        if not self.authorized:
            raise DerivProtocolError("BROKER_SESSION_NOT_AUTHORIZED")
        proposal_id = payload.get("proposal_id")
        if not proposal_id:
            raise DerivProtocolError("ORDER_REQUIRES_BROKER_PROPOSAL_ID")
        try:
            reply = await self.request(
                {"buy": str(proposal_id), "price": payload["stake"]}
            )
        except Exception:
            return BrokerResult(
                BrokerOutcome.UNKNOWN,
                "unknown",
                raw_class="SUBMISSION_RESPONSE_UNKNOWN",
            )
        buy = reply.get("buy") or {}
        transaction_id = str(buy.get("transaction_id") or "") or None
        contract_id = str(buy.get("contract_id") or "") or None
        # A capital-moving acceptance is not considered fully known until
        # both broker identifiers are present. This prevents partial responses
        # from being treated as confirmed economic effects.
        if not transaction_id or not contract_id:
            return BrokerResult(
                BrokerOutcome.UNKNOWN,
                "unknown",
                broker_transaction_id=transaction_id,
                contract_id=contract_id,
                raw_class="BROKER_ACCEPTANCE_PARTIAL",
            )
        return BrokerResult(
            BrokerOutcome.ACCEPTED,
            "buy",
            broker_transaction_id=transaction_id,
            contract_id=contract_id,
            raw_class="BUY_ACCEPTED",
            broker_timestamp=datetime.now(timezone.utc),
        )

    async def resolve_unknown_order(
        self,
        *,
        transaction_id: str | None = None,
        contract_id: str | None = None,
    ) -> dict[str, Any]:
        statement = await self.statement(limit=100)
        portfolio = await self.portfolio()
        transaction = None
        contract = None

        if transaction_id:
            transaction = next(
                (
                    row
                    for row in statement
                    if str(row.get("transaction_id") or row.get("id") or "")
                    == str(transaction_id)
                ),
                None,
            )

        if contract_id:
            contract = next(
                (
                    row
                    for row in portfolio
                    if str(row.get("contract_id") or row.get("id") or "")
                    == str(contract_id)
                ),
                None,
            )

        return {
            "known": transaction is not None or contract is not None,
            "transaction": transaction,
            "contract": contract,
            "recovery_requires_reconciliation": True,
        }

    async def get_contract_status(self, contract_id: str) -> dict[str, Any]:
        reply = await self.request(
            {"proposal_open_contract": 1, "contract_id": int(contract_id)}
        )
        return dict(reply.get("proposal_open_contract") or {})

    async def portfolio(self) -> list[dict[str, Any]]:
        reply = await self.request({"portfolio": 1})
        return list(reply.get("portfolio", {}).get("contracts") or [])

    async def statement(
        self,
        *,
        limit: int = 100,
        action_type: str | None = None,
    ) -> list[dict[str, Any]]:
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
