"""Pure, side-effect-free AURELIA assurance predicates.

This module is intentionally outside the capital execution path. It does not
submit orders, mutate broker state, or grant authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AuthorizationInputs:
    account_is_real: bool
    broker_session_verified: bool
    market_data_valid: bool
    strategy_valid: bool
    probability_valid: bool
    probability: Optional[float]
    risk_approved: bool
    capital_authorized: bool
    stake_affordable: bool
    execution_firewall_approved: bool
    kill_switch_off: bool
    reconciliation_healthy: bool
    stale_authorization: bool
    configuration_matched: bool
    unknown_broker_state: bool


def probability_policy_valid(probability: Optional[float]) -> bool:
    """Validate without clipping. 0.55-0.75 is inclusive."""
    return probability is not None and 0.55 <= probability <= 0.75


def final_execution_authorized(x: AuthorizationInputs) -> bool:
    """Pure conjunction for a fully-known authorization state."""
    if x.unknown_broker_state or x.stale_authorization:
        return False
    return all(
        (
            x.account_is_real,
            x.broker_session_verified,
            x.market_data_valid,
            x.strategy_valid,
            x.probability_valid and probability_policy_valid(x.probability),
            x.risk_approved,
            x.capital_authorized,
            x.stake_affordable,
            x.execution_firewall_approved,
            x.kill_switch_off,
            x.reconciliation_healthy,
            x.configuration_matched,
        )
    )


def order_affordability(balance: Optional[float], minimum_stake: float = 1.50) -> str:
    """Return explicit affordability state; absence of balance is UNKNOWN."""
    if balance is None:
        return "UNKNOWN"
    return "AFFORDABLE" if balance >= minimum_stake else "UNAFFORDABLE"


def capital_readiness_blocker_for_balance(
    balance: Optional[float], minimum_stake: float = 1.50
) -> bool:
    """Low balance is never a global system-readiness blocker."""
    return False


def blind_resubmit_allowed(*, broker_state_unknown: bool) -> bool:
    """Blind resubmission is never permitted.

    A known broker state is not sufficient to justify a new economic action:
    the caller must perform explicit recovery/reconciliation and establish a
    new, authorized intent before any resubmission path can be considered.
    """
    return False
