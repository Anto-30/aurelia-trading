"""Typed, source-bound Deriv Options account identity.

These identifiers are separate:
- AURELIA internal UUID: locally configured system identity.
- Options account_id: GET /trading/v1/options/accounts.
- Broker UUID: id in the authenticated balance response.
- Login ID: loginid in the authenticated balance response.

SHA-256 detects payload drift; it does not authenticate a source.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

OPTIONS_ACCOUNTS_ENDPOINT = "https://api.derivws.com/trading/v1/options/accounts"
OPTIONS_WS_PREFIX = "wss://api.derivws.com/trading/v1/options/ws/"


class EnvironmentType(str, Enum):
    REAL = "real"
    DEMO = "demo"


class ProductType(str, Enum):
    OPTIONS = "OPTIONS"


def _utc_timestamp(value: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _is_uuid(value: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


@dataclass(frozen=True)
class AURELIAIdentity:
    internal_uuid: str
    source_config_key: str = "AURELIA_INTERNAL_ACCOUNT_UUID"

    def validate(self) -> bool:
        return _is_uuid(self.internal_uuid) and bool(self.source_config_key.strip())


@dataclass(frozen=True)
class DerivAccountIdentifier:
    account_id: str
    account_type: str
    status: str
    source_endpoint: str
    source_response_sha256: str
    observed_at_utc: str

    def validate(self) -> bool:
        return (
            isinstance(self.account_id, str)
            and 1 <= len(self.account_id.strip()) <= 128
            and self.account_type in {EnvironmentType.REAL.value, EnvironmentType.DEMO.value}
            and self.status == "active"
            and self.source_endpoint == OPTIONS_ACCOUNTS_ENDPOINT
            and _is_sha256(self.source_response_sha256)
            and _utc_timestamp(self.observed_at_utc)
        )


@dataclass(frozen=True)
class BrokerReturnedUUID:
    value: str
    source_method: str
    source_response_sha256: str
    observed_at_utc: str

    def validate(self) -> bool:
        return (
            _is_uuid(self.value)
            and self.source_method == "balance"
            and _is_sha256(self.source_response_sha256)
            and _utc_timestamp(self.observed_at_utc)
        )


@dataclass(frozen=True)
class LoginID:
    value: str
    source_method: str
    observed_at_utc: str

    def validate(self) -> bool:
        return (
            isinstance(self.value, str)
            and 1 <= len(self.value.strip()) <= 128
            and self.source_method == "balance"
            and _utc_timestamp(self.observed_at_utc)
        )


@dataclass(frozen=True)
class AccountContext:
    product: ProductType
    environment: EnvironmentType
    currency: str
    account_list_currency: str
    balance_currency: str
    account_status: str
    product_source_endpoint: str
    environment_source_endpoint: str
    currency_verified_at_utc: str

    def validate(self) -> bool:
        parsed = urlsplit(self.environment_source_endpoint)
        return (
            self.product is ProductType.OPTIONS
            and self.environment in {EnvironmentType.REAL, EnvironmentType.DEMO}
            and isinstance(self.currency, str)
            and re.fullmatch(r"[A-Z]{3}", self.currency) is not None
            and self.account_list_currency == self.currency
            and self.balance_currency == self.currency
            and self.account_status == "active"
            and self.product_source_endpoint == OPTIONS_ACCOUNTS_ENDPOINT
            and parsed.scheme == "wss"
            and parsed.netloc == "api.derivws.com"
            and parsed.path == f"/trading/v1/options/ws/{self.environment.value}"
            and not parsed.query
            and _utc_timestamp(self.currency_verified_at_utc)
        )


@dataclass(frozen=True)
class CompositeAccountIdentity:
    aurelia: AURELIAIdentity
    deriv_account: DerivAccountIdentifier
    broker_uuid: BrokerReturnedUUID
    login_id: LoginID
    context: AccountContext
    identity_checksum: str
    verified_at_utc: str

    @classmethod
    def create(
        cls,
        *,
        aurelia: AURELIAIdentity,
        deriv_account: DerivAccountIdentifier,
        broker_uuid: BrokerReturnedUUID,
        login_id: LoginID,
        context: AccountContext,
        verified_at_utc: str | None = None,
    ) -> "CompositeAccountIdentity":
        components = (aurelia, deriv_account, broker_uuid, login_id, context)
        if not all(component.validate() for component in components):
            raise ValueError("ACCOUNT_IDENTITY_COMPONENT_INVALID")
        if deriv_account.account_id != login_id.value:
            raise ValueError("DERIV_ACCOUNT_ID_LOGINID_MISMATCH")
        if deriv_account.account_type != context.environment.value:
            raise ValueError("DERIV_ACCOUNT_ENVIRONMENT_MISMATCH")
        if deriv_account.status != context.account_status:
            raise ValueError("DERIV_ACCOUNT_STATUS_MISMATCH")
        verified = verified_at_utc or datetime.now(timezone.utc).isoformat()
        if not _utc_timestamp(verified):
            raise ValueError("ACCOUNT_IDENTITY_VERIFICATION_TIMESTAMP_INVALID")
        provisional = cls(
            aurelia, deriv_account, broker_uuid, login_id, context, "", verified
        )
        return cls(
            aurelia, deriv_account, broker_uuid, login_id, context,
            _sha256(provisional._checksum_payload()), verified,
        )

    def _checksum_payload(self) -> dict[str, Any]:
        return {
            "aurelia_internal_uuid": self.aurelia.internal_uuid,
            "deriv_account_id": self.deriv_account.account_id,
            "deriv_account_type": self.deriv_account.account_type,
            "deriv_account_status": self.deriv_account.status,
            "deriv_account_response_sha256": self.deriv_account.source_response_sha256,
            "broker_uuid": self.broker_uuid.value,
            "broker_uuid_response_sha256": self.broker_uuid.source_response_sha256,
            "login_id": self.login_id.value,
            "product": self.context.product.value,
            "environment": self.context.environment.value,
            "currency": self.context.currency,
            "account_list_currency": self.context.account_list_currency,
            "balance_currency": self.context.balance_currency,
            "account_status": self.context.account_status,
            "environment_source_endpoint": self.context.environment_source_endpoint,
        }

    def validate_integrity(self) -> bool:
        components = (
            self.aurelia, self.deriv_account, self.broker_uuid,
            self.login_id, self.context,
        )
        if not all(component.validate() for component in components):
            return False
        if self.deriv_account.account_id != self.login_id.value:
            return False
        if self.deriv_account.account_type != self.context.environment.value:
            return False
        if self.deriv_account.status != self.context.account_status:
            return False
        if not _utc_timestamp(self.verified_at_utc):
            return False
        return self.identity_checksum == _sha256(self._checksum_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            "aurelia": {
                "internal_uuid": self.aurelia.internal_uuid,
                "source_config_key": self.aurelia.source_config_key,
            },
            "deriv_account": {
                "account_id": self.deriv_account.account_id,
                "account_type": self.deriv_account.account_type,
                "status": self.deriv_account.status,
                "source_endpoint": self.deriv_account.source_endpoint,
                "source_response_sha256": self.deriv_account.source_response_sha256,
                "observed_at_utc": self.deriv_account.observed_at_utc,
            },
            "broker_uuid": {
                "value": self.broker_uuid.value,
                "source_method": self.broker_uuid.source_method,
                "source_response_sha256": self.broker_uuid.source_response_sha256,
                "observed_at_utc": self.broker_uuid.observed_at_utc,
            },
            "login_id": {
                "value": self.login_id.value,
                "source_method": self.login_id.source_method,
                "observed_at_utc": self.login_id.observed_at_utc,
            },
            "context": {
                "product": self.context.product.value,
                "environment": self.context.environment.value,
                "currency": self.context.currency,
                "account_list_currency": self.context.account_list_currency,
                "balance_currency": self.context.balance_currency,
                "account_status": self.context.account_status,
                "product_source_endpoint": self.context.product_source_endpoint,
                "environment_source_endpoint": self.context.environment_source_endpoint,
                "currency_verified_at_utc": self.context.currency_verified_at_utc,
            },
            "identity_checksum": self.identity_checksum,
            "verified_at_utc": self.verified_at_utc,
            "checksum_is_authentication": False,
        }
