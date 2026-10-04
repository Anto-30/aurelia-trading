from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from math import isfinite

from .models import (
    AccountIdentity,
    AuthorizationContext,
    CapitalSnapshot,
    Decision,
    OrderIntent,
    utc_now,
)

MIN_PROBABILITY = 0.55
MAX_PROBABILITY = 0.75
STARTING_STAKE = 1.00
EXECUTION_MINIMUM_STAKE = 1.00


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    reason_codes: tuple[str, ...]


def probability_is_valid(probability: float) -> bool:
    return isfinite(probability) and MIN_PROBABILITY <= probability <= MAX_PROBABILITY


def requested_stake_is_permitted(
    requested: float,
    capital: CapitalSnapshot,
    minimum_stake: float = EXECUTION_MINIMUM_STAKE,
) -> bool:
    return bool(
        isfinite(requested)
        and requested >= minimum_stake
        and requested <= capital.available_balance
        and capital.is_valid()
    )


def authorization_gate(
    *,
    decision: Decision,
    account: AccountIdentity,
    capital: CapitalSnapshot,
    config_hash: str,
    runtime_config_hash: str,
    kill_switch_off: bool,
    risk_approved: bool,
    firewall_approved: bool,
    reconciliation_healthy: bool,
    final_execution_authorization: bool,
    live_trading_enabled: bool,
    probability_calibrated: bool = False,
    probability_fresh: bool = False,
    probability_drift_ok: bool = False,
    market_data_validated: bool = False,
    exposure_approved: bool = False,
    authorization_ttl_seconds: float = 30.0,
    execution_mode: str = "LIVE",
) -> tuple[GateResult, AuthorizationContext | None]:
    reasons: list[str] = []

    if account.account_type != "real":
        reasons.append("ACCOUNT_NOT_REAL")
    if account.loginid != capital.account.loginid:
        reasons.append("ACCOUNT_IDENTITY_MISMATCH")
    if account.currency != capital.currency:
        reasons.append("CURRENCY_MISMATCH")
    if not capital.is_valid():
        reasons.append("CAPITAL_TRUTH_NOT_FRESH")
    if not probability_is_valid(decision.probability):
        reasons.append("PROBABILITY_OUTSIDE_HARD_POLICY")

    # Probability validity is intentionally conjunctive. A probability inside
    # the numeric range is not sufficient when calibration is stale/invalid or
    # drift has not been cleared.
    if not probability_calibrated:
        reasons.append("PROBABILITY_NOT_CALIBRATED")
    if not probability_fresh:
        reasons.append("PROBABILITY_NOT_FRESH")
    if not probability_drift_ok:
        reasons.append("PROBABILITY_DRIFT_DETECTED_OR_UNVERIFIED")
    if not market_data_validated:
        reasons.append("MARKET_DATA_NOT_VALIDATED")
    if not exposure_approved:
        reasons.append("EXPOSURE_NOT_APPROVED")

    if not decision.strategy_hash:
        reasons.append("STRATEGY_HASH_MISSING")
    if not config_hash or config_hash != runtime_config_hash:
        reasons.append("CONFIG_DIGEST_MISMATCH")
    if not requested_stake_is_permitted(decision.risk_requested_stake, capital):
        reasons.append("STAKE_NOT_AFFORDABLE_OR_BELOW_BROKER_MINIMUM")
    if not risk_approved:
        reasons.append("RISK_WARDEN_REJECTED")
    if not firewall_approved:
        reasons.append("EXECUTION_FIREWALL_REJECTED")
    if execution_mode not in {"LIVE", "VERIFY_ONLY"}:
        reasons.append("INVALID_EXECUTION_MODE")

    if execution_mode == "LIVE":
        if not kill_switch_off:
            reasons.append("KILL_SWITCH_ON")
        if not final_execution_authorization:
            reasons.append("FINAL_EXECUTION_AUTHORIZATION_FALSE")
        if not live_trading_enabled:
            reasons.append("LIVE_TRADING_DISABLED")

    if reasons:
        return GateResult(False, tuple(reasons)), None

    now = utc_now()
    return (
        GateResult(True, ()),
        AuthorizationContext(
            decision=decision,
            account=account,
            capital=capital,
            config_hash=config_hash,
            authorization_id=f"auth:{decision.decision_id}:{int(now.timestamp() * 1000)}",
            authorization_issued_at=now,
            authorization_expires_at=now + timedelta(seconds=authorization_ttl_seconds),
            kill_switch_off=kill_switch_off,
            risk_approved=risk_approved,
            firewall_approved=firewall_approved,
            reconciliation_healthy=reconciliation_healthy,
            final_execution_authorization=final_execution_authorization,
        ),
    )


def build_intent(
    context: AuthorizationContext,
    *,
    proposal_id: str | None,
    mode: str = "LIVE",
) -> OrderIntent:
    if not context.is_current() or not context.final_execution_authorization:
        raise RuntimeError("CANNOT_BUILD_UNAUTHORIZED_INTENT")
    decision = context.decision
    return OrderIntent(
        intent_id=f"intent:{decision.decision_id}",
        decision_id=decision.decision_id,
        account=context.account,
        symbol=decision.symbol,
        direction=decision.direction,
        stake=decision.risk_requested_stake,
        created_at=utc_now(),
        strategy_hash=decision.strategy_hash,
        config_hash=context.config_hash,
        execution_mode=mode,
        proposal_id=proposal_id,
    )
