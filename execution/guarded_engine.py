"""Fail-closed execution boundary for AURELIA's Deriv Options API.

This module is deliberately separate from signal generation. It accepts a validated
proposal ID from the existing strategy/adapter path, reconciles broker state before
a purchase, and blocks execution on any ambiguity. It does not claim broker-enforced
exactly-once semantics: Deriv's documented `buy` endpoint does not document a
client UUID as an idempotency key. The UUID is carried in `passthrough` for
correlation only.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable, Mapping, Protocol


class ExecutionHalted(RuntimeError):
    """Raised when execution is halted until an operator manually resets it."""


class StateMismatch(ExecutionHalted):
    """Raised when local state differs from a fresh broker snapshot."""


class BrokerAmbiguous(ExecutionHalted):
    """Raised when a request may have reached the broker but is not verifiable."""


class Adapter(Protocol):
    """Minimum interface implemented by AURELIA's DerivAdapter."""

    authorized: bool

    async def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send one request and return its decoded Deriv response."""


@dataclass(frozen=True)
class AccountSnapshot:
    """Comparable broker state captured from balance and open-contract endpoints."""

    loginid: str
    currency: str
    balance: Decimal
    open_contracts: tuple[tuple[str, str, str, str], ...]
    # Each contract tuple is (contract_id, contract_type, currency, buy_price).


@dataclass(frozen=True)
class TradeIntent:
    """A single proposed purchase, fully specified before execution."""

    proposal_id: str
    price_limit: Decimal
    symbol: str
    contract_type: str
    currency: str
    stake: Decimal
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class RiskLimits:
    """Hard circuit-breaker limits. Values are fractions unless stated otherwise."""

    daily_loss_fraction: Decimal = Decimal("0.03")
    consecutive_losses: int = 3
    max_drawdown_fraction: Decimal = Decimal("0.08")


class RiskManager:
    """Synchronous signal interceptor with sticky, manual-reset circuit breakers."""

    def __init__(self, limits: RiskLimits = RiskLimits()) -> None:
        if not (Decimal("0") < limits.daily_loss_fraction < Decimal("1")):
            raise ValueError("daily_loss_fraction must be between 0 and 1")
        if limits.consecutive_losses < 1:
            raise ValueError("consecutive_losses must be >= 1")
        if not (Decimal("0") < limits.max_drawdown_fraction < Decimal("1")):
            raise ValueError("max_drawdown_fraction must be between 0 and 1")
        self.limits = limits
        self.halted = False
        self.halt_reason: str | None = None
        self.daily_starting_balance: Decimal | None = None
        self.daily_net_pnl = Decimal("0")
        self.consecutive_losses = 0
        self.high_water_mark: Decimal | None = None

    def initialize_session(self, starting_balance: Decimal) -> None:
        """Set session anchors once from a verified broker balance."""
        if starting_balance <= 0:
            self._halt("INVALID_STARTING_BALANCE")
            raise ExecutionHalted(self.halt_reason or "INVALID_STARTING_BALANCE")
        self.daily_starting_balance = starting_balance
        self.high_water_mark = starting_balance

    def authorize_signal(self, equity: Decimal) -> None:
        """Reject every signal when a circuit breaker has tripped."""
        if self.halted:
            raise ExecutionHalted(self.halt_reason or "RISK_MANAGER_HALTED")
        if self.daily_starting_balance is None or self.high_water_mark is None:
            self._halt("RISK_SESSION_NOT_INITIALIZED")
            raise ExecutionHalted(self.halt_reason or "RISK_SESSION_NOT_INITIALIZED")
        self.high_water_mark = max(self.high_water_mark, equity)
        daily_floor = -self.daily_starting_balance * self.limits.daily_loss_fraction
        drawdown_floor = self.high_water_mark * (
            Decimal("1") - self.limits.max_drawdown_fraction
        )
        if self.daily_net_pnl < daily_floor:
            self._halt("DAILY_LOSS_LIMIT")
        elif self.consecutive_losses >= self.limits.consecutive_losses:
            self._halt("CONSECUTIVE_LOSS_LIMIT")
        elif equity < drawdown_floor:
            self._halt("MAX_DRAWDOWN_LIMIT")
        if self.halted:
            raise ExecutionHalted(self.halt_reason or "RISK_LIMIT_BREACHED")

    def record_closed_trade(self, net_pnl: Decimal, equity: Decimal) -> None:
        """Update realised P&L and loss streak from broker-confirmed settlement."""
        if self.daily_starting_balance is None:
            self._halt("RISK_SESSION_NOT_INITIALIZED")
            raise ExecutionHalted(self.halt_reason or "RISK_SESSION_NOT_INITIALIZED")
        self.daily_net_pnl += net_pnl
        self.high_water_mark = max(self.high_water_mark or equity, equity)
        self.consecutive_losses = (
            self.consecutive_losses + 1 if net_pnl < 0 else 0
        )
        # Check immediately on settlement; do not wait for the next signal.
        try:
            self.authorize_signal(equity)
        except ExecutionHalted:
            raise

    def manual_reset(self, *, starting_balance: Decimal) -> None:
        """Explicit operator action. This is never called automatically."""
        if starting_balance <= 0:
            raise ValueError("starting_balance must be positive")
        self.halted = False
        self.halt_reason = None
        self.daily_starting_balance = starting_balance
        self.daily_net_pnl = Decimal("0")
        self.consecutive_losses = 0
        self.high_water_mark = starting_balance

    def _halt(self, reason: str) -> None:
        self.halted = True
        self.halt_reason = reason


class SecretMaskFilter(logging.Filter):
    """Mask environment secrets, bearer tokens, and account identifiers in logs."""

    _PATTERNS = (
        re.compile(r"(?i)(bearer\\s+)[A-Za-z0-9._~+/-]+=*"),
        re.compile(r"(?i)((?:token|pat|api[_-]?key|otp|secret)\\s*[:=]\\s*)[^\\s,;]+"),
        re.compile(r"(?i)((?:loginid|account[_-]?id)\\s*[:=]\\s*)[A-Z0-9_-]+"),
        re.compile(r"(?i)(wss://[^\\s?]+\\?[^\\s]*otp=)[^&\\s]+"),
    )

    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        env_secrets = [
            value for key, value in os.environ.items()
            if value and any(word in key.upper() for word in (
                "TOKEN", "PAT", "SECRET", "PASSWORD", "API_KEY", "OTP"
            ))
        ]
        self._secrets = sorted(set((secrets or []) + env_secrets), key=len, reverse=True)

    def filter(self, record: logging.LogRecord) -> bool:
        rendered = record.getMessage()
        for secret in self._secrets:
            if len(secret) >= 4:
                rendered = rendered.replace(secret, "[REDACTED]")
        for pattern in self._PATTERNS:
            rendered = pattern.sub(r"\\1[REDACTED]", rendered)
        record.msg = rendered
        record.args = ()
        return True


class SecureLogger:
    """Configure one redacting logger for stdout/file handlers."""

    def __init__(self, name: str = "aurelia.execution") -> None:
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"
            ))
            handler.addFilter(SecretMaskFilter())
            self.logger.addHandler(handler)
        else:
            # Attach a filter to every existing handler too; filters on a logger
            # alone do not redact messages created by child loggers.
            for handler in self.logger.handlers:
                if not any(isinstance(f, SecretMaskFilter) for f in handler.filters):
                    handler.addFilter(SecretMaskFilter())

    def __getattr__(self, name: str) -> Any:
        return getattr(self.logger, name)


TradingStatusCheck = Callable[[], Awaitable[bool]]


class ExecutionEngine:
    """Reconcile, risk-check, and execute through AURELIA's existing adapter."""

    def __init__(
        self,
        adapter: Adapter,
        risk_manager: RiskManager,
        *,
        status_check: TradingStatusCheck,
        mode: str | None = None,
        logger: SecureLogger | logging.Logger | None = None,
        response_timeout: float = 8.0,
        verification_attempts: int = 3,
    ) -> None:
        # LIVE requires an explicit opt-in; every other value is verify-only.
        requested_mode = (mode or os.getenv("AURELIA_MODE", "VERIFY_ONLY")).upper()
        if requested_mode not in {"VERIFY_ONLY", "LIVE"}:
            raise ValueError("AURELIA_MODE must be VERIFY_ONLY or LIVE")
        self.mode = requested_mode
        self.adapter = adapter
        self.risk = risk_manager
        self.status_check = status_check
        self.logger = logger or SecureLogger()
        self.response_timeout = response_timeout
        self.verification_attempts = max(1, verification_attempts)
        self.halted = False
        self.halt_reason: str | None = None
        self.local_snapshot: AccountSnapshot | None = None
        self._lock = asyncio.Lock()
        self._pending_intents: set[str] = set()

    async def verify_only(self) -> AccountSnapshot:
        """Authenticate, verify account balance/contracts and trading status.

        This method never calls the buy endpoint, even when AURELIA_MODE=LIVE.
        """
        if not getattr(self.adapter, "authorized", False):
            self._halt("BROKER_SESSION_NOT_AUTHORIZED")
        if not await self.status_check():
            self._halt("BROKER_TRADING_STATUS_NOT_VERIFIED")
        snapshot = await self._broker_snapshot()
        if self.local_snapshot is not None and snapshot != self.local_snapshot:
            self._halt("STATE_MISMATCH")
        self.local_snapshot = snapshot
        if self.risk.daily_starting_balance is None:
            self.risk.initialize_session(snapshot.balance)
        self.logger.info("VERIFY_ONLY checks passed; no order was submitted")
        return snapshot

    async def execute(self, intent: TradeIntent) -> dict[str, Any]:
        """Execute a single intent with preflight reconciliation and ambiguity halt."""
        async with self._lock:
            self._assert_not_halted()
            if self.mode != "LIVE":
                raise ExecutionHalted("VERIFY_ONLY_BLOCKS_BUY")
            if not getattr(self.adapter, "authorized", False):
                self._halt("BROKER_SESSION_NOT_AUTHORIZED")
            if intent.intent_id in self._pending_intents:
                self._halt("DUPLICATE_LOCAL_INTENT")
            if intent.stake <= 0 or intent.price_limit <= 0:
                self._halt("INVALID_STAKE_OR_PRICE")
            if intent.currency.upper() != intent.currency:
                self._halt("CURRENCY_NOT_CANONICAL")

            if not await self.status_check():
                self._halt("BROKER_TRADING_STATUS_NOT_VERIFIED")
            fresh = await self._broker_snapshot()
            if self.local_snapshot is None or fresh != self.local_snapshot:
                self._halt("STATE_MISMATCH")
            self.risk.authorize_signal(fresh.balance)
            if intent.currency != fresh.currency:
                self._halt("INTENT_CURRENCY_MISMATCH")
            if intent.stake > fresh.balance:
                self._halt("INSUFFICIENT_AVAILABLE_BALANCE")

            self._pending_intents.add(intent.intent_id)
            # Deriv's documented buy schema does not promise that `refers` is
            # an idempotency key. Use passthrough for traceability only.
            request = {
                "buy": intent.proposal_id,
                "price": float(intent.price_limit),
                "passthrough": {
                    "aurelia_intent_id": intent.intent_id,
                    "symbol": intent.symbol,
                    "contract_type": intent.contract_type,
                },
            }
            try:
                response = await asyncio.wait_for(
                    self.adapter.request(request), timeout=self.response_timeout
                )
            except (asyncio.TimeoutError, ConnectionError, OSError) as exc:
                # A timeout does not prove the broker rejected the order. Never
                # resend. Query broker state; if it cannot be resolved, halt.
                try:
                    found = await self._verify_intent_outcome(intent)
                except Exception as verify_exc:
                    self._halt("BUY_OUTCOME_UNKNOWN")
                    raise BrokerAmbiguous("BUY_OUTCOME_UNKNOWN; no retry attempted") from verify_exc
                if found is None:
                    self._halt("BUY_OUTCOME_UNKNOWN")
                    raise BrokerAmbiguous("BUY_OUTCOME_UNKNOWN; no retry attempted") from exc
                response = {"buy": found, "recovered_after_timeout": True}
            except Exception as exc:
                self._halt("BUY_REQUEST_OUTCOME_UNKNOWN")
                raise BrokerAmbiguous("BUY_REQUEST_OUTCOME_UNKNOWN; no retry attempted") from exc

            if "error" in response or not isinstance(response.get("buy"), dict):
                # An explicit broker error is a rejected intent; any malformed
                # response is ambiguous and must not be retried automatically.
                if "error" in response:
                    self._halt("BROKER_REJECTED_BUY")
                    raise ExecutionHalted("BROKER_REJECTED_BUY")
                self._halt("BUY_RESPONSE_UNVERIFIABLE")
                raise BrokerAmbiguous("BUY_RESPONSE_UNVERIFIABLE")

            bought = response["buy"]
            contract_id = str(bought.get("contract_id") or "")
            if not contract_id:
                self._halt("BUY_CONTRACT_ID_MISSING")
                raise BrokerAmbiguous("BUY_CONTRACT_ID_MISSING")
            verified = await self._verify_contract(intent, contract_id)
            # Refresh state from broker only after a verified contract.
            self.local_snapshot = await self._broker_snapshot()
            self.logger.info(
                "Broker contract verified; intent_id=%s contract_id=%s",
                intent.intent_id, contract_id,
            )
            return {"buy": bought, "verification": verified}

    async def _broker_snapshot(self) -> AccountSnapshot:
        """Read balance and all open contracts; fail on incomplete responses."""
        balance_reply = await self.adapter.request({"balance": 1})
        if "error" in balance_reply or not isinstance(balance_reply.get("balance"), dict):
            self._halt("BALANCE_QUERY_FAILED")
        balance = balance_reply["balance"]
        loginid = str(balance.get("loginid") or balance.get("login_id") or "")
        currency = str(balance.get("currency") or "").strip().upper()
        try:
            amount = Decimal(str(balance["balance"]))
        except (KeyError, InvalidOperation) as exc:
            self._halt("BALANCE_UNVERIFIABLE")
            raise ExecutionHalted("BALANCE_UNVERIFIABLE") from exc
        if not loginid or not currency or not amount.is_finite():
            self._halt("BALANCE_IDENTITY_OR_VALUE_UNVERIFIED")

        # Current Deriv API returns the active open-contract stream when
        # contract_id is omitted. Request one snapshot (not a subscription).
        contract_reply = await self.adapter.request({"proposal_open_contract": 1})
        if "error" in contract_reply:
            self._halt("OPEN_CONTRACT_QUERY_FAILED")
        rows = contract_reply.get("proposal_open_contract")
        if rows is None:
            # Some responses contain a single object; a missing object is not
            # silently interpreted as an empty portfolio.
            self._halt("OPEN_CONTRACT_STATE_UNVERIFIABLE")
        if isinstance(rows, dict):
            row_list = [rows]
        elif isinstance(rows, list):
            row_list = rows
        else:
            self._halt("OPEN_CONTRACT_STATE_UNVERIFIABLE")
        contracts: list[tuple[str, str, str, str]] = []
        for row in row_list:
            if not isinstance(row, dict):
                self._halt("OPEN_CONTRACT_STATE_UNVERIFIABLE")
            contract_id = str(row.get("contract_id") or "")
            if not contract_id:
                self._halt("OPEN_CONTRACT_ID_MISSING")
            contracts.append((
                contract_id,
                str(row.get("contract_type") or ""),
                str(row.get("currency") or "").upper(),
                str(row.get("buy_price") or ""),
            ))
        return AccountSnapshot(
            loginid=loginid,
            currency=currency,
            balance=amount,
            open_contracts=tuple(sorted(contracts)),
        )

    async def _verify_contract(
        self, intent: TradeIntent, contract_id: str
    ) -> dict[str, Any]:
        """Confirm one contract exists once and matches the requested intent."""
        matches: list[dict[str, Any]] = []
        for attempt in range(self.verification_attempts):
            reply = await self.adapter.request({
                "proposal_open_contract": 1,
                "contract_id": int(contract_id),
            })
            if "error" in reply:
                self._halt("POST_BUY_CONTRACT_QUERY_FAILED")
            row = reply.get("proposal_open_contract")
            if isinstance(row, dict):
                matches = [row]
            elif isinstance(row, list):
                matches = [item for item in row if isinstance(item, dict)]
            else:
                matches = []
            if matches:
                break
            if attempt + 1 < self.verification_attempts:
                await asyncio.sleep(min(0.25 * (attempt + 1), 1.0))
        if len(matches) != 1:
            self._halt("POST_BUY_CONTRACT_NOT_UNIQUE")
        contract = matches[0]
        if str(contract.get("contract_id")) != contract_id:
            self._halt("POST_BUY_CONTRACT_ID_MISMATCH")
        if str(contract.get("contract_type") or "") != intent.contract_type:
            self._halt("POST_BUY_CONTRACT_TYPE_MISMATCH")
        if str(contract.get("currency") or "").upper() != intent.currency:
            self._halt("POST_BUY_CURRENCY_MISMATCH")
        if str(contract.get("underlying") or contract.get("symbol") or "") != intent.symbol:
            self._halt("POST_BUY_SYMBOL_MISMATCH")
        try:
            buy_price = Decimal(str(contract.get("buy_price")))
        except InvalidOperation as exc:
            self._halt("POST_BUY_PRICE_UNVERIFIABLE")
            raise ExecutionHalted("POST_BUY_PRICE_UNVERIFIABLE") from exc
        if buy_price != intent.stake:
            self._halt("POST_BUY_STAKE_MISMATCH")
        return contract

    async def _verify_intent_outcome(
        self, intent: TradeIntent
    ) -> dict[str, Any] | None:
        """Inspect broker state after timeout; never resubmit the original buy."""
        snapshot = await self._broker_snapshot()
        if self.local_snapshot and snapshot.balance > self.local_snapshot.balance:
            # A balance increase alone is not proof of this purchase.
            self._halt("TIMEOUT_OUTCOME_NOT_CORRELATED")
        # passthrough is not guaranteed to be returned by every contract view.
        # Only a broker contract matching all intent fields can be recovered.
        matches = []
        for contract_id, contract_type, currency, buy_price in snapshot.open_contracts:
            if (
                contract_type == intent.contract_type
                and currency == intent.currency
                and buy_price
                and Decimal(buy_price) == intent.stake
            ):
                reply = await self.adapter.request({
                    "proposal_open_contract": 1,
                    "contract_id": int(contract_id),
                })
                row = reply.get("proposal_open_contract") if "error" not in reply else None
                if isinstance(row, dict) and (
                    str(row.get("underlying") or row.get("symbol") or "") == intent.symbol
                ):
                    matches.append(row)
        if len(matches) > 1:
            self._halt("TIMEOUT_MATCH_NOT_UNIQUE")
        return matches[0] if len(matches) == 1 else None

    def manual_reset(self, *, verified_snapshot: AccountSnapshot) -> None:
        """Reset sticky engine/risk halts only from a verified operator action."""
        self.halted = False
        self.halt_reason = None
        self.local_snapshot = verified_snapshot
        self.risk.manual_reset(starting_balance=verified_snapshot.balance)
        self._pending_intents.clear()

    def _assert_not_halted(self) -> None:
        if self.halted or self.risk.halted:
            raise ExecutionHalted(self.halt_reason or self.risk.halt_reason or "HALTED")

    def _halt(self, reason: str) -> None:
        self.halted = True
        self.halt_reason = reason
        self.logger.error("EXECUTION_HALTED reason=%s", reason)
        raise ExecutionHalted(reason)
