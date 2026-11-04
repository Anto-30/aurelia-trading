from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any, Mapping
from uuid import UUID


def utc_now():
    return datetime.now(timezone.utc)


class RuntimeState(str, Enum):
    BOOT="BOOT"; SELF_CHECK="SELF_CHECK"; BROKER_CONNECTING="BROKER_CONNECTING"; BROKER_VERIFIED="BROKER_VERIFIED"; MARKET_READY="MARKET_READY"; DECISION_READY="DECISION_READY"; AUTHORIZED="AUTHORIZED"; EXECUTING="EXECUTING"; SETTLING="SETTLING"; RECONCILING="RECONCILING"; HEALTHY="HEALTHY"; DEGRADED="DEGRADED"; CAPITAL_PROTECTED="CAPITAL_PROTECTED"; RECOVERY="RECOVERY"; VERIFIED="VERIFIED"; SHUTDOWN="SHUTDOWN"


class BrokerOutcome(str, Enum):
    ACCEPTED="ACCEPTED"; REJECTED="REJECTED"; SETTLED="SETTLED"; UNKNOWN="UNKNOWN"


@dataclass(frozen=True)
class AccountIdentity:
    """Account identity with separate modern Options and legacy namespaces."""

    loginid: str | None
    account_type: str
    currency: str
    environment: str
    account_id: str | None = None

    @property
    def canonical_account_key(self) -> str | None:
        if self.account_id:
            return "deriv-options:" + self.account_id
        if self.loginid:
            return "deriv-legacy:" + self.loginid
        return None


@dataclass(frozen=True)
class CapitalSnapshot:
    balance: float
    currency: str
    available_balance: float
    captured_at: datetime
    source: str
    account: AccountIdentity

    def is_valid(self, max_age_seconds: float = 15.0) -> bool:
        if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, (int, float)):
            return False
        if isinstance(self.balance, bool) or not isinstance(self.balance, (int, float)):
            return False
        if isinstance(self.available_balance, bool) or not isinstance(
            self.available_balance, (int, float)
        ):
            return False
        try:
            max_age = float(max_age_seconds)
            balance = float(self.balance)
            available = float(self.available_balance)
        except (TypeError, ValueError, OverflowError):
            return False
        if not isfinite(max_age) or max_age <= 0:
            return False
        if not isfinite(balance) or not isfinite(available) or balance < 0 or available < 0:
            return False
        if available > balance:
            return False
        if not isinstance(self.account, AccountIdentity):
            return False
        if not isinstance(self.currency, str) or not self.currency.strip():
            return False
        if self.currency.strip().upper() != str(self.account.currency).strip().upper():
            return False
        if self.account.environment not in {"real", "demo", "virtual"}:
            return False
        if not isinstance(self.captured_at, datetime) or self.captured_at.tzinfo is None:
            return False
        try:
            age = (utc_now() - self.captured_at).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return False
        return isfinite(age) and 0 <= age <= max_age


@dataclass(frozen=True)
class MarketTick:
    symbol: str
    quote: float
    epoch: int
    received_at: datetime
    sequence: int|None=None

    def valid(self) -> bool:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            return False
        if isinstance(self.quote, bool) or not isinstance(self.quote, (int, float)):
            return False
        try:
            quote = float(self.quote)
        except (TypeError, ValueError, OverflowError):
            return False
        if not isfinite(quote) or quote < 0:
            return False
        if isinstance(self.epoch, bool) or not isinstance(self.epoch, int) or self.epoch <= 0:
            return False
        if not isinstance(self.received_at, datetime) or self.received_at.tzinfo is None:
            return False
        if self.sequence is not None and (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            return False
        return True


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
    average_win: float | None = None
    average_loss: float | None = None
    execution_cost: float = 0.0
    slippage_cost: float = 0.0
    quote_cost: float = 0.0
    expected_value: float | None = None


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
    proposal_parameters_hash: str|None=None


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


# Composite broker identity: each namespace remains distinct.  SHA-256 below is
# an integrity checksum, not a signature, identity provider, or proof of broker scope.


def _identity_timestamp_valid(value: datetime) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() == timezone.utc.utcoffset(value)
    )


