from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from math import isfinite
from typing import Any, AsyncIterator

from runtime.adapters.deriv_session import DerivSessionError, get_authenticated_ws_url, validate_modern_options_ws_url
from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport
from runtime.security.deriv_auth_gate import (
    AuthModeMismatchError,
    DerivAuthenticationGate,
    SecurityError,
)
from runtime.core.circuit import CircuitBreaker
from runtime.core.events import sha256
from runtime.core.request_ledger import RequestLedger, RequestState
from runtime.core.secrets import get_optional_secret
from runtime.oauth.client import DerivOAuthError
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
    _requires_executor_capability = True

    """Transport-only Deriv Options API boundary for AURELIA.

    Generic request calls are restricted to an explicit non-mutating action
    allowlist. Capital-moving requests are only constructed by the dedicated
    executor submission method after the adapter has an authorized account
    session; they cannot be smuggled through request() or mixed with read calls.
    """

    _READ_REQUEST_FIELDS = {
        "active_symbols": frozenset({"active_symbols", "req_id", "passthrough"}),
        "balance": frozenset({"balance", "subscribe", "req_id", "passthrough"}),
        "portfolio": frozenset({"portfolio", "req_id", "passthrough"}),
        "statement": frozenset({
            "statement", "limit", "offset", "action_type", "date_from",
            "date_to", "req_id", "passthrough",
        }),
        "proposal": frozenset({
            "proposal", "amount", "basis", "contract_type", "currency",
            "duration", "duration_unit", "underlying_symbol", "barrier",
            "date_expiry", "req_id", "passthrough",
        }),
        "proposal_open_contract": frozenset({
            "proposal_open_contract", "contract_id", "subscribe",
            "req_id", "passthrough",
        }),
    }
    _CAPITAL_ACTIONS = frozenset({
        "buy", "sell", "cancel", "contract_update", "payout",
        "deposit", "withdrawal", "transfer", "topup",
        "paymentagent_transfer",
    })

    @classmethod
    def _validate_request_payload(
        cls,
        payload: dict[str, Any],
        *,
        executor_submission: bool = False,
    ) -> str:
        if not isinstance(payload, dict) or not payload:
            raise DerivProtocolError("BROKER_REQUEST_PAYLOAD_INVALID")

        recognized_actions = set(cls._READ_REQUEST_FIELDS).union(cls._CAPITAL_ACTIONS)
        actions = set(payload).intersection(recognized_actions)
        if len(actions) != 1:
            raise DerivProtocolError("BROKER_REQUEST_ACTION_INVALID")

        action = next(iter(actions))
        if action in cls._CAPITAL_ACTIONS:
            if not (executor_submission and action == "buy"):
                raise DerivProtocolError(
                    "CAPITAL_ACTION_REQUIRES_EXECUTOR_AUTHORITY"
                )
            allowed_fields = frozenset({"buy", "price"})
        else:
            if executor_submission:
                raise DerivProtocolError("EXECUTOR_BUY_ACTION_REQUIRED")
            allowed_fields = cls._READ_REQUEST_FIELDS[action]

        if not set(payload).issubset(allowed_fields):
            raise DerivProtocolError("BROKER_REQUEST_FIELD_NOT_ALLOWED")
        return action

    def __init__(
        self,
        *,
        ws_url: str | None = None,
        auth_token: str | None = None,
        expected_loginid: str | None = None,
        expected_currency: str | None = None,
        environment: str = "real",
        timeout_seconds: float = 10.0,
    ):
        self.ws_url = ws_url or os.getenv("DERIV_WS_URL", "")
        # Account authentication is disabled until a verifiable read-only
        # broker permission exists. Do not retain credential material here.
        self.auth_token = ""
        self.expected_loginid = (
            expected_loginid or get_optional_secret("DERIV_EXPECTED_LOGINID")
        )
        configured_currency = expected_currency if expected_currency is not None else os.getenv("DERIV_EXPECTED_CURRENCY", "")
        self.expected_currency = str(configured_currency).strip().upper()
        self.environment = environment
        self.timeout_seconds = timeout_seconds
        self.transport: DerivWebSocketTransport | None = None
        self.authorized = False
        self.account: AccountIdentity | None = None
        self._executor_capability: object | None = None
        self._oauth_extension: Any | None = None
        self.circuit = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout_seconds=60.0,
            half_open_max_requests=1,
        )
        self.ledger = RequestLedger(max_pending_age_seconds=30.0)
        self._subscription_keys: set[str] = set()

    def attach_oauth_extension(self, extension: Any) -> None:
        if getattr(extension, "adapter", None) is not self:
            raise DerivProtocolError("OAUTH_EXTENSION_ADAPTER_MISMATCH")
        if self._oauth_extension is not None and self._oauth_extension is not extension:
            raise DerivProtocolError("OAUTH_EXTENSION_ALREADY_ATTACHED")
        self._oauth_extension = extension

    def initiate_oauth_authorization(self, *, redirect_uri: str, session_binding: str) -> str:
        extension = self._oauth_extension
        if extension is None:
            raise DerivProtocolError("DERIV_OAUTH_EXTENSION_NOT_CONFIGURED")
        return extension.initiate_authorization(
            redirect_uri=redirect_uri, session_binding=session_binding
        )

    async def complete_oauth_authorization(
        self, *, auth_code: str, state: str, redirect_uri: str, session_binding: str
    ):
        extension = self._oauth_extension
        if extension is None:
            raise DerivProtocolError("DERIV_OAUTH_EXTENSION_NOT_CONFIGURED")
        return await extension.complete_authorization(
            auth_code=auth_code, state=state,
            redirect_uri=redirect_uri, session_binding=session_binding,
        )

    def _bind_executor_capability(self, capability: object) -> None:
        """Bind this adapter to exactly one capital-plane executor instance."""
        if capability is None:
            raise DerivProtocolError("BROKER_EXECUTOR_CAPABILITY_REQUIRED")
        if self._executor_capability is not None:
            if self._executor_capability is capability:
                return
            raise DerivProtocolError("BROKER_EXECUTOR_CAPABILITY_ALREADY_BOUND")
        self._executor_capability = capability

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
        if not self.expected_currency:
            raise DerivProtocolError("EXPECTED_ACCOUNT_CURRENCY_REQUIRED")
        try:
            DerivAuthenticationGate(plane="account").get_client()
        except (AuthModeMismatchError, SecurityError) as exc:
            raise DerivProtocolError(str(exc)) from exc
        raise DerivProtocolError("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")

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

    async def connect_demo_with_oauth(
        self,
        *,
        account_id: str,
        expected_currency: str,
    ) -> AccountIdentity:
        """Connect one exact demo account through OAuth, REST OTP and WS.

        This bootstrap never creates a real-account session or changes the
        capital-plane release state. The OTP URL remains an in-memory secret.
        """
        if self._oauth_extension is None:
            raise DerivProtocolError("DERIV_OAUTH_EXTENSION_NOT_CONFIGURED")
        if not isinstance(expected_currency, str) or not expected_currency.strip():
            raise DerivProtocolError("EXPECTED_ACCOUNT_CURRENCY_REQUIRED")
        try:
            session = await asyncio.to_thread(
                self._oauth_extension.create_authenticated_demo_session,
                account_id=account_id,
                expected_currency=expected_currency,
            )
        except DerivOAuthError as exc:
            raise DerivProtocolError(str(exc)) from None
        except Exception:
            raise DerivProtocolError("DERIV_OAUTH_DEMO_BOOTSTRAP_FAILED") from None

        try:
            validate_modern_options_ws_url(
                session.websocket_url,
                expected_environment="demo",
            )
            if (
                session.account.account_id != account_id
                or session.account.account_type != "demo"
                or session.account.status != "active"
                or session.account.currency != expected_currency.strip().upper()
            ):
                raise DerivProtocolError("DERIV_DEMO_ACCOUNT_BINDING_MISMATCH")

            if self.transport is None:
                transport = DerivWebSocketTransport(
                    session.websocket_url,
                    timeout_seconds=self.timeout_seconds,
                )
                await transport.connect()
                self.transport = transport
            else:
                await self.transport.reconnect(fresh_url=session.websocket_url)

            self.ws_url = session.websocket_url
            self.auth_token = ""
            self.authorized = False
            self.account = None

            reply = await self._tracked_request("balance", {"balance": 1})
            result = reply.get("balance")
            if not isinstance(result, dict):
                raise DerivProtocolError("OPTIONS_BALANCE_RESPONSE_INVALID")
            amount = result.get("balance")
            currency = result.get("currency")
            if (
                isinstance(amount, bool)
                or not isinstance(amount, (int, float))
                or not isfinite(float(amount))
                or float(amount) < 0
            ):
                raise DerivProtocolError("OPTIONS_BALANCE_VALUE_INVALID")
            if currency != session.account.currency:
                raise DerivProtocolError("CURRENCY_CHANGED")
            returned_account_id = result.get("account_id")
            if returned_account_id is not None and returned_account_id != account_id:
                raise DerivProtocolError("ACCOUNT_IDENTITY_CHANGED")

            returned_loginid = result.get("loginid")
            if returned_loginid is not None and (
                not isinstance(returned_loginid, str) or not returned_loginid.strip()
            ):
                raise DerivProtocolError("LEGACY_LOGINID_RESPONSE_INVALID")
            self.account = AccountIdentity(
                loginid=returned_loginid,
                account_type="demo",
                currency=session.account.currency,
                environment="demo",
                account_id=account_id,
            )
            self.environment = "demo"
            self.expected_currency = session.account.currency
            self.authorized = True
            return self.account
        except Exception:
            await self.close()
            raise

    async def connect_public(self) -> int:
        transport = DerivWebSocketTransport(
            PUBLIC_WS_URL,
            timeout_seconds=self.timeout_seconds,
        )
        await transport.connect()
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

    async def _tracked_request(
        self,
        request_type: str,
        payload: dict[str, Any],
        *,
        executor_capability: object | None = None,
    ) -> dict[str, Any]:
        """Send a request after action validation, with correlation and circuit enforcement."""
        executor_submission = (
            self._executor_capability is not None
            and executor_capability is self._executor_capability
        )
        action = self._validate_request_payload(
            payload,
            executor_submission=executor_submission,
        )
        if executor_submission and (request_type != "buy" or action != "buy"):
            raise DerivProtocolError("EXECUTOR_BUY_ACTION_REQUIRED")
        if self.transport is None:
            raise DerivProtocolError("BROKER_SESSION_NOT_CONNECTED")
        if not self.circuit.allow_request():
            raise DerivProtocolError("CIRCUIT_BREAKER_OPEN")

        allocate_request_id = getattr(self.transport, "allocate_request_id", None)
        if callable(allocate_request_id):
            reserved_req_id = allocate_request_id()
            tracked = self.ledger.create_request(
                request_type,
                dict(payload),
                req_id=reserved_req_id,
            )
        else:
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
        result = (await self.request({"balance": 1})).get("balance")
        if not isinstance(result, dict):
            raise DerivProtocolError("OPTIONS_BALANCE_RESPONSE_INVALID")
        raw_amount = result.get("balance")
        if (
            isinstance(raw_amount, bool)
            or not isinstance(raw_amount, (int, float))
            or not isfinite(float(raw_amount))
            or float(raw_amount) < 0
        ):
            raise DerivProtocolError("OPTIONS_BALANCE_VALUE_INVALID")
        amount = float(raw_amount)
        currency = str(result.get("currency") or "").strip().upper()
        if currency != self.account.currency:
            raise DerivProtocolError("CURRENCY_CHANGED")
        returned_account_id = result.get("account_id")
        if (
            returned_account_id is not None
            and returned_account_id != self.account.account_id
        ):
            raise DerivProtocolError("ACCOUNT_IDENTITY_CHANGED")
        returned_loginid = result.get("loginid")
        if (
            self.account.loginid is not None
            and returned_loginid is not None
            and returned_loginid != self.account.loginid
        ):
            raise DerivProtocolError("ACCOUNT_IDENTITY_CHANGED")
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

    async def submit_authorized_order(
        self,
        payload: dict[str, Any],
        *,
        executor_capability: object | None = None,
    ) -> BrokerResult:
        if (
            self._executor_capability is None
            or executor_capability is not self._executor_capability
        ):
            raise DerivProtocolError("BROKER_EXECUTOR_CAPABILITY_REQUIRED")
        if not self.authorized or self.account is None:
            raise DerivProtocolError("BROKER_SESSION_NOT_AUTHORIZED")
        if (
            self.account.account_type != "real"
            or self.account.environment != "real"
        ):
            raise DerivProtocolError("LIVE_ORDER_REQUIRES_REAL_ACCOUNT")
        if not isinstance(payload, dict) or set(payload) != {"proposal_id", "stake"}:
            raise DerivProtocolError("ORDER_PAYLOAD_INVALID")

        proposal_id = payload.get("proposal_id")
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise DerivProtocolError("ORDER_REQUIRES_BROKER_PROPOSAL_ID")
        stake = payload.get("stake")
        if (
            isinstance(stake, bool)
            or not isinstance(stake, (int, float))
            or not isfinite(float(stake))
            or float(stake) <= 0
        ):
            raise DerivProtocolError("ORDER_STAKE_INVALID")

        try:
            # This is the only adapter method allowed to construct a buy
            # request. It is called by CapitalPlaneExecutor after the
            # deterministic release, risk, firewall, exposure, reconciliation,
            # fencing, idempotency, proposal-binding and balance checks.
            reply = await self._tracked_request(
                "buy",
                {"buy": proposal_id.strip(), "price": float(stake)},
                executor_capability=executor_capability,
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
        date_from: int | None = None,
        date_to: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not 1 <= int(limit) <= 999:
            raise ValueError("DERIV_STATEMENT_LIMIT_INVALID")
        if isinstance(offset, bool) or int(offset) < 0:
            raise ValueError("DERIV_STATEMENT_OFFSET_INVALID")
        if date_from is not None and (isinstance(date_from, bool) or int(date_from) < 0):
            raise ValueError("DERIV_STATEMENT_DATE_FROM_INVALID")
        if date_to is not None and (isinstance(date_to, bool) or int(date_to) < 0):
            raise ValueError("DERIV_STATEMENT_DATE_TO_INVALID")
        if date_from is not None and date_to is not None and int(date_to) < int(date_from):
            raise ValueError("DERIV_STATEMENT_DATE_WINDOW_INVALID")
        payload: dict[str, Any] = {"statement": 1, "limit": int(limit), "offset": int(offset)}
        if action_type:
            payload["action_type"] = action_type
        if date_from is not None:
            payload["date_from"] = int(date_from)
        if date_to is not None:
            payload["date_to"] = int(date_to)
        reply = await self.request(payload)
        statement = reply.get("statement") or {}
        return list(statement.get("transactions") or [])

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
