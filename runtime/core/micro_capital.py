from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any


FIXED_MICRO_STAKE_USD = Decimal("0.35")


@dataclass(frozen=True)
class MicroStakeDecision:
    allowed: bool
    stake: Decimal | None
    loss_fraction: Decimal | None
    reason_codes: tuple[str, ...]


def evaluate_micro_capital_stake(
    *,
    available_balance: Any,
    currency: str,
    account_verified: bool,
    balance_fresh: bool,
    exact_contract_quote_verified: bool,
    quoted_stake: Any,
    quoted_max_loss: Any,
    one_open_contract_or_less: bool,
    session_loss_usd: Any,
    transaction_state_reconciled: bool,
    strategy_qualified: bool,
    probability: Any,
    probability_calibrated: bool,
    probability_fresh: bool,
    probability_drift_ok: bool,
    net_economics_positive: bool,
    kill_switch_clear: bool,
    canonical_release_gate_passed: bool,
) -> MicroStakeDecision:
    """Fail-closed decision helper for the separately governed $0.35 micro mode.

    This helper is a policy pre-check, not a live-authority decision. The caller
    must obtain source-bound broker evidence and pass the canonical release gate.
    `canonical_release_gate_passed` must mean the independently evaluated gate
    passed; it must never be populated from the raw LIVE_LOCK enabled/disabled
    flag. Until integrated and reviewed, this helper must not be used to submit orders.
    """
    reasons: list[str] = []

    def decimal_value(value: Any) -> Decimal | None:
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
            return None
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
        return result if result.is_finite() else None

    balance = decimal_value(available_balance)
    quote = decimal_value(quoted_stake)
    max_loss = decimal_value(quoted_max_loss)
    session_loss = decimal_value(session_loss_usd)
    prob = decimal_value(probability)

    if balance is None or balance <= 0:
        reasons.append("BALANCE_INVALID")
    if str(currency or "").strip().upper() != "USD":
        reasons.append("CURRENCY_MISMATCH")
    if account_verified is not True:
        reasons.append("ACCOUNT_UNVERIFIED")
    if balance_fresh is not True:
        reasons.append("BALANCE_STALE")
    if exact_contract_quote_verified is not True:
        reasons.append("EXACT_CONTRACT_QUOTE_UNVERIFIED")
    if quote is None or quote != FIXED_MICRO_STAKE_USD:
        reasons.append("QUOTED_STAKE_NOT_EXACTLY_USD_0_35")
    if max_loss is None or max_loss <= 0 or max_loss > FIXED_MICRO_STAKE_USD:
        reasons.append("CONTRACT_MAX_LOSS_INVALID_OR_OVER_LIMIT")
    if balance is not None and quote is not None and balance < quote:
        reasons.append("STAKE_UNAFFORDABLE")
    if one_open_contract_or_less is not True:
        reasons.append("OPEN_CONTRACT_LIMIT_EXCEEDED")
    if session_loss is None or session_loss < 0:
        reasons.append("SESSION_LOSS_INVALID")
    elif (
        session_loss >= FIXED_MICRO_STAKE_USD
        or session_loss + (max_loss if max_loss is not None else FIXED_MICRO_STAKE_USD)
        > FIXED_MICRO_STAKE_USD
    ):
        # Reaching the cap blocks immediately, even if the next contract's
        # quoted maximum loss is zero or malformed.
        reasons.append("MICRO_SESSION_LOSS_LIMIT_REACHED")
    if transaction_state_reconciled is not True:
        reasons.append("TRANSACTION_RECONCILIATION_REQUIRED")
    if strategy_qualified is not True:
        reasons.append("STRATEGY_NOT_QUALIFIED")
    if prob is None or not Decimal("0.55") <= prob <= Decimal("0.75"):
        reasons.append("PROBABILITY_OUTSIDE_HARD_POLICY")
    if probability_calibrated is not True:
        reasons.append("PROBABILITY_NOT_CALIBRATED")
    if probability_fresh is not True:
        reasons.append("PROBABILITY_NOT_FRESH")
    if probability_drift_ok is not True:
        reasons.append("PROBABILITY_DRIFT_DETECTED_OR_UNVERIFIED")
    if net_economics_positive is not True:
        reasons.append("NET_ECONOMICS_NOT_POSITIVE")
    if kill_switch_clear is not True:
        reasons.append("KILL_SWITCH_ACTIVE")
    if canonical_release_gate_passed is not True:
        reasons.append("LIVE_RELEASE_GATE_BLOCKED")

    if reasons:
        loss_fraction = None
        if balance is not None and balance > 0 and max_loss is not None and max_loss >= 0:
            loss_fraction = max_loss / balance
        return MicroStakeDecision(False, None, loss_fraction, tuple(dict.fromkeys(reasons)))

    assert balance is not None and max_loss is not None
    return MicroStakeDecision(
        True,
        FIXED_MICRO_STAKE_USD,
        max_loss / balance,
        ("MICRO_STAKE_POLICY_PASSED_RELEASE_GATE_STILL_REQUIRED",),
    )