@dataclass(frozen=True)
class AURELIAIdentity:
    """AURELIA's internal session identity; never inferred from broker fields."""
    internal_uuid: str
    created_at: datetime
    system_version: str

    def validate(self) -> bool:
        if not isinstance(self.internal_uuid, str) or not self.internal_uuid.strip():
            return False
        try:
            UUID(self.internal_uuid)
        except (ValueError, TypeError, AttributeError):
            return False
        return (
            _identity_timestamp_valid(self.created_at)
            and isinstance(self.system_version, str)
            and bool(self.system_version.strip())
        )


@dataclass(frozen=True)
class DerivAccountIdentifier:
    """Modern Deriv Options account identity.

    account_id is the canonical modern Options identifier (for example
    DOT90004580). It is not a legacy CR/VR loginid and must never be relabelled
    as one. Legacy loginid is optional and retained in its own field only when
    an explicit provider source actually returns it.
    """
    account_id: str
    account_type: str
    status: str
    group: str
    currency: str
    balance: float
    legacy_loginid: str | None = None

    def validate(self) -> bool:
        if (
            not isinstance(self.account_id, str)
            or not self.account_id
            or not self.account_id.isascii()
            or not self.account_id.isalnum()
            or self.account_id != self.account_id.upper()
        ):
            return False
        if self.account_type not in {"real", "demo"}:
            return False
        if self.status not in {"active", "inactive"}:
            return False
        if not isinstance(self.group, str) or not self.group.strip():
            return False
        if (
            not isinstance(self.currency, str)
            or len(self.currency) != 3
            or not self.currency.isalpha()
            or self.currency != self.currency.upper()
        ):
            return False
        if isinstance(self.balance, bool) or not isinstance(self.balance, (int, float)):
            return False
        try:
            balance = float(self.balance)
        except (TypeError, ValueError, OverflowError):
            return False
        if not isfinite(balance) or balance < 0:
            return False
        if self.legacy_loginid is not None and (
            not isinstance(self.legacy_loginid, str)
            or not self.legacy_loginid.strip()
            or not self.legacy_loginid.isascii()
            or not self.legacy_loginid.isalnum()
            or self.legacy_loginid != self.legacy_loginid.upper()
        ):
            return False
        return True


@dataclass(frozen=True)
class BrokerReturnedUUID:
    """Optional external identity UUID; it is not an Options account_id.

    Deriv's modern Options account-list response does not contain this field.
    The separate identity endpoint requires account_manage, which AURELIA does
    not request in the trade-only OAuth flow. Absence is explicit.
    """
    broker_uuid: str | None
    broker_uuid_source: str
    broker_uuid_timestamp: datetime | None

    def validate(self) -> bool:
        if self.broker_uuid is None:
            return (
                self.broker_uuid_source == "not_returned"
                and self.broker_uuid_timestamp is None
            )
        if not isinstance(self.broker_uuid, str) or not self.broker_uuid.strip():
            return False
        try:
            UUID(self.broker_uuid)
        except (ValueError, TypeError, AttributeError):
            return False
        return (
            isinstance(self.broker_uuid_source, str)
            and bool(self.broker_uuid_source.strip())
            and _identity_timestamp_valid(self.broker_uuid_timestamp)
        )


@dataclass(frozen=True)
class LoginID:
    """Optional AURELIA user-facing login identifier, not Deriv account_id.

    Email addresses and email hashes are deliberately excluded. This value is
    only populated when supplied by AURELIA's authenticated identity provider.
    """
    login_id: str | None
    login_id_source: str

    def validate(self) -> bool:
        if self.login_id is None:
            return self.login_id_source == "not_returned"
        return (
            isinstance(self.login_id, str)
            and bool(self.login_id.strip())
            and isinstance(self.login_id_source, str)
            and bool(self.login_id_source.strip())
        )


@dataclass(frozen=True)
class AccountContext:
    product: str
    environment: str
    currency: str
    currency_validated_at: datetime

    def validate(self) -> bool:
        return (
            isinstance(self.product, str)
            and bool(self.product.strip())
            and self.environment in {"REAL", "DEMO"}
            and isinstance(self.currency, str)
            and len(self.currency) == 3
            and self.currency.isalpha()
            and self.currency.isupper()
            and _identity_timestamp_valid(self.currency_validated_at)
        )


