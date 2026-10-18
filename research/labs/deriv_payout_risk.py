"""Research-only payout maths and bounded deterministic debate for Deriv options.

This module deliberately has no network, credential, broker-adapter, or order API.
It may reject or pass a proposal for research simulation; it cannot authorize orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import floor, isfinite

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
ORDER_SUBMISSION_PERMITTED = False


class DebateAction(str, Enum):
    REJECT = "REJECT"
    WAIT = "WAIT"
    APPROVE_RESEARCH_ONLY = "APPROVE_RESEARCH_ONLY"


def _number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def _floor_cents(value: float) -> float:
    # Decimal currency rounding is intentionally downward: never exceed the risk cap.
    return floor((value + 1e-10) * 100.0) / 100.0


@dataclass(frozen=True)
class ContractQuote:
    """Normalized proposal quote: ask_price is purchase cost; payout_total is gross return on win."""

    symbol: str
    contract_type: str
    currency: str
    ask_price: float
    payout_total: float
    proposal_id: str
    quote_age_ms: float
    payout_drop_fraction: float = 0.0


@dataclass(frozen=True)
class AccountRiskSnapshot:
    equity: float
    daily_peak_equity: float
    consecutive_losses: int
    currency: str = "USD"
    age_ms: float = 0.0
    verified: bool = True


@dataclass(frozen=True)
class TradeProposal:
    quote: ContractQuote
    proposer_probability: float
    critic_probability: float
    confidence_lower_bound: float
    calibrated: bool
    volatility_percentile: float
    debate_elapsed_ms: float
    additional_cost: float = 0.0


@dataclass(frozen=True)
class CriticConfig:
    # Match AURELIA's existing 1% per-trade risk ceiling; do not use full Kelly.
    max_trade_risk_fraction: float = 0.01
    min_ev_per_risk_dollar: float = 0.02
    min_probability: float = 0.55
    max_probability: float = 0.75
    max_probability_disagreement: float = 0.10
    max_daily_drawdown_fraction: float = 0.03
    max_consecutive_losses: int = 3
    max_quote_age_ms: float = 50.0
    max_debate_elapsed_ms: float = 50.0
    max_payout_drop_fraction: float = 0.01
    max_volatility_percentile: float = 0.95
    max_account_snapshot_age_ms: float = 5_000.0
    minimum_stake: float = 1.0
    stake_currency: str = "USD"


@dataclass(frozen=True)
class DebateDecision:
    action: DebateAction
    reasons: tuple[str, ...]
    conservative_probability: float | None = None
    break_even_probability: float | None = None
    expected_value: float | None = None
    ev_per_risk_dollar: float | None = None
    full_kelly_fraction: float | None = None
    half_kelly_fraction: float | None = None
    maximum_risk_budget: float | None = None
    recommended_stake_for_requote: float | None = None
    research_only: bool = True
    capital_authority: bool = False
    order_submission_permitted: bool = False


def expected_value(
    *,
    ask_price: float,
    payout_total: float,
    win_probability: float,
    additional_cost: float = 0.0,
) -> float:
    """Expected net P&L in account currency, before unmodelled effects.

    A win nets payout_total - ask_price - additional_cost. A loss is
    -(ask_price + additional_cost). Costs already reflected in the broker quote
    must not be subtracted a second time.
    """
    values = (ask_price, payout_total, win_probability, additional_cost)
    if not all(_number(v) for v in values):
        raise ValueError("ECONOMICS_NON_FINITE_OR_NON_NUMERIC")
    if ask_price <= 0 or payout_total <= 0 or additional_cost < 0:
        raise ValueError("ECONOMICS_AMOUNT_OUT_OF_RANGE")
    if not 0.0 <= win_probability <= 1.0:
        raise ValueError("PROBABILITY_OUT_OF_RANGE")
    win_net = payout_total - ask_price - additional_cost
    loss_net = ask_price + additional_cost
    return win_probability * win_net - (1.0 - win_probability) * loss_net


def break_even_probability(*, ask_price: float, payout_total: float, additional_cost: float = 0.0) -> float:
    """Win probability required for zero EV under the supplied contract cashflows."""
    values = (ask_price, payout_total, additional_cost)
    if not all(_number(v) for v in values):
        raise ValueError("ECONOMICS_NON_FINITE_OR_NON_NUMERIC")
    if ask_price <= 0 or payout_total <= 0 or additional_cost < 0:
        raise ValueError("ECONOMICS_AMOUNT_OUT_OF_RANGE")
    if payout_total <= additional_cost:
        raise ValueError("WIN_PAYOUT_DOES_NOT_EXCEED_COST")
    return (ask_price + additional_cost) / payout_total


def _blocked(*reasons: str) -> DebateDecision:
    return DebateDecision(action=DebateAction.REJECT, reasons=tuple(reasons))


def evaluate_debate(
    proposal: TradeProposal,
    account: AccountRiskSnapshot,
    config: CriticConfig = CriticConfig(),
) -> DebateDecision:
    """Run one bounded Proposer/Critic/Arbiter pass. Never submits an order.

    The Critic uses the minimum of the Proposer estimate, independent Critic
    estimate, and supplied lower confidence bound. Missing, stale, invalid, or
    uncalibrated data fails closed. Re-quote is required if Kelly/risk caps
    imply a lower price than the quote was requested for.
    """
    if not isinstance(proposal, TradeProposal):
        return _blocked("PROPOSAL_OBJECT_INVALID")
    if not isinstance(account, AccountRiskSnapshot):
        return _blocked("ACCOUNT_SNAPSHOT_OBJECT_INVALID")
    if not isinstance(proposal.quote, ContractQuote):
        return _blocked("QUOTE_OBJECT_INVALID")
    if not isinstance(config, CriticConfig):
        return _blocked("CRITIC_CONFIG_OBJECT_INVALID")

    q = proposal.quote
    reasons: list[str] = []

    # Configuration may tighten but can never weaken the hard policy.
    if not (_number(config.max_trade_risk_fraction) and 0 < config.max_trade_risk_fraction <= 0.01):
        reasons.append("CONFIG_MAX_TRADE_RISK_FRACTION_INVALID")
    if not (_number(config.min_ev_per_risk_dollar) and config.min_ev_per_risk_dollar >= 0.02):
        reasons.append("CONFIG_MIN_EV_INVALID")
    if not (_number(config.min_probability) and config.min_probability >= 0.55):
        reasons.append("CONFIG_MIN_PROBABILITY_INVALID")
    if not (_number(config.max_probability) and config.max_probability <= 0.75):
        reasons.append("CONFIG_MAX_PROBABILITY_INVALID")
    if _number(config.min_probability) and _number(config.max_probability) and config.min_probability > config.max_probability:
        reasons.append("CONFIG_PROBABILITY_BAND_INVALID")
    if not (_number(config.max_probability_disagreement) and 0 <= config.max_probability_disagreement <= 0.10):
        reasons.append("CONFIG_PROBABILITY_DISAGREEMENT_INVALID")
    if not (_number(config.max_daily_drawdown_fraction) and 0 < config.max_daily_drawdown_fraction <= 0.03):
        reasons.append("CONFIG_MAX_DRAWDOWN_INVALID")
    if not isinstance(config.max_consecutive_losses, int) or isinstance(config.max_consecutive_losses, bool) or not 1 <= config.max_consecutive_losses <= 3:
        reasons.append("CONFIG_MAX_CONSECUTIVE_LOSSES_INVALID")
    if not (_number(config.max_quote_age_ms) and 0 < config.max_quote_age_ms <= 50.0):
        reasons.append("CONFIG_QUOTE_AGE_INVALID")
    if not (_number(config.max_debate_elapsed_ms) and 0 < config.max_debate_elapsed_ms <= 50.0):
        reasons.append("CONFIG_DEBATE_LATENCY_INVALID")
    if not (_number(config.max_payout_drop_fraction) and 0 <= config.max_payout_drop_fraction <= 0.01):
        reasons.append("CONFIG_PAYOUT_DROP_TOLERANCE_INVALID")
    if not (_number(config.max_volatility_percentile) and 0 < config.max_volatility_percentile <= 0.95):
        reasons.append("CONFIG_VOLATILITY_PERCENTILE_INVALID")
    if not (_number(config.max_account_snapshot_age_ms) and 0 < config.max_account_snapshot_age_ms <= 5_000.0):
        reasons.append("CONFIG_ACCOUNT_SNAPSHOT_AGE_INVALID")
    if not (_number(config.minimum_stake) and config.minimum_stake >= 1.0):
        reasons.append("CONFIG_MINIMUM_STAKE_INVALID")
    if not isinstance(config.stake_currency, str) or config.stake_currency.strip().upper() != "USD":
        reasons.append("CONFIG_STAKE_CURRENCY_UNSUPPORTED")
    if reasons:
        return _blocked(*reasons)

    numeric_quote = (q.ask_price, q.payout_total, q.quote_age_ms, q.payout_drop_fraction)
    if not all(_number(v) for v in numeric_quote):
        reasons.append("QUOTE_NON_FINITE_OR_NON_NUMERIC")
    elif q.ask_price <= 0 or q.payout_total <= 0 or q.quote_age_ms < 0 or not 0 <= q.payout_drop_fraction <= 1:
        reasons.append("QUOTE_VALUE_OUT_OF_RANGE")
    elif q.ask_price < config.minimum_stake:
        reasons.append("QUOTE_BELOW_MINIMUM_STAKE")
    if not all(isinstance(value, str) and value.strip() for value in (q.symbol, q.contract_type, q.proposal_id)):
        reasons.append("QUOTE_IDENTITY_MISSING")
    if not isinstance(q.currency, str) or q.currency.strip().upper() != config.stake_currency.strip().upper():
        reasons.append("QUOTE_CURRENCY_NOT_SUPPORTED")
    if _number(q.quote_age_ms) and q.quote_age_ms >= config.max_quote_age_ms:
        reasons.append("QUOTE_STALE")
    if _number(q.payout_drop_fraction) and q.payout_drop_fraction > config.max_payout_drop_fraction:
        reasons.append("PAYOUT_MOVED_BEYOND_TOLERANCE")

    account_numbers = (account.equity, account.daily_peak_equity, account.age_ms)
    if not all(_number(v) for v in account_numbers):
        reasons.append("ACCOUNT_SNAPSHOT_INVALID")
    elif account.equity <= 0 or account.daily_peak_equity < account.equity or account.age_ms < 0:
        reasons.append("ACCOUNT_SNAPSHOT_VALUE_OUT_OF_RANGE")
    if not isinstance(account.verified, bool) or not account.verified:
        reasons.append("ACCOUNT_SNAPSHOT_UNVERIFIED")
    if _number(account.age_ms) and account.age_ms > config.max_account_snapshot_age_ms:
        reasons.append("ACCOUNT_SNAPSHOT_STALE")
    if not isinstance(account.consecutive_losses, int) or isinstance(account.consecutive_losses, bool) or account.consecutive_losses < 0:
        reasons.append("CONSECUTIVE_LOSS_COUNT_INVALID")
    elif account.consecutive_losses >= config.max_consecutive_losses:
        reasons.append("CONSECUTIVE_LOSS_CIRCUIT_BREAKER")
    if not isinstance(account.currency, str) or account.currency.strip().upper() != config.stake_currency.strip().upper():
        reasons.append("ACCOUNT_CURRENCY_NOT_SUPPORTED")

    probability_values = (
        proposal.proposer_probability,
        proposal.critic_probability,
        proposal.confidence_lower_bound,
        proposal.volatility_percentile,
        proposal.debate_elapsed_ms,
        proposal.additional_cost,
    )
    if not all(_number(v) for v in probability_values):
        reasons.append("PROPOSAL_NON_FINITE_OR_NON_NUMERIC")
    else:
        for label, p in (
            ("PROPOSER", proposal.proposer_probability),
            ("CRITIC", proposal.critic_probability),
            ("LOWER_BOUND", proposal.confidence_lower_bound),
        ):
            if p < config.min_probability or p > config.max_probability:
                reasons.append(f"{label}_PROBABILITY_OUT_OF_POLICY_BAND")
        if proposal.confidence_lower_bound > min(proposal.proposer_probability, proposal.critic_probability):
            reasons.append("CONFIDENCE_LOWER_BOUND_INCONSISTENT")
        if abs(proposal.proposer_probability - proposal.critic_probability) > config.max_probability_disagreement:
            reasons.append("PROBABILITY_DISAGREEMENT_TOO_WIDE")
        if not 0 <= proposal.volatility_percentile <= 1:
            reasons.append("VOLATILITY_PERCENTILE_OUT_OF_RANGE")
        elif proposal.volatility_percentile >= config.max_volatility_percentile:
            reasons.append("VOLATILITY_REGIME_OUT_OF_TRAINING_ENVELOPE")
        if proposal.debate_elapsed_ms < 0:
            reasons.append("DEBATE_LATENCY_INVALID")
        elif proposal.debate_elapsed_ms >= config.max_debate_elapsed_ms:
            reasons.append("DEBATE_DEADLINE_EXCEEDED")
        if proposal.additional_cost < 0:
            reasons.append("ADDITIONAL_COST_INVALID")
    if not isinstance(proposal.calibrated, bool) or not proposal.calibrated:
        reasons.append("PROBABILITY_MODEL_UNCALIBRATED")

    if _number(account.equity) and _number(account.daily_peak_equity) and account.daily_peak_equity > 0 and account.equity > 0:
        drawdown = (account.daily_peak_equity - account.equity) / account.daily_peak_equity
        if drawdown >= config.max_daily_drawdown_fraction:
            reasons.append("DAILY_DRAWDOWN_CIRCUIT_BREAKER")

    if reasons:
        return _blocked(*reasons)

    p = min(proposal.proposer_probability, proposal.critic_probability, proposal.confidence_lower_bound)
    break_even = break_even_probability(
        ask_price=q.ask_price,
        payout_total=q.payout_total,
        additional_cost=proposal.additional_cost,
    )
    ev = expected_value(
        ask_price=q.ask_price,
        payout_total=q.payout_total,
        win_probability=p,
        additional_cost=proposal.additional_cost,
    )
    max_loss = q.ask_price + proposal.additional_cost
    ev_ratio = ev / max_loss
    win_net = q.payout_total - max_loss
    if win_net <= 0:
        return DebateDecision(
            action=DebateAction.REJECT,
            reasons=("NON_POSITIVE_NET_WIN",),
            conservative_probability=p,
            break_even_probability=break_even,
            expected_value=ev,
            ev_per_risk_dollar=ev_ratio,
        )
    if p <= break_even:
        return DebateDecision(
            action=DebateAction.REJECT,
            reasons=("WIN_PROBABILITY_AT_OR_BELOW_BREAK_EVEN",),
            conservative_probability=p,
            break_even_probability=break_even,
            expected_value=ev,
            ev_per_risk_dollar=ev_ratio,
        )
    if ev_ratio <= config.min_ev_per_risk_dollar + 1e-12:
        return DebateDecision(
            action=DebateAction.REJECT,
            reasons=("EV_BELOW_REQUIRED_BUFFER",),
            conservative_probability=p,
            break_even_probability=break_even,
            expected_value=ev,
            ev_per_risk_dollar=ev_ratio,
        )

    net_odds = win_net / max_loss
    full_kelly = p - (1.0 - p) / net_odds
    half_kelly = max(0.0, full_kelly / 2.0)
    risk_budget = _floor_cents(account.equity * min(half_kelly, config.max_trade_risk_fraction))
    recommended = min(
        max(0.0, _floor_cents(risk_budget - proposal.additional_cost)),
        _floor_cents(account.equity * config.max_trade_risk_fraction),
    )

    common = dict(
        conservative_probability=p,
        break_even_probability=break_even,
        expected_value=ev,
        ev_per_risk_dollar=ev_ratio,
        full_kelly_fraction=full_kelly,
        half_kelly_fraction=half_kelly,
        maximum_risk_budget=risk_budget,
        recommended_stake_for_requote=recommended,
    )
    if recommended < config.minimum_stake:
        return DebateDecision(
            action=DebateAction.REJECT,
            reasons=("KELLY_RISK_BUDGET_BELOW_MINIMUM_STAKE",),
            **common,
        )
    # A Deriv proposal is priced for its requested terms. A smaller stake needs a
    # fresh proposal and new debate; never reuse the old proposal_id.
    if q.ask_price > recommended + 0.009:
        return DebateDecision(
            action=DebateAction.WAIT,
            reasons=("REQUOTE_AT_RECOMMENDED_STAKE_AND_REEVALUATE",),
            **common,
        )
    if max_loss > account.equity * config.max_trade_risk_fraction + 0.009:
        return DebateDecision(
            action=DebateAction.REJECT,
            reasons=("MAX_TRADE_RISK_FRACTION_EXCEEDED",),
            **common,
        )
    return DebateDecision(
        action=DebateAction.APPROVE_RESEARCH_ONLY,
        reasons=("POSITIVE_EV_AND_RISK_CHECKS_PASSED_RESEARCH_ONLY",),
        **common,
    )


def realized_reward(*, ask_price: float, payout_total: float, won: bool, equity_before: float) -> float:
    """Outcome-based RL reward in equity units; never uses the model's prediction."""
    if not _number(ask_price) or not _number(payout_total) or not _number(equity_before):
        raise ValueError("REWARD_INPUT_NON_FINITE_OR_NON_NUMERIC")
    if ask_price <= 0 or payout_total <= 0 or equity_before <= 0:
        raise ValueError("REWARD_INPUT_OUT_OF_RANGE")
    pnl = (payout_total - ask_price) if won else -ask_price
    return pnl / equity_before
