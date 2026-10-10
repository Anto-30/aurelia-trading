from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP
from math import isfinite
from typing import Any

DEFAULT_MAX_TRADE_RISK_FRACTION = 0.01
DEFAULT_MINIMUM_STAKE = 1.00
_CENT = Decimal("0.01")


@dataclass(frozen=True)
class StakeSizingResult:
    allowed: bool
    stake: float | None
    risk_budget: float | None
    reason: str


def size_stake_for_balance(
    verified_available_balance: Any,
    *,
    maximum_risk_fraction: float = DEFAULT_MAX_TRADE_RISK_FRACTION,
    minimum_stake: float = DEFAULT_MINIMUM_STAKE,
) -> StakeSizingResult:
    """Size a purchased contract to at most 1% of fresh available capital.

    Deriv purchased-contract stake is treated as the contractual maximum loss.
    Risk budget is rounded down to cents. If that budget cannot fund the
    broker's minimum stake, no live stake is returned; the minimum is never
    forced above the account's risk budget.
    """
    if (
        isinstance(verified_available_balance, bool)
        or not isinstance(verified_available_balance, (int, float, Decimal))
        or not isfinite(float(verified_available_balance))
        or float(verified_available_balance) < 0
    ):
        return StakeSizingResult(False, None, None, "AVAILABLE_BALANCE_INVALID")

    if (
        isinstance(maximum_risk_fraction, bool)
        or not isinstance(maximum_risk_fraction, (int, float, Decimal))
        or not isfinite(float(maximum_risk_fraction))
        or not 0 < float(maximum_risk_fraction) <= 0.02
    ):
        return StakeSizingResult(False, None, None, "MAX_TRADE_RISK_FRACTION_INVALID")

    if (
        isinstance(minimum_stake, bool)
        or not isinstance(minimum_stake, (int, float, Decimal))
        or not isfinite(float(minimum_stake))
        or float(minimum_stake) <= 0
    ):
        return StakeSizingResult(False, None, None, "MINIMUM_STAKE_INVALID")

    try:
        balance = Decimal(str(verified_available_balance))
        fraction = Decimal(str(maximum_risk_fraction))
        minimum = Decimal(str(minimum_stake)).quantize(_CENT, rounding=ROUND_UP)
        budget = (balance * fraction).quantize(_CENT, rounding=ROUND_DOWN)
    except (InvalidOperation, ValueError, OverflowError):
        return StakeSizingResult(False, None, None, "STAKE_SIZING_INPUT_INVALID")

    if budget < minimum:
        return StakeSizingResult(
            False,
            None,
            float(budget),
            "STAKE_RISK_BUDGET_BELOW_BROKER_MINIMUM",
        )

    # With a validated risk fraction <= 2%, the budget is below available
    # balance. Keep this assertion as a fail-closed defense against future edits.
    if budget > balance:
        return StakeSizingResult(False, None, float(budget), "STAKE_EXCEEDS_AVAILABLE_BALANCE")

    return StakeSizingResult(
        True,
        float(budget),
        float(budget),
        "BALANCE_SCALED_WITHIN_RISK_BUDGET",
    )
