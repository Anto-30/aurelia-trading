from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from math import isfinite

from .economics import TradeEconomics
from .models import (
    AccountIdentity,
    AuthorizationContext,
    CapitalSnapshot,
    Decision,
    OrderIntent,
    utc_now,
)
from .stake_sizing import size_stake_for_balance
from .probability_policy import MAX_PROBABILITY, MIN_PROBABILITY, probability_is_valid

STARTING_STAKE = 1.00
EXECUTION_MINIMUM_STAKE = 1.00


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    reason_codes: tuple[str, ...]


def decision_economics_gate(decision: Decision) -> tuple[bool, str, float | None]:
    if any(value is None for value in (decision.average_win, decision.average_loss)):
        return False, "ECONOMICS_INPUTS_MISSING", None

    raw_values = (
        decision.probability,
        decision.average_win,
        decision.average_loss,
        decision.execution_cost,
        decision.slippage_cost,
        decision.quote_cost,
    )
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in raw_values
    ):
        return False, "ECONOMICS_INPUTS_INVALID", None
    try:
        if not all(isfinite(float(value)) for value in raw_values):
            return False, "ECONOMICS_INPUTS_INVALID", None
        economics = TradeEconomics(
            probability=float(decision.probability),
            average_win=float(decision.average_win),
            average_loss=float(decision.average_loss),
            execution_cost=float(decision.execution_cost),
            slippage_cost=float(decision.slippage_cost),
            quote_cost=float(decision.quote_cost),
        )
    except (TypeError, ValueError, OverflowError):
        return False, "ECONOMICS_INPUTS_INVALID", None

    allowed, reason = economics.gate()
    computed = economics.expected_value if isfinite(economics.expected_value) else None
    if decision.expected_value is not None:
        if isinstance(decision.expected_value, bool) or not isinstance(
            decision.expected_value, (int, float)
        ):
            return False, "EXPECTED_VALUE_INVALID", computed
        try:
            supplied = float(decision.expected_value)
        except (TypeError, ValueError, OverflowError):
            return False, "EXPECTED_VALUE_INVALID", computed
        if not isfinite(supplied):
            return False, "EXPECTED_VALUE_NON_FINITE", computed
        if abs(supplied - economics.expected_value) > 1e-9:
            return False, "EXPECTED_VALUE_MISMATCH", computed
    if not allowed:
        return False, reason, computed
    return True, "EXPECTED_VALUE_POSITIVE", computed


def requested_stake_is_permitted(
    requested: float,
    capital: CapitalSnapshot,
    minimum_stake: float = EXECUTION_MINIMUM_STAKE,
) -> bool:
    # External strategy payloads are untrusted. Malformed or extreme numeric
    # values must become a denial, not an exception that bypasses the gate.
    if isinstance(requested, bool) or not isinstance(requested, (int, float)):
        return False
    if isinstance(capital.available_balance, bool) or not isinstance(
        capital.available_balance, (int, float)
    ):
        return False
    if isinstance(minimum_stake, bool) or not isinstance(minimum_stake, (int, float)):
        return False
    try:
        value = float(requested)
        available = float(capital.available_balance)
        minimum = float(minimum_stake)
        valid_capital = capital.is_valid()
    except (TypeError, ValueError, OverflowError):
        return False
    return bool(
        isfinite(value)
        and isfinite(available)
        and isfinite(minimum)
        and minimum > 0
        and value >= minimum
        and value <= available
        and valid_capital
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
    if account != capital.account:
        reasons.append("ACCOUNT_IDENTITY_MISMATCH")
    if execution_mode == "LIVE" and (
        account.environment != "real" or capital.account.environment != "real"
    ):
        reasons.append("ACCOUNT_ENVIRONMENT_NOT_REAL")
    if account.currency != capital.currency:
        reasons.append("CURRENCY_MISMATCH")
    if not capital.is_valid():
        reasons.append("CAPITAL_TRUTH_NOT_FRESH")
    if execution_mode == "LIVE" and capital.currency.strip().upper() != "USD":
        reasons.append("USD_STAKE_POLICY_REQUIRES_USD_ACCOUNT")
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

    if execution_mode == "LIVE":
        economics_allowed, economics_reason, _ = decision_economics_gate(decision)
        if not economics_allowed:
            reasons.append(economics_reason)

    if not decision.strategy_hash:
        reasons.append("STRATEGY_HASH_MISSING")
    if not config_hash or config_hash != runtime_config_hash:
        reasons.append("CONFIG_DIGEST_MISMATCH")

    # Keep the proposed request valid, but do not let a strategy/LLM choose
    # the final capital amount. LIVE sizing is recalculated deterministically
    # from the exact fresh available-balance snapshot and then travels in the
    # authorization context to intent creation.
    if not requested_stake_is_permitted(decision.risk_requested_stake, capital):
        reasons.append("STAKE_NOT_AFFORDABLE_OR_BELOW_BROKER_MINIMUM")
    if execution_mode == "LIVE":
        sizing = size_stake_for_balance(capital.available_balance)
        if not sizing.allowed:
            reasons.append(sizing.reason)
        else:
            try:
                proposed_stake = float(decision.risk_requested_stake)
            except (TypeError, ValueError, OverflowError):
                proposed_stake = float("nan")
            # Risk/exposure controls must evaluate the exact stake that will be
            # submitted. Do not silently resize after those approvals were
            # computed against a strategy/agent-proposed amount.
            if not isfinite(proposed_stake) or abs(proposed_stake - float(sizing.stake)) > 1e-9:
                reasons.append("LIVE_STAKE_NOT_POLICY_SIZED")

    if not risk_approved:
        reasons.append("RISK_WARDEN_REJECTED")
    if not firewall_approved:
        reasons.append("EXECUTION_FIREWALL_REJECTED")
    if execution_mode not in {"LIVE", "VERIFY_ONLY"}:
        reasons.append("INVALID_EXECUTION_MODE")

    if execution_mode == "LIVE":
        if not reconciliation_healthy:
            reasons.append("RECONCILIATION_UNHEALTHY")
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
    proposal_parameters_hash: str | None = None,
) -> OrderIntent:
    if mode == "VERIFY_ONLY":
        now = utc_now()
        if not (context.authorization_issued_at <= now < context.authorization_expires_at):
            raise RuntimeError("CANNOT_BUILD_EXPIRED_VERIFICATION_INTENT")
    elif not context.is_current() or not context.final_execution_authorization:
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
        proposal_parameters_hash=proposal_parameters_hash,
    )
