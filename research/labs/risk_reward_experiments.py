"""Research-only, cost-aware exit-policy comparison for normalized linear trade paths.

This module does not generate signals, size positions, authorize capital, or place
orders. A caller may use it only after an instrument-specific adapter maps prices
into signed R units using verified contract specifications. Fixed-payout contracts
are deliberately rejected by this path model: their payoff must be evaluated using
contract payout and settlement economics.

If stop and target are both touched in an OHLC bar and tick ordering is unavailable,
the stop wins. A gap through a stop fills at the bar open. Targets never receive
favourable gap improvement. Dynamic stop updates observed at a bar close take effect
on the next bar only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from random import Random
from statistics import mean
from typing import Literal, Sequence

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False

CostSource = Literal["OBSERVED", "BROKER_DOCUMENTED", "INFERRED", "STRESS_ASSUMPTION"]
_COST_SOURCES = frozenset({"OBSERVED", "BROKER_DOCUMENTED", "INFERRED", "STRESS_ASSUMPTION"})


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field.upper()}_INVALID")
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{field.upper()}_NON_FINITE")
    return value


def _aware_utc(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field.upper()}_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field.upper()}_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class NormalizedBar:
    """OHLC in signed initial-risk R units, normalized for the trade direction.

    The instrument adapter must calculate favourable high_r and adverse low_r
    correctly for both long and short positions using verified product mechanics.
    """
    timestamp_utc: str
    open_r: float
    high_r: float
    low_r: float
    close_r: float

    def validate(self) -> None:
        _aware_utc(self.timestamp_utc, "bar_timestamp_utc")
        o, h, lo, c = (
            _number(self.open_r, "open_r"), _number(self.high_r, "high_r"),
            _number(self.low_r, "low_r"), _number(self.close_r, "close_r"),
        )
        if lo > min(o, c) or h < max(o, c) or lo > h:
            raise ValueError("OHLC_R_INCONSISTENT")


@dataclass(frozen=True)
class CostComponent:
    """One nonnegative cost in account currency; embedded costs are not subtracted twice."""
    component_id: str
    name: str
    amount_cash: float
    currency: str
    source_kind: CostSource
    source_ref: str
    observed_at_utc: str
    embedded_in_fill: bool = False

    def validate(self, account_currency: str) -> None:
        if not self.component_id.strip() or not self.name.strip():
            raise ValueError("COST_COMPONENT_ID_OR_NAME_MISSING")
        if _number(self.amount_cash, "cost_amount_cash") < 0:
            raise ValueError("COST_AMOUNT_NEGATIVE")
        if self.currency.strip().upper() != account_currency.strip().upper():
            raise ValueError("COST_CURRENCY_MISMATCH")
        if self.source_kind not in _COST_SOURCES:
            raise ValueError("COST_SOURCE_KIND_INVALID")
        if not self.source_ref.strip():
            raise ValueError("COST_SOURCE_REFERENCE_MISSING")
        _aware_utc(self.observed_at_utc, "cost_observed_at_utc")


@dataclass(frozen=True)
class TradePath:
    """One eligible entry and its causally ordered future path."""
    signal_id: str
    strategy_id: str
    instrument_id: str
    timeframe: str
    regime: str
    entry_timestamp_utc: str
    initial_risk_cash: float
    account_currency: str
    payoff_model: str
    instrument_spec_ref: str
    data_hash: str
    bars: tuple[NormalizedBar, ...]
    cost_components: tuple[CostComponent, ...]
    costs_complete: bool
    unknown_cost_components: tuple[str, ...] = ()

    def validate(self) -> None:
        for field in ("signal_id", "strategy_id", "instrument_id", "timeframe", "regime",
                      "account_currency", "instrument_spec_ref", "data_hash"):
            if not str(getattr(self, field)).strip():
                raise ValueError(f"{field.upper()}_MISSING")
        if self.payoff_model != "LINEAR_R_PATH":
            raise ValueError("PAYOFF_MODEL_NOT_SUPPORTED_BY_R_PATH_ENGINE")
        if _number(self.initial_risk_cash, "initial_risk_cash") <= 0:
            raise ValueError("INITIAL_PLANNED_RISK_MUST_BE_POSITIVE")
        prior = _aware_utc(self.entry_timestamp_utc, "entry_timestamp_utc")
        if not self.bars:
            raise ValueError("TRADE_PATH_BARS_MISSING")
        for bar in self.bars:
            bar.validate()
            stamp = _aware_utc(bar.timestamp_utc, "bar_timestamp_utc")
            if stamp <= prior:
                raise ValueError("TRADE_PATH_BARS_NOT_STRICTLY_CHRONOLOGICAL")
            prior = stamp
        ids: set[str] = set()
        for component in self.cost_components:
            component.validate(self.account_currency)
            if component.component_id in ids:
                raise ValueError("DUPLICATE_COST_COMPONENT_ID")
            ids.add(component.component_id)
        if self.costs_complete and (not self.cost_components or self.unknown_cost_components):
            raise ValueError("COSTS_CLAIMED_COMPLETE_WITHOUT_FULL_EVIDENCE")
        if any(not str(item).strip() for item in self.unknown_cost_components):
            raise ValueError("UNKNOWN_COST_COMPONENT_NAME_EMPTY")

    @property
    def known_cost_cash(self) -> float:
        return sum(c.amount_cash for c in self.cost_components if not c.embedded_in_fill)

    @property
    def known_cost_r(self) -> float:
        return self.known_cost_cash / float(self.initial_risk_cash)


@dataclass(frozen=True)
class ExitPolicy:
    policy_id: str
    target_r: float | None = None
    break_even_trigger_r: float | None = None
    trailing_activation_r: float | None = None
    trailing_distance_r: float | None = None
    time_stop_bars: int | None = None

    def validate(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("EXIT_POLICY_ID_MISSING")
        if all(x is None for x in (self.target_r, self.break_even_trigger_r,
                                   self.trailing_activation_r, self.trailing_distance_r,
                                   self.time_stop_bars)):
            raise ValueError("EXIT_POLICY_HAS_NO_EXIT_RULE")
        for field in ("target_r", "break_even_trigger_r", "trailing_activation_r", "trailing_distance_r"):
            value = getattr(self, field)
            if value is not None and _number(value, field) <= 0:
                raise ValueError(f"{field.upper()}_MUST_BE_POSITIVE")
        if (self.trailing_activation_r is None) != (self.trailing_distance_r is None):
            raise ValueError("TRAILING_POLICY_REQUIRES_ACTIVATION_AND_DISTANCE")
        if self.time_stop_bars is not None and (
            isinstance(self.time_stop_bars, bool) or not isinstance(self.time_stop_bars, int)
            or self.time_stop_bars < 1
        ):
            raise ValueError("TIME_STOP_BARS_INVALID")


def standard_exit_policies() -> tuple[ExitPolicy, ...]:
    """Candidate grid only; no listed ratio is assumed profitable."""
    ratios = (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0)
    fixed = tuple(ExitPolicy(f"FIXED_{r:g}R", target_r=r) for r in ratios)
    return fixed + (
        ExitPolicy("FIXED_2R_BE_AT_1R", target_r=2.0, break_even_trigger_r=1.0),
        ExitPolicy("TRAIL_AFTER_1R_DISTANCE_1R", trailing_activation_r=1.0, trailing_distance_r=1.0),
        ExitPolicy("TIME_STOP_10_BARS", time_stop_bars=10),
    )


@dataclass(frozen=True)
class TradeResult:
    signal_id: str
    policy_id: str
    exit_timestamp_utc: str
    exit_reason: str
    exit_r: float
    gross_cash: float
    duration_bars: int
    max_adverse_excursion_r: float
    max_favourable_excursion_r: float
    known_cost_r: float
    known_cost_cash: float
    costs_complete: bool
    net_r: float | None
    net_cash: float | None


def simulate_exit(path: TradePath, policy: ExitPolicy) -> TradeResult:
    path.validate()
    policy.validate()
    stop_r = -1.0
    best_r = 0.0
    exit_r: float | None = None
    exit_idx = len(path.bars) - 1
    exit_reason = "PATH_END"
    for idx, bar in enumerate(path.bars):
        best_r = max(best_r, float(bar.high_r))
        target = policy.target_r
        if float(bar.open_r) <= stop_r:
            exit_r, exit_idx, exit_reason = float(bar.open_r), idx, "STOP_GAP"
            break
        if target is not None and float(bar.open_r) >= target:
            exit_r, exit_idx, exit_reason = target, idx, "TARGET"
            break
        stop_touched = float(bar.low_r) <= stop_r
        target_touched = target is not None and float(bar.high_r) >= target
        if stop_touched:
            exit_r, exit_idx, exit_reason = stop_r, idx, "STOP"
            break
        if target_touched:
            exit_r, exit_idx, exit_reason = target, idx, "TARGET"
            break
        if policy.break_even_trigger_r is not None and best_r >= policy.break_even_trigger_r:
            stop_r = max(stop_r, 0.0)
        if policy.trailing_activation_r is not None and best_r >= policy.trailing_activation_r:
            stop_r = max(stop_r, best_r - float(policy.trailing_distance_r))
        if policy.time_stop_bars is not None and idx + 1 >= policy.time_stop_bars:
            exit_r, exit_idx, exit_reason = float(bar.close_r), idx, "TIME_STOP"
            break
        if idx == len(path.bars) - 1:
            exit_r, exit_idx, exit_reason = float(bar.close_r), idx, "PATH_END"
    if exit_r is None:
        raise RuntimeError("EXIT_RESULT_UNRESOLVED")
    used = path.bars[:exit_idx + 1]
    max_favourable = max(0.0, max(float(b.high_r) for b in used))
    max_adverse = max(0.0, -min(float(b.low_r) for b in used))
    risk_cash = float(path.initial_risk_cash)
    cost_cash = path.known_cost_cash
    cost_r = cost_cash / risk_cash
    gross_cash = exit_r * risk_cash
    net_r = exit_r - cost_r if path.costs_complete else None
    net_cash = gross_cash - cost_cash if path.costs_complete else None
    return TradeResult(
        signal_id=path.signal_id, policy_id=policy.policy_id,
        exit_timestamp_utc=path.bars[exit_idx].timestamp_utc, exit_reason=exit_reason,
        exit_r=exit_r, gross_cash=gross_cash, duration_bars=exit_idx + 1,
        max_adverse_excursion_r=max_adverse, max_favourable_excursion_r=max_favourable,
        known_cost_r=cost_r, known_cost_cash=cost_cash, costs_complete=path.costs_complete,
        net_r=net_r, net_cash=net_cash,
    )


def _profit_factor(values: Sequence[float]) -> float | None:
    gains = sum(x for x in values if x > 0)
    losses = -sum(x for x in values if x < 0)
    return gains / losses if losses > 0 else None


def _max_drawdown(values: Sequence[float]) -> float | None:
    if not values:
        return None
    equity = peak = drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown


def block_bootstrap_mean_ci(
    values: Sequence[float], *, confidence: float = 0.95, block_length: int = 5,
    replicates: int = 1000, seed: int = 20261014,
) -> tuple[float, float] | None:
    """Circular moving-block bootstrap CI; dependence beyond block length remains unmodelled."""
    xs = [_number(x, "bootstrap_value") for x in values]
    if len(xs) < 2:
        return None
    if not 0 < confidence < 1 or isinstance(block_length, bool) or block_length < 1:
        raise ValueError("BOOTSTRAP_PARAMETERS_INVALID")
    if isinstance(replicates, bool) or replicates < 100:
        raise ValueError("BOOTSTRAP_REPLICATES_TOO_SMALL")
    rng = Random(seed)
    n = len(xs)
    estimates: list[float] = []
    for _ in range(replicates):
        sample: list[float] = []
        while len(sample) < n:
            start = rng.randrange(n)
            sample.extend(xs[(start + j) % n] for j in range(block_length))
        estimates.append(mean(sample[:n]))
    estimates.sort()
    alpha = (1.0 - confidence) / 2.0
    lo = min(len(estimates) - 1, max(0, int(alpha * len(estimates))))
    hi = min(len(estimates) - 1, max(0, int((1.0 - alpha) * len(estimates)) - 1))
    return estimates[lo], estimates[hi]


def compare_exit_policies(
    paths: Sequence[TradePath], policies: Sequence[ExitPolicy], *,
    bootstrap_replicates: int = 1000, bootstrap_block_length: int = 5,
    bootstrap_seed: int = 20261014,
) -> dict[str, dict[str, object]]:
    """Compare candidate exits on the exact same path set; no capital authority."""
    if not paths:
        raise ValueError("TRADE_PATHS_REQUIRED")
    if not policies:
        raise ValueError("EXIT_POLICIES_REQUIRED")
    signal_ids = [p.signal_id for p in paths]
    if len(signal_ids) != len(set(signal_ids)):
        raise ValueError("DUPLICATE_ENTRY_SIGNAL_ID")
    policy_ids = [p.policy_id for p in policies]
    if len(policy_ids) != len(set(policy_ids)):
        raise ValueError("DUPLICATE_EXIT_POLICY_ID")
    for path in paths:
        path.validate()
    output: dict[str, dict[str, object]] = {}
    for policy in policies:
        policy.validate()
        trades = [simulate_exit(path, policy) for path in paths]
        gross = [t.exit_r for t in trades]
        complete = all(t.costs_complete for t in trades)
        known_net = [t.exit_r - t.known_cost_r for t in trades]
        net = [float(t.net_r) for t in trades] if complete else []
        ci = block_bootstrap_mean_ci(
            net, block_length=bootstrap_block_length, replicates=bootstrap_replicates,
            seed=bootstrap_seed,
        ) if complete else None
        net_cash = [float(t.net_cash) for t in trades] if complete else []
        output[policy.policy_id] = {
            "policy_id": policy.policy_id,
            "trade_count": len(trades),
            "entry_signal_ids": signal_ids,
            "gross_expectancy_r": mean(gross),
            "gross_expectancy_cash": mean(t.gross_cash for t in trades),
            "gross_win_rate": sum(x > 0 for x in gross) / len(gross),
            "gross_profit_factor": _profit_factor(gross),
            "net_expectancy_r": mean(net) if net else None,
            "net_expectancy_cash": mean(net_cash) if net_cash else None,
            "net_win_rate": sum(x > 0 for x in net) / len(net) if net else None,
            "net_profit_factor": _profit_factor(net) if net else None,
            "max_net_drawdown_r": _max_drawdown(net) if net else None,
            "max_net_drawdown_cash": _max_drawdown(net_cash) if net_cash else None,
            "mean_known_cost_r": mean(t.known_cost_r for t in trades),
            "cost_complete_trade_count": sum(t.costs_complete for t in trades),
            "cost_coverage": sum(t.costs_complete for t in trades) / len(trades),
            "known_cost_only_expectancy_r_not_fully_net": mean(known_net),
            "net_expectancy_block_bootstrap_ci95_r": list(ci) if ci is not None else None,
            "status": "COST_COMPLETE_RESEARCH_METRICS" if complete else "COST_INCOMPLETE",
            "trades": [t.__dict__ for t in trades],
        }
    return output
