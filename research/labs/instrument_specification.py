"""Versioned instrument/contract metadata with fail-closed qualification.

This is a research-plane schema, not a source of fabricated instrument facts.
A specification cannot qualify until its values are backed by a current source
for the exact provider, account type, instrument and contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Literal, Mapping

InstrumentCategory = Literal[
    "DERIV_SYNTHETIC_INDEX",
    "DERIV_FOREX",
    "DERIV_FIXED_PAYOUT",
    "DERIV_MULTIPLIER",
    "EXCHANGE_TRADED",
]

SUPPORTED_CATEGORIES = frozenset({
    "DERIV_SYNTHETIC_INDEX",
    "DERIV_FOREX",
    "DERIV_FIXED_PAYOUT",
    "DERIV_MULTIPLIER",
    "EXCHANGE_TRADED",
})


def _parse_aware_utc(value: str) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        return None
    return stamp.astimezone(timezone.utc)


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _positive_finite(value: float | None) -> bool:
    return value is not None and isfinite(float(value)) and float(value) > 0


def _nonnegative_finite(value: float | None) -> bool:
    return value is not None and isfinite(float(value)) and float(value) >= 0


@dataclass(frozen=True)
class InstrumentSpecification:
    instrument_id: str
    category: InstrumentCategory
    specification_version: str
    provider: str
    account_type: str
    source_uri: str
    verified: bool
    observed_at_utc: str

    # Contract mechanics. None means unknown, not zero or "not applicable".
    price_precision: int | None
    tick_size_applicable: bool
    tick_size: float | None
    minimum_stake_or_order_size: float | None
    size_increment: float | None
    contract_multiplier: float | None
    payoff_model: str | None
    trading_hours: str | None
    trading_hours_timezone: str | None
    settlement_rules: str | None
    supported_order_types: tuple[str, ...]

    # Execution mechanics and protection. Unknown support is not false.
    order_book_model: bool
    spread_model: str | None
    slippage_model: str | None
    commission_model: str | None
    financing_model: str | None
    native_stop_supported: bool | None
    native_oco_supported: bool | None
    partial_fills_supported: bool | None

    # These fields apply only to verified order-book products.
    maker_fee_bps: float | None = None
    taker_fee_bps: float | None = None

    maximum_age_seconds: float = 86400.0

    def validation_errors(
        self,
        *,
        now: datetime | None = None,
        require_verified: bool = True,
    ) -> tuple[str, ...]:
        errors: list[str] = []
        if not _nonempty(self.instrument_id):
            errors.append("INSTRUMENT_ID_MISSING")
        if self.category not in SUPPORTED_CATEGORIES:
            errors.append("INSTRUMENT_CATEGORY_UNSUPPORTED_OR_UNKNOWN")
        if not _nonempty(self.specification_version):
            errors.append("SPECIFICATION_VERSION_MISSING")
        for field_name, value in (
            ("provider", self.provider),
            ("account_type", self.account_type),
            ("source_uri", self.source_uri),
        ):
            if not _nonempty(value):
                errors.append(f"SPECIFICATION_{field_name.upper()}_MISSING")
        if require_verified and self.verified is not True:
            errors.append("INSTRUMENT_SPECIFICATION_UNVERIFIED")

        if isinstance(self.price_precision, bool) or not isinstance(self.price_precision, int) or self.price_precision < 0:
            errors.append("PRICE_PRECISION_UNKNOWN_OR_INVALID")
        if not isinstance(self.tick_size_applicable, bool):
            errors.append("TICK_SIZE_APPLICABILITY_UNKNOWN")
        elif self.tick_size_applicable and not _positive_finite(self.tick_size):
            errors.append("TICK_SIZE_UNKNOWN_OR_INVALID")
        elif not self.tick_size_applicable and self.tick_size is not None:
            errors.append("TICK_SIZE_PRESENT_BUT_MARKED_NOT_APPLICABLE")

        if not _positive_finite(self.minimum_stake_or_order_size):
            errors.append("MINIMUM_STAKE_OR_ORDER_SIZE_UNKNOWN_OR_INVALID")
        if not _positive_finite(self.size_increment):
            errors.append("SIZE_INCREMENT_UNKNOWN_OR_INVALID")
        if not _positive_finite(self.contract_multiplier):
            errors.append("CONTRACT_MULTIPLIER_UNKNOWN_OR_INVALID")

        for name, value in (
            ("payoff_model", self.payoff_model),
            ("trading_hours", self.trading_hours),
            ("trading_hours_timezone", self.trading_hours_timezone),
            ("settlement_rules", self.settlement_rules),
            ("spread_model", self.spread_model),
            ("slippage_model", self.slippage_model),
            ("commission_model", self.commission_model),
            ("financing_model", self.financing_model),
        ):
            if not _nonempty(value):
                errors.append(f"{name.upper()}_UNKNOWN")

        if not self.supported_order_types or any(not _nonempty(x) for x in self.supported_order_types):
            errors.append("SUPPORTED_ORDER_TYPES_UNKNOWN")
        if len(set(self.supported_order_types)) != len(self.supported_order_types):
            errors.append("SUPPORTED_ORDER_TYPES_DUPLICATED")

        if not isinstance(self.order_book_model, bool):
            errors.append("ORDER_BOOK_MODEL_UNKNOWN")
        elif self.order_book_model:
            if not _nonnegative_finite(self.maker_fee_bps):
                errors.append("ORDER_BOOK_MAKER_FEE_UNKNOWN_OR_INVALID")
            if not _nonnegative_finite(self.taker_fee_bps):
                errors.append("ORDER_BOOK_TAKER_FEE_UNKNOWN_OR_INVALID")
        else:
            if self.maker_fee_bps is not None or self.taker_fee_bps is not None:
                errors.append("MAKER_TAKER_FEES_NOT_APPLICABLE_TO_THIS_MODEL")

        if self.native_stop_supported is None:
            errors.append("NATIVE_STOP_SUPPORT_UNKNOWN")
        if self.native_oco_supported is None:
            errors.append("NATIVE_OCO_SUPPORT_UNKNOWN")
        if self.partial_fills_supported is None:
            errors.append("PARTIAL_FILL_SUPPORT_UNKNOWN")

        if not _nonnegative_finite(self.maximum_age_seconds) or self.maximum_age_seconds <= 0:
            errors.append("SPECIFICATION_MAXIMUM_AGE_INVALID")
        observed = _parse_aware_utc(self.observed_at_utc)
        if observed is None:
            errors.append("SPECIFICATION_TIMESTAMP_INVALID")
        else:
            reference = now or datetime.now(timezone.utc)
            if reference.tzinfo is None:
                errors.append("VALIDATION_TIME_MUST_BE_TIMEZONE_AWARE")
            else:
                age = (reference.astimezone(timezone.utc) - observed).total_seconds()
                if age < 0:
                    errors.append("SPECIFICATION_TIMESTAMP_IN_FUTURE")
                elif age > self.maximum_age_seconds:
                    errors.append("INSTRUMENT_SPECIFICATION_STALE")
        return tuple(errors)

    def qualifies(self, *, now: datetime | None = None) -> bool:
        return not self.validation_errors(now=now)

    def qualification_report(self, *, now: datetime | None = None) -> dict[str, object]:
        errors = self.validation_errors(now=now)
        return {
            "instrument_id": self.instrument_id,
            "category": self.category,
            "specification_version": self.specification_version,
            "verified": self.verified,
            "status": "PASS" if not errors else "BLOCKED",
            "reasons": list(errors),
            "source_uri": self.source_uri,
            "observed_at_utc": self.observed_at_utc,
        }


class InstrumentSpecificationRegistry:
    """Immutable identity map; it never infers absent specification fields."""

    def __init__(self, specifications: Mapping[str, InstrumentSpecification]):
        self._specifications = dict(specifications)
        for key, spec in self._specifications.items():
            if key != spec.instrument_id:
                raise ValueError("INSTRUMENT_REGISTRY_KEY_MISMATCH")
        if len(self._specifications) != len(specifications):
            raise ValueError("INSTRUMENT_REGISTRY_DUPLICATE_ID")

    def get(self, instrument_id: str) -> InstrumentSpecification | None:
        return self._specifications.get(instrument_id)

    def qualify(self, instrument_id: str, *, now: datetime | None = None) -> dict[str, object]:
        spec = self.get(instrument_id)
        if spec is None:
            return {
                "instrument_id": instrument_id,
                "status": "BLOCKED",
                "reasons": ["INSTRUMENT_SPECIFICATION_NOT_REGISTERED"],
            }
        return spec.qualification_report(now=now)

    def instrument_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._specifications))
