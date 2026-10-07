"""Leakage-safe intra-bar timing features."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class BarTiming:
    open_ts: float
    high_ts: float
    low_ts: float
    close_ts: float

def timing_features(t: BarTiming, *, require_completed: bool = True) -> dict[str, float]:
    o,h,l,c = map(float, (t.open_ts,t.high_ts,t.low_ts,t.close_ts))
    if not all(isfinite(x) for x in (o,h,l,c)) or not o < c:
        raise ValueError("invalid bar timing")
    if require_completed and not (h <= c and l <= c):
        raise ValueError("high/low timestamps must be known only after bar close")
    if not (o <= h <= c and o <= l <= c):
        raise ValueError("extreme timestamps must fall inside bar")
    d=c-o; hp=(h-o)/d; lp=(l-o)/d
    return {"high_time_position":hp,"low_time_position":lp,"high_before_low":float(h<l),
            "extreme_time_gap":abs(hp-lp),"time_to_high":hp,"time_to_low":lp}
