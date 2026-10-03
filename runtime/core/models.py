from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any, Mapping


def utc_now():
    return datetime.now(timezone.utc)


class RuntimeState(str, Enum):
    BOOT="BOOT"; SELF_CHECK="SELF_CHECK"; BROKER_CONNECTING="BROKER_CONNECTING"; BROKER_VERIFIED="BROKER_VERIFIED"; MARKET_READY="MARKET_READY"; DECISION_READY="DECISION_READY"; AUTHORIZED="AUTHORIZED"; EXECUTING="EXECUTING"; SETTLING="SETTLING"; RECONCILING="RECONCILING"; HEALTHY="HEALTHY"; DEGRADED="DEGRADED"; CAPITAL_PROTECTED="CAPITAL_PROTECTED"; RECOVERY="RECOVERY"; VERIFIED="VERIFIED"; SHUTDOWN="SHUTDOWN"


class BrokerOutcome(str, Enum):
    ACCEPTED="ACCEPTED"; REJECTED="REJECTED"; SETTLED="SETTLED"; UNKNOWN="UNKNOWN"


@dataclass(frozen=True)
class AccountIdentity:
    loginid: str
    account_type: str
    currency: str
    environment: str


@dataclass(frozen=True)
class CapitalSnapshot:
    balance: float
    currency: str
    available_balance: float
    captured_at: datetime
    source: str
    account: AccountIdentity

    def is_valid(self, max_age_seconds: float = 15.0) -> bool:
        if not all(isfinite(v) and v >= 0 for v in (self.balance, self.available_balance)):
            return False
        if self.available_balance > self.balance:
            return False
        if self.currency != self.account.currency:
            return False
        if self.account.environment not in {"real", "demo", "virtual"}:
            return False
        age=(utc_now()-self.captured_at).total_seconds()
        return 0 <= age <= max_age_seconds


@dataclass(frozen=True)
class MarketTick:
    symbol: str
    quote: float
    epoch: int
    received_at: datetime
    sequence: int|None=None

    def valid(self) -> bool:
        return bool(self.symbol) and isfinite(self.quote) and self.quote >= 0 and self.epoch > 0


@dataclass(frozen=True)
class Decision:
    decision_id: str
    strategy_id: str
    strategy_version: str
    strategy_hash: str
    symbol: str
    direction: str
    probability: float
    decision_time: datetime
    market_snapshot_hash: str
    risk_requested_stake: float
    rationale_codes: tuple[str,...]=field(default_factory=tuple)


@dataclass(frozen=True)
class AuthorizationContext:
    decision: Decision
    account: AccountIdentity
    capital: CapitalSnapshot
    config_hash: str
    authorization_id: str
    authorization_issued_at: datetime
    authorization_expires_at: datetime
    kill_switch_off: bool
    risk_approved: bool
    firewall_approved: bool
    reconciliation_healthy: bool
    final_execution_authorization: bool=False

    def is_current(self):
        now=utc_now()
        return self.authorization_issued_at <= now < self.authorization_expires_at and self.kill_switch_off


@dataclass(frozen=True)
class OrderIntent:
    intent_id: str
    decision_id: str
    account: AccountIdentity
    symbol: str
    direction: str
    stake: float
    created_at: datetime
    strategy_hash: str
    config_hash: str
    execution_mode: str
    proposal_id: str|None=None


@dataclass(frozen=True)
class BrokerResult:
    outcome: BrokerOutcome
    request_id: str
    broker_transaction_id: str|None=None
    contract_id: str|None=None
    raw_class: str=""
    broker_timestamp: datetime|None=None


@dataclass(frozen=True)
class LedgerEvent:
    event_id: str
    intent_id: str
    account: AccountIdentity
    event_type: str
    amount: float
    currency: str
    occurred_at: datetime
    broker_transaction_id: str|None=None
    metadata: Mapping[str,Any]=field(default_factory=dict)
