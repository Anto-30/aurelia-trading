"""Execution-neutral research quality and post-trade assurance contracts."""
from __future__ import annotations

from dataclasses import dataclass
from math import inf, log, isfinite
from typing import Iterable, Sequence

@dataclass(frozen=True)
class CalibrationBucket:
    lower: float
    upper: float
    count: int
    mean_probability: float
    realized_rate: float

@dataclass(frozen=True)
class TradeAttribution:
    trade_id: str
    expected_entry: float
    actual_entry: float
    expected_exit: float
    actual_exit: float
    gross_pnl: float
    fees: float
    slippage_cost: float
    latency_ms: float

def brier_score(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probabilities and outcomes must be non-empty and equal length")
    if any(not isfinite(p) or p < 0 or p > 1 for p in probabilities):
        raise ValueError("probabilities must be in [0,1]")
    if any(y not in (0, 1) for y in outcomes):
        raise ValueError("outcomes must be binary")
    return sum((p-y) ** 2 for p, y in zip(probabilities, outcomes)) / len(probabilities)

def log_loss(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probabilities and outcomes must be non-empty and equal length")
    total = 0.0
    for p, y in zip(probabilities, outcomes):
        if y not in (0, 1) or not isfinite(p) or p < 0 or p > 1:
            raise ValueError("invalid probability or outcome")
        if (y == 1 and p == 0) or (y == 0 and p == 1):
            return inf
        total += -(y * log(p) + (1-y) * log(1-p))
    return total / len(probabilities)

def reliability_buckets(
    probabilities: Sequence[float],
    outcomes: Sequence[int],
    bucket_edges: Iterable[float] = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
) -> list[CalibrationBucket]:
    edges=list(bucket_edges)
    if len(edges) < 2 or any(a >= b for a,b in zip(edges, edges[1:])):
        raise ValueError("bucket edges must be strictly increasing")
    if len(probabilities) != len(outcomes):
        raise ValueError("length mismatch")
    result=[]
    for lo, hi in zip(edges, edges[1:]):
        xs=[(p,y) for p,y in zip(probabilities,outcomes) if lo <= p < hi or (hi == edges[-1] and p == hi)]
        if not xs:
            continue
        result.append(CalibrationBucket(lo, hi, len(xs), sum(p for p,_ in xs)/len(xs), sum(y for _,y in xs)/len(xs)))
    return result

def net_expectancy(gross_pnl: float | None, costs: float | None) -> float | None:
    if gross_pnl is None or costs is None:
        return None
    if not all(isfinite(v) for v in (gross_pnl, costs)):
        return None
    return gross_pnl - costs

def multiple_testing_status(trial_count: int, search_degrees_of_freedom: int, oos_reuse_count: int) -> str:
    if min(trial_count, search_degrees_of_freedom, oos_reuse_count) < 0:
        return "INVALID"
    if trial_count == 0:
        return "NO_TRIALS"
    return "ACCOUNTED" if oos_reuse_count == 0 else "REUSED_OOS"

def mean_probability_drift(baseline: Sequence[float], recent: Sequence[float], threshold: float) -> bool:
    if not baseline or not recent or threshold < 0:
        raise ValueError("invalid drift inputs")
    return abs(sum(baseline)/len(baseline) - sum(recent)/len(recent)) > threshold

def post_trade_net_pnl(attribution: TradeAttribution) -> float:
    return attribution.gross_pnl - attribution.fees - attribution.slippage_cost

def single_trade_may_promote_strategy(number_of_completed_trades: int) -> bool:
    return False
