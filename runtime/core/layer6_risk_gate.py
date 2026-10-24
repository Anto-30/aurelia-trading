"""Execution-neutral, fail-closed Layer 6 risk veto.

This module never authorizes capital or submits broker requests. It is a pure,
local risk evaluation layer; the canonical AURELIA capital plane and LIVE_LOCK
remain the only execution authority.

The elapsed-time guard rejects a late result after the pure evaluation returns.
It does not pre-empt Python execution, so this method must remain synchronous,
side-effect-free, and free of I/O or plugin/LLM calls.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

logger = logging.getLogger("AURELIA.Layer6RiskGate")


def _finite_number(value: Any) -> float | None:
    """Accept finite numeric scalars only; booleans and numeric strings are invalid."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


@dataclass(frozen=True)
class RiskPolicy:
    """Explicit local risk limits; values must be supplied by verified policy."""

    max_daily_loss: float
    max_position_size: float
    max_total_exposure: float
    timeout_ms: int = 50

    def __post_init__(self) -> None:
        for name in ("max_daily_loss", "max_position_size", "max_total_exposure"):
            value = _finite_number(getattr(self, name))
            if value is None or value <= 0:
                raise ValueError(f"INVALID_RISK_POLICY_{name.upper()}")
        if (
            isinstance(self.timeout_ms, bool)
            or not isinstance(self.timeout_ms, int)
            or self.timeout_ms <= 0
        ):
            raise ValueError("INVALID_RISK_POLICY_TIMEOUT_MS")
        if self.max_total_exposure < self.max_position_size:
            raise ValueError("TOTAL_EXPOSURE_LIMIT_BELOW_POSITION_LIMIT")


@dataclass(frozen=True)
class RiskRequest:
    """Normalized risk snapshot. This is not a Deriv order payload."""

    symbol: str
    direction: str
    stake: Any
    available_balance: Any
    daily_pnl: Any
    worst_case_loss: Any
    existing_exposure: Any = 0.0
    pending_exposure: Any = 0.0
    concurrent_exposure: Any = 0.0
    correlated_exposure: Any = 0.0
    account_verified: bool = False
    state_verified: bool = False
    kill_switch_active: bool = True


@dataclass(frozen=True)
class RiskVerdict:
    """Risk-only result. Deliberately has no `authorized` field."""

    risk_approved: bool
    reason: str
    evaluated_at_utc: str
    latency_ms: float
    gate_name: str = "LAYER_6_RISK_GATE"


class Layer6RiskGate:
    """Deterministic veto gate, disabled by default, never a capital authorizer."""

    def __init__(self, policy: RiskPolicy, *, enabled: bool = False) -> None:
        if not isinstance(policy, RiskPolicy):
            raise TypeError("RISK_POLICY_REQUIRED")
        if not isinstance(enabled, bool):
            raise TypeError("RISK_GATE_ENABLED_FLAG_MUST_BE_BOOLEAN")
        self.policy = policy
        self.enabled = enabled

    def _evaluate_checks(self, request: RiskRequest) -> str:
        if not isinstance(request, RiskRequest):
            return "INVALID_RISK_REQUEST"
        if not isinstance(request.symbol, str) or not request.symbol.strip():
            return "INVALID_SYMBOL"
        if not isinstance(request.direction, str) or request.direction.strip().upper() not in {
            "CALL", "PUT", "BUY", "SELL"
        }:
            return "INVALID_DIRECTION"
        if request.account_verified is not True:
            return "ACCOUNT_UNVERIFIED"
        if request.state_verified is not True:
            return "RISK_STATE_UNVERIFIED"
        if request.kill_switch_active is not False:
            return "KILL_SWITCH_ACTIVE"

        stake = _finite_number(request.stake)
        if stake is None or stake <= 0:
            return "INVALID_STAKE"
        balance = _finite_number(request.available_balance)
        if balance is None or balance < 0:
            return "AVAILABLE_BALANCE_UNVERIFIED"
        daily_pnl = _finite_number(request.daily_pnl)
        if daily_pnl is None:
            return "DAILY_PNL_UNVERIFIED"
        worst_case_loss = _finite_number(request.worst_case_loss)
        if worst_case_loss is None or worst_case_loss <= 0:
            return "WORST_CASE_LOSS_UNVERIFIED"

        exposure_values: list[float] = []
        for name in (
            "existing_exposure", "pending_exposure", "concurrent_exposure", "correlated_exposure"
        ):
            value = _finite_number(getattr(request, name))
            if value is None or value < 0:
                return f"INVALID_{name.upper()}"
            exposure_values.append(value)

        if stake > self.policy.max_position_size:
            return "EXCEEDS_MAX_POSITION_SIZE"
        if stake > balance:
            return "STAKE_EXCEEDS_VERIFIED_AVAILABLE_BALANCE"
        # Reserve the proposed trade's verified worst-case loss against the
        # remaining daily loss budget; checking only today's realized PnL can
        # approve a trade that crosses the hard limit on its next loss.
        if daily_pnl - worst_case_loss <= -self.policy.max_daily_loss:
            return "DAILY_LOSS_LIMIT_BREACHED"
        total_exposure = math.fsum((*exposure_values, stake))
        if not math.isfinite(total_exposure):
            return "TOTAL_EXPOSURE_UNVERIFIED"
        if total_exposure > self.policy.max_total_exposure:
            return "EXCEEDS_TOTAL_EXPOSURE_LIMIT"
        return "RISK_CHECKS_PASSED"

    def evaluate(self, request: RiskRequest) -> RiskVerdict:
        """Return a risk-only verdict, rejecting exceptions and late results."""
        started = perf_counter()
        reason = "DEFAULT_FAIL_CLOSED"
        approved = False
        try:
            if not self.enabled:
                reason = "RISK_GATE_DISABLED"
            else:
                reason = self._evaluate_checks(request)
                approved = reason == "RISK_CHECKS_PASSED"
        except Exception as exc:  # risk code must convert failures to a denial
            logger.critical("Layer 6 evaluation failed closed (%s)", type(exc).__name__)
            reason = "EXCEPTION_FAIL_CLOSED"
            approved = False
        elapsed_ms = max(0.0, (perf_counter() - started) * 1000.0)
        if elapsed_ms > self.policy.timeout_ms:
            approved = False
            reason = "TIMEOUT_FAIL_CLOSED"
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return RiskVerdict(
            risk_approved=approved,
            reason=reason,
            evaluated_at_utc=timestamp,
            latency_ms=round(elapsed_ms, 3),
        )