@dataclass(frozen=True)
class CompositeAccountIdentity:
    """Composite identity with independently validated namespaces."""
    aurelia: AURELIAIdentity
    deriv_account: DerivAccountIdentifier
    broker_uuid: BrokerReturnedUUID
    login_id: LoginID
    context: AccountContext
    identity_checksum: str
    verified_at: datetime

    @staticmethod
    def _payload(
        aurelia: AURELIAIdentity,
        deriv_account: DerivAccountIdentifier,
        broker_uuid: BrokerReturnedUUID,
        login_id: LoginID,
        context: AccountContext,
        verified_at: datetime,
    ) -> str:
        data = {
            "verified_at": verified_at.isoformat(),
            "aurelia": {
                "internal_uuid": aurelia.internal_uuid,
                "created_at": aurelia.created_at.isoformat(),
                "system_version": aurelia.system_version,
            },
            "deriv_account": {
                "account_id": deriv_account.account_id,
                "account_type": deriv_account.account_type,
                "status": deriv_account.status,
                "group": deriv_account.group,
                "currency": deriv_account.currency,
                "balance": float(deriv_account.balance),
                "legacy_loginid": deriv_account.legacy_loginid,
            },
            "broker_uuid": {
                "broker_uuid": broker_uuid.broker_uuid,
                "source": broker_uuid.broker_uuid_source,
                "timestamp": (
                    broker_uuid.broker_uuid_timestamp.isoformat()
                    if broker_uuid.broker_uuid_timestamp is not None else None
                ),
            },
            "login_id": {
                "login_id": login_id.login_id,
                "source": login_id.login_id_source,
            },
            "context": {
                "product": context.product,
                "environment": context.environment,
                "currency": context.currency,
                "currency_validated_at": context.currency_validated_at.isoformat(),
            },
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def create(
        cls,
        aurelia: AURELIAIdentity,
        deriv_account: DerivAccountIdentifier,
        broker_uuid: BrokerReturnedUUID,
        login_id: LoginID,
        context: AccountContext,
    ) -> "CompositeAccountIdentity":
        components = (
            ("AURELIA", aurelia),
            ("DERIV_ACCOUNT", deriv_account),
            ("BROKER_UUID", broker_uuid),
            ("LOGIN_ID", login_id),
            ("ACCOUNT_CONTEXT", context),
        )
        for label, component in components:
            validator = getattr(component, "validate", None)
            if not callable(validator) or validator() is not True:
                raise ValueError(f"{label}_IDENTITY_VALIDATION_FAILED")
        expected_environment = (
            "REAL" if deriv_account.account_type == "real" else "DEMO"
        )
        if (
            context.environment != expected_environment
            or context.currency != deriv_account.currency
        ):
            raise ValueError("ACCOUNT_CONTEXT_MISMATCH")
        if deriv_account.status != "active":
            raise ValueError("DERIV_ACCOUNT_NOT_ACTIVE")

        verified_at = utc_now()
        payload = cls._payload(
            aurelia, deriv_account, broker_uuid, login_id, context, verified_at
        )
        checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return cls(
            aurelia=aurelia,
            deriv_account=deriv_account,
            broker_uuid=broker_uuid,
            login_id=login_id,
            context=context,
            identity_checksum=checksum,
            verified_at=verified_at,
        )

    def validate_integrity(self) -> bool:
        if not all(
            component.validate()
            for component in (
                self.aurelia,
                self.deriv_account,
                self.broker_uuid,
                self.login_id,
                self.context,
            )
        ):
            return False
        expected_environment = (
            "REAL" if self.deriv_account.account_type == "real" else "DEMO"
        )
        if (
            self.deriv_account.status != "active"
            or self.context.environment != expected_environment
            or self.context.currency != self.deriv_account.currency
        ):
            return False
        if not _identity_timestamp_valid(self.verified_at):
            return False
        if (
            not isinstance(self.identity_checksum, str)
            or len(self.identity_checksum) != 64
            or any(char not in "0123456789abcdef" for char in self.identity_checksum)
        ):
            return False
        payload = self._payload(
            self.aurelia,
            self.deriv_account,
            self.broker_uuid,
            self.login_id,
            self.context,
            self.verified_at,
        )
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return self.identity_checksum == expected
