from __future__ import annotations

"""Research-only Deriv Multipliers economics.

Converts intended underlying-price stop/target levels into estimated contract
P/L using Deriv's published percentage-price-move × multiplier × stake less
opening commission formula. It does not call Deriv, build an order payload,
or authorize execution. Inputs must be normalized from fresh account-specific
broker responses by a separately reviewed evidence adapter.

Deriv's contract_update limit_order inputs are monetary P/L amounts, not
underlying price levels. Any future integration must compare the broker's
returned mapped price values with the desired stop and target before use.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import re
from typing import Any

ZERO = Decimal("0")
ONE = Decimal("1")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SUPPORTED_TYPES = {"MULTUP", "MULTDOWN"}


class MultiplierEconomicsError(ValueError):
    """Invalid normalized quote or price input."""


def _decimal(value: Any, reason: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise MultiplierEconomicsError(reason)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MultiplierEconomicsError(reason) from exc
    if not parsed.is_finite():
        raise MultiplierEconomicsError(reason)
    return parsed


def multiplier_opening_commission(
    *,
    stake: str | Decimal,
    multiplier: str | Decimal,
    commission_rate_percent: str | Decimal,
    minimum_commission: str | Decimal,
) -> Decimal:
    """Normalize Deriv's quoted percentage into an opening fee in account currency.

    The percentage applies to notional (stake × multiplier). The minimum
    commission is an explicit broker/jurisdiction input; it is never guessed.
    """
    stake_value = _decimal(stake, "STAKE_INVALID")
    multiplier_value = _decimal(multiplier, "MULTIPLIER_INVALID")
    rate_pct = _decimal(commission_rate_percent, "COMMISSION_RATE_PERCENT_INVALID")
    minimum = _decimal(minimum_commission, "MINIMUM_COMMISSION_INVALID")
    if stake_value <= ZERO or multiplier_value <= ZERO:
        raise MultiplierEconomicsError("STAKE_AND_MULTIPLIER_MUST_BE_POSITIVE")
    if rate_pct < ZERO or minimum < ZERO:
        raise MultiplierEconomicsError("COMMISSION_INPUTS_MUST_NOT_BE_NEGATIVE")
    with localcontext() as context:
        context.prec = 36
        notional = stake_value * multiplier_value
        percentage_fee = notional * rate_pct / Decimal("100")
        return max(percentage_fee, minimum)


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise MultiplierEconomicsError("QUOTE_TIMESTAMP_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MultiplierEconomicsError("QUOTE_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MultiplierEconomicsError("QUOTE_TIMESTAMP_INVALID")
    return parsed.astimezone(timezone.utc)


def _check_hash(value: str, reason: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise MultiplierEconomicsError(reason)


@dataclass(frozen=True)
class ObservedMultiplierQuote:
    """One normalized, timestamped catalogue/proposal observation.

    minimum_stake and price_increment must be derived from target-product
    evidence, not generic marketing figures or MT5 specifications.
    commission is the normalized opening fee in account currency, not the
    raw percentage returned by the proposal endpoint. Use
    multiplier_opening_commission() with the observed commission percentage
    and a verified account/jurisdiction minimum before constructing this row.
    SHA-256 values bind captured payloads but do not authenticate their origin.
    """

    symbol: str
    contract_type: str
    currency: str
    proposal_id: str
    stake: str
    multiplier: str
    entry_spot: str
    commission: str
    minimum_stake: str | None
    price_increment: str | None
    observed_at_utc: str
    catalogue_sha256: str
    proposal_sha256: str


@dataclass(frozen=True)
class MultiplierEconomicsResult:
    model_valid: bool
    risk_gate_passed: bool
    executable: bool
    symbol: str
    contract_type: str
    currency: str
    stake: str | None
    multiplier: str | None
    entry_spot: str | None
    stop_price: str | None
    target_price: str | None
    commission: str | None
    stop_loss_order_amount_estimate: str | None
    take_profit_order_amount_estimate: str | None
    gross_stop_pnl: str | None
    net_stop_pnl: str | None
    gross_target_pnl: str | None
    net_target_pnl: str | None
    risk_at_stop: str | None
    risk_budget: str | None
    commission_as_fraction_of_risk: str | None
    net_reward_risk: str | None
    blockers: tuple[str, ...]
    evidence_grade: str = "NORMALIZED_INPUTS_UNAUTHENTICATED_BY_THIS_MODULE"


def _pnl_at_price(
    *,
    contract_type: str,
    stake: Decimal,
    multiplier: Decimal,
    entry_spot: Decimal,
    exit_price: Decimal,
    commission: Decimal,
) -> tuple[Decimal, Decimal]:
    if entry_spot <= ZERO or exit_price <= ZERO:
        raise MultiplierEconomicsError("PRICE_MUST_BE_POSITIVE")
    directional_move = (exit_price - entry_spot) / entry_spot
    if contract_type == "MULTDOWN":
        directional_move = -directional_move
    gross = directional_move * multiplier * stake
    net = gross - commission
    # Published product information caps losses at the initial stake.
    if net < -stake:
        net = -stake
    return gross, net


def _failed_result(reason: str, symbol: str = "", contract_type: str = "", currency: str = "") -> MultiplierEconomicsResult:
    return MultiplierEconomicsResult(
        model_valid=False,
        risk_gate_passed=False,
        executable=False,
        symbol=symbol,
        contract_type=contract_type,
        currency=currency,
        stake=None,
        multiplier=None,
        entry_spot=None,
        stop_price=None,
        target_price=None,
        commission=None,
        stop_loss_order_amount_estimate=None,
        take_profit_order_amount_estimate=None,
        gross_stop_pnl=None,
        net_stop_pnl=None,
        gross_target_pnl=None,
        net_target_pnl=None,
        risk_at_stop=None,
        risk_budget=None,
        commission_as_fraction_of_risk=None,
        net_reward_risk=None,
        blockers=(reason,),
    )


def evaluate_multiplier_economics(
    quote: ObservedMultiplierQuote,
    *,
    stop_price: str,
    target_price: str,
    account_equity: str,
    available_balance: str,
    account_currency: str,
    account_captured_at_utc: str,
    account_snapshot_sha256: str,
    account_reference_sha256: str,
    stop_execution_price: str,
    target_execution_price: str,
    slippage_evidence_sha256: str,
    broker_stop_loss_mapped_price: str,
    broker_take_profit_mapped_price: str,
    broker_mapping_sha256: str,
    risk_fraction: str = "0.01",
    minimum_net_reward_risk: str = "3.0",
    maximum_quote_age_seconds: int = 30,
    maximum_account_age_seconds: int = 15,
    as_of_utc: datetime | None = None,
) -> MultiplierEconomicsResult:
    """Calculate Multipliers economics; never authorizes or submits a trade.

    The risk check deliberately requires a fresh, currency-matched account
    snapshot, fresh proposal evidence, measured adverse stop/target execution
    prices, and broker-returned contract-update prices within one verified
    instrument increment of the intended levels. The mapping hash identifies
    captured evidence; this function does not authenticate that artifact.
    It requires stake + opening commission to fit within both the selected
    risk budget and available balance. This function still never authorizes
    or constructs an executable order.
    """
    if not isinstance(quote, ObservedMultiplierQuote):
        return _failed_result("NORMALIZED_QUOTE_REQUIRED")

    symbol = str(quote.symbol or "")
    contract_type = str(quote.contract_type or "").upper()
    currency = str(quote.currency or "").upper()
    blockers: list[str] = []

    try:
        if not re.fullmatch(r"[A-Z0-9_]{2,30}", symbol):
            raise MultiplierEconomicsError("SYMBOL_INVALID")
        if contract_type not in SUPPORTED_TYPES:
            raise MultiplierEconomicsError("CONTRACT_TYPE_NOT_MULTIPLIER")
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise MultiplierEconomicsError("CURRENCY_INVALID")
        if not isinstance(quote.proposal_id, str) or not quote.proposal_id.strip():
            raise MultiplierEconomicsError("PROPOSAL_ID_MISSING")
        _check_hash(quote.catalogue_sha256, "CATALOGUE_EVIDENCE_HASH_INVALID")
        _check_hash(quote.proposal_sha256, "PROPOSAL_EVIDENCE_HASH_INVALID")
        observed = _timestamp(quote.observed_at_utc)
        if (
            isinstance(maximum_quote_age_seconds, bool)
            or not isinstance(maximum_quote_age_seconds, int)
            or maximum_quote_age_seconds <= 0
        ):
            raise MultiplierEconomicsError("MAXIMUM_QUOTE_AGE_INVALID")
        if (
            isinstance(maximum_account_age_seconds, bool)
            or not isinstance(maximum_account_age_seconds, int)
            or maximum_account_age_seconds <= 0
        ):
            raise MultiplierEconomicsError("MAXIMUM_ACCOUNT_AGE_INVALID")
        now = as_of_utc or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise MultiplierEconomicsError("AS_OF_TIMESTAMP_MUST_BE_AWARE")
        now_utc = now.astimezone(timezone.utc)
        quote_age = (now_utc - observed).total_seconds()
        if quote_age < 0 or quote_age > maximum_quote_age_seconds:
            blockers.append("QUOTE_STALE_OR_FROM_FUTURE")
        account_observed = _timestamp(account_captured_at_utc)
        account_age = (now_utc - account_observed).total_seconds()
        if account_age < 0 or account_age > maximum_account_age_seconds:
            blockers.append("ACCOUNT_CAPITAL_SNAPSHOT_STALE_OR_FROM_FUTURE")
        _check_hash(account_snapshot_sha256, "ACCOUNT_SNAPSHOT_HASH_INVALID")
        _check_hash(account_reference_sha256, "ACCOUNT_REFERENCE_HASH_INVALID")
        _check_hash(slippage_evidence_sha256, "SLIPPAGE_EVIDENCE_HASH_INVALID")
        if not isinstance(account_currency, str) or not re.fullmatch(
            r"[A-Z]{3}", account_currency.upper()
        ):
            raise MultiplierEconomicsError("ACCOUNT_CURRENCY_INVALID")
        if account_currency.upper() != currency:
            blockers.append("ACCOUNT_AND_CONTRACT_CURRENCY_MISMATCH")
        _check_hash(
            broker_mapping_sha256,
            "BROKER_MAPPING_EVIDENCE_HASH_INVALID",
        )

        stake = _decimal(quote.stake, "STAKE_INVALID")
        multiplier = _decimal(quote.multiplier, "MULTIPLIER_INVALID")
        entry = _decimal(quote.entry_spot, "ENTRY_SPOT_INVALID")
        commission = _decimal(quote.commission, "OPENING_COMMISSION_INVALID")
        minimum_stake = (
            _decimal(quote.minimum_stake, "MINIMUM_STAKE_INVALID")
            if quote.minimum_stake is not None else None
        )
        price_increment = (
            _decimal(quote.price_increment, "PRICE_INCREMENT_INVALID")
            if quote.price_increment is not None else None
        )
        broker_stop_mapped = _decimal(
            broker_stop_loss_mapped_price, "BROKER_STOP_MAPPED_PRICE_INVALID"
        )
        broker_target_mapped = _decimal(
            broker_take_profit_mapped_price, "BROKER_TARGET_MAPPED_PRICE_INVALID"
        )
        stop = _decimal(stop_price, "STOP_PRICE_INVALID")
        target = _decimal(target_price, "TARGET_PRICE_INVALID")
        stop_execution = _decimal(
            stop_execution_price, "STOP_EXECUTION_PRICE_INVALID"
        )
        target_execution = _decimal(
            target_execution_price, "TARGET_EXECUTION_PRICE_INVALID"
        )
        equity = _decimal(account_equity, "ACCOUNT_EQUITY_INVALID")
        available = _decimal(available_balance, "AVAILABLE_BALANCE_INVALID")
        risk_pct = _decimal(risk_fraction, "RISK_FRACTION_INVALID")
        minimum_rr = _decimal(minimum_net_reward_risk, "MINIMUM_RR_INVALID")

        if stake <= ZERO or multiplier <= ZERO or entry <= ZERO:
            raise MultiplierEconomicsError("STAKE_MULTIPLIER_AND_ENTRY_MUST_BE_POSITIVE")
        if commission < ZERO:
            raise MultiplierEconomicsError("OPENING_COMMISSION_NEGATIVE")
        if minimum_stake is None or minimum_stake <= ZERO:
            blockers.append("MINIMUM_STAKE_NOT_VERIFIED_FROM_ACCOUNT_PRODUCT")
        elif stake < minimum_stake:
            blockers.append("STAKE_BELOW_VERIFIED_PRODUCT_MINIMUM")
        if price_increment is None or price_increment <= ZERO:
            blockers.append("PRICE_INCREMENT_NOT_VERIFIED_FROM_LIVE_INSTRUMENT")
        elif any(
            (price / price_increment) != (price / price_increment).to_integral_value()
            for price in (
                entry, stop, target, stop_execution, target_execution,
                broker_stop_mapped, broker_target_mapped,
            )
        ):
            blockers.append("PRICE_LEVEL_NOT_ALIGNED_TO_VERIFIED_INCREMENT")
        else:
            if abs(broker_stop_mapped - stop) > price_increment:
                blockers.append("BROKER_STOP_MAPPING_OUTSIDE_ONE_TICK_TOLERANCE")
            if abs(broker_target_mapped - target) > price_increment:
                blockers.append("BROKER_TAKE_PROFIT_MAPPING_OUTSIDE_ONE_TICK_TOLERANCE")
        if equity <= ZERO or available < ZERO or available > equity:
            raise MultiplierEconomicsError("ACCOUNT_CAPITAL_INVALID")
        if not ZERO < risk_pct <= Decimal("0.02"):
            raise MultiplierEconomicsError("RISK_FRACTION_OUTSIDE_HARD_CEILING")
        if minimum_rr < ONE:
            raise MultiplierEconomicsError("MINIMUM_RR_INVALID")
        if contract_type == "MULTUP" and not (stop < entry < target):
            raise MultiplierEconomicsError("MULTUP_PRICE_LEVELS_INVALID")
        if contract_type == "MULTDOWN" and not (target < entry < stop):
            raise MultiplierEconomicsError("MULTDOWN_PRICE_LEVELS_INVALID")
        if contract_type == "MULTUP" and not (
            stop_execution <= stop and entry < target_execution <= target
        ):
            blockers.append("MULTUP_SLIPPAGE_INPUT_NOT_ADVERSE_CONSERVATIVE")
        if contract_type == "MULTDOWN" and not (
            stop_execution >= stop and target <= target_execution < entry
        ):
            blockers.append("MULTDOWN_SLIPPAGE_INPUT_NOT_ADVERSE_CONSERVATIVE")

        with localcontext() as context:
            context.prec = 36
            gross_stop, net_stop = _pnl_at_price(
                contract_type=contract_type,
                stake=stake,
                multiplier=multiplier,
                entry_spot=entry,
                exit_price=stop_execution,
                commission=commission,
            )
            gross_target, net_target = _pnl_at_price(
                contract_type=contract_type,
                stake=stake,
                multiplier=multiplier,
                entry_spot=entry,
                exit_price=target_execution,
                commission=commission,
            )
            if net_stop >= ZERO:
                blockers.append("STOP_DOES_NOT_PRODUCE_NET_LOSS")
            risk_at_stop = -net_stop
            if risk_at_stop <= ZERO:
                blockers.append("STOP_RISK_NOT_POSITIVE")
            if risk_at_stop >= stake:
                blockers.append("STOP_AT_OR_BEYOND_STAKE_STOP_OUT_CAP")
            if net_target <= ZERO:
                blockers.append("TARGET_DOES_NOT_PRODUCE_NET_PROFIT")
            risk_budget = equity * risk_pct
            initial_debit = stake + commission
            if initial_debit > risk_budget:
                blockers.append("STAKE_PLUS_COMMISSION_EXCEEDS_RISK_BUDGET")
            if initial_debit > available:
                blockers.append("STAKE_PLUS_COMMISSION_EXCEEDS_AVAILABLE_BALANCE")
            net_rr = net_target / risk_at_stop if risk_at_stop > ZERO else ZERO
            if risk_at_stop > ZERO and net_rr < minimum_rr:
                blockers.append("NET_REWARD_RISK_BELOW_REQUIRED_MINIMUM")
            commission_fraction = commission / risk_at_stop if risk_at_stop > ZERO else ZERO

        return MultiplierEconomicsResult(
            model_valid=True,
            risk_gate_passed=not blockers,
            executable=False,
            symbol=symbol,
            contract_type=contract_type,
            currency=currency,
            stake=str(stake),
            multiplier=str(multiplier),
            entry_spot=str(entry),
            stop_price=str(stop),
            target_price=str(target),
            commission=str(commission),
            stop_loss_order_amount_estimate=str(risk_at_stop),
            take_profit_order_amount_estimate=str(net_target),
            gross_stop_pnl=str(gross_stop),
            net_stop_pnl=str(net_stop),
            gross_target_pnl=str(gross_target),
            net_target_pnl=str(net_target),
            risk_at_stop=str(risk_at_stop),
            risk_budget=str(risk_budget),
            commission_as_fraction_of_risk=str(commission_fraction),
            net_reward_risk=str(net_rr),
            blockers=tuple(dict.fromkeys(blockers)),
        )
    except MultiplierEconomicsError as exc:
        return _failed_result(str(exc), symbol, contract_type, currency)
