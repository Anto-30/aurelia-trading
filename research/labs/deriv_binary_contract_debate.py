"""Deterministic, research-only gate for fixed-stake Deriv-style binary contracts.

This module has no broker transport and no capital authority. It evaluates a
quote and calibrated probability estimate; it never sends an order.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite
from typing import Literal


Decision = Literal["REJECT", "WAIT", "RESEARCH_APPROVED"]


@dataclass(frozen=True)
class ContractProposal:
    symbol: str
    direction: str
    stake: float
    total_return_if_won: float
    estimated_win_probability: float
    probability_lower_bound: float
    quote_age_ms: float
    payout_change_pct_500ms: float = 0.0
    equity: float = 0.0
    drawdown_pct: float = 0.0
    consecutive_losses: int = 0
    calibration_valid: bool = False
    out_of_sample_qualified: bool = False


@dataclass(frozen=True)
class DebateDecision:
    action: Decision
    reason: str
    break_even_probability: float | None = None
    expected_value_cash: float | None = None
    expected_value_per_stake: float | None = None
    half_kelly_fraction: float | None = None
    maximum_stake: float | None = None
    checks: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DebatePolicy:
    minimum_ev_per_stake: float = 0.02
    maximum_stake_fraction: float = 0.01
    maximum_quote_age_ms: float = 500.0
    maximum_payout_change_pct_500ms: float = 2.0
    maximum_drawdown_pct: float = 0.03
    maximum_consecutive_losses: int = 3
    minimum_equity: float = 0.0


def evaluate_contract(
    proposal: ContractProposal, policy: DebatePolicy = DebatePolicy()
) -> DebateDecision:
    """Run deterministic proposal/critic/arbitration rules; no execution."""
    numeric = {
        "stake": proposal.stake,
        "total_return_if_won": proposal.total_return_if_won,
        "estimated_win_probability": proposal.estimated_win_probability,
        "probability_lower_bound": proposal.probability_lower_bound,
        "quote_age_ms": proposal.quote_age_ms,
        "payout_change_pct_500ms": proposal.payout_change_pct_500ms,
        "equity": proposal.equity,
        "drawdown_pct": proposal.drawdown_pct,
        "minimum_ev_per_stake": policy.minimum_ev_per_stake,
        "maximum_stake_fraction": policy.maximum_stake_fraction,
        "maximum_quote_age_ms": policy.maximum_quote_age_ms,
        "maximum_payout_change_pct_500ms": policy.maximum_payout_change_pct_500ms,
        "maximum_drawdown_pct": policy.maximum_drawdown_pct,
        "minimum_equity": policy.minimum_equity,
    }
    for name, value in numeric.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            return DebateDecision("REJECT", f"INVALID_NUMERIC:{name}")
    if not proposal.symbol.strip() or not proposal.direction.strip():
        return DebateDecision("REJECT", "CONTRACT_IDENTITY_MISSING")
    if proposal.stake <= 0 or proposal.total_return_if_won <= proposal.stake:
        return DebateDecision("REJECT", "CONTRACT_PAYOUT_INVALID")
    if not 0.0 <= proposal.probability_lower_bound <= proposal.estimated_win_probability <= 1.0:
        return DebateDecision("REJECT", "PROBABILITY_INTERVAL_INVALID")
    if isinstance(proposal.consecutive_losses, bool) or not isinstance(proposal.consecutive_losses, int) or proposal.consecutive_losses < 0:
        return DebateDecision("REJECT", "CONSECUTIVE_LOSS_COUNT_INVALID")
    if proposal.equity <= 0:
        return DebateDecision("REJECT", "EQUITY_NOT_VERIFIED_OR_NONPOSITIVE")
    if not proposal.calibration_valid:
        return DebateDecision("REJECT", "PROBABILITY_CALIBRATION_UNVERIFIED")
    if not proposal.out_of_sample_qualified:
        return DebateDecision("REJECT", "OUT_OF_SAMPLE_QUALIFICATION_MISSING")
    if proposal.quote_age_ms < 0 or proposal.quote_age_ms > policy.maximum_quote_age_ms:
        return DebateDecision("WAIT", "QUOTE_STALE")
    if abs(proposal.payout_change_pct_500ms) > policy.maximum_payout_change_pct_500ms:
        return DebateDecision("WAIT", "PAYOUT_UNSTABLE")
    if proposal.drawdown_pct < 0 or proposal.drawdown_pct >= policy.maximum_drawdown_pct:
        return DebateDecision("REJECT", "DRAWDOWN_CIRCUIT_BREAKER")
    if proposal.consecutive_losses >= policy.maximum_consecutive_losses:
        return DebateDecision("REJECT", "CONSECUTIVE_LOSS_CIRCUIT_BREAKER")

    stake = proposal.stake
    profit = proposal.total_return_if_won - stake
    break_even = stake / proposal.total_return_if_won
    p = proposal.probability_lower_bound  # conservative CI bound, not point estimate
    ev_cash = p * profit - (1.0 - p) * stake
    ev_per_stake = ev_cash / stake
    net_odds = profit / stake
    kelly = p - ((1.0 - p) / net_odds)
    half_kelly = max(0.0, kelly / 2.0)
    maximum_stake = min(
        proposal.equity * policy.maximum_stake_fraction,
        proposal.equity * half_kelly,
    )
    checks = (
        "BREAK_EVEN_CHECKED",
        "CONSERVATIVE_PROBABILITY_BOUND_USED",
        "EV_NET_OF_STAKE_CHECKED",
        "FRACTIONAL_KELLY_CAPPED",
        "NO_ORDER_SUBMISSION",
    )
    if p <= break_even:
        return DebateDecision("REJECT", "CONSERVATIVE_PROBABILITY_NOT_ABOVE_BREAK_EVEN",
                              break_even, ev_cash, ev_per_stake, half_kelly, maximum_stake, checks)
    if ev_per_stake < policy.minimum_ev_per_stake:
        return DebateDecision("REJECT", "EXPECTED_VALUE_BUFFER_NOT_MET",
                              break_even, ev_cash, ev_per_stake, half_kelly, maximum_stake, checks)
    if maximum_stake <= 0 or stake > maximum_stake:
        return DebateDecision("REJECT", "PROPOSED_STAKE_EXCEEDS_RISK_CAP",
                              break_even, ev_cash, ev_per_stake, half_kelly, maximum_stake, checks)
    return DebateDecision("RESEARCH_APPROVED", "MATH_AND_RESEARCH_GATES_PASSED_NOT_EXECUTABLE",
                          break_even, ev_cash, ev_per_stake, half_kelly, maximum_stake, checks)
