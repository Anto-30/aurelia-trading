"""Research-only liquidity sweep and signal-conflict rules.

No broker interface. A sweep is confirmed only by a completed bar closing back
through a pre-existing, externally identified level; this module never discovers
pivots from future bars.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math


@dataclass(frozen=True)
class SweepLevel:
    price: float
    kind: str
    observed_at: datetime
    source: str

    def validate(self) -> None:
        if not math.isfinite(self.price):
            raise ValueError("level price must be finite")
        if self.kind not in {"prior_high", "prior_low", "equal_highs", "equal_lows", "session_high", "session_low"}:
            raise ValueError("unsupported sweep level kind")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("level timestamp must be timezone-aware")
        if not self.source.strip():
            raise ValueError("level source is required")


def liquidity_sweep_candidate(*, bar_start: datetime, bar_end: datetime, open_price: float,
                              high: float, low: float, close: float, complete: bool,
                              level: SweepLevel, decision_time: datetime,
                              min_excursion: float = 0.0) -> dict[str, object]:
    """Return a candidate only for a completed excursion and close back across level."""
    level.validate()
    for name, stamp in (("bar_start", bar_start), ("bar_end", bar_end), ("decision_time", decision_time)):
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return {"strategy": "NO_TRADE", "direction": "NONE", "reason": f"{name} must be timezone-aware"}
    values = (open_price, high, low, close, min_excursion)
    if any(not math.isfinite(float(v)) for v in values) or min_excursion < 0:
        return {"strategy": "NO_TRADE", "direction": "NONE", "reason": "invalid price input"}
    if not complete or bar_end <= bar_start or bar_end > decision_time:
        return {"strategy": "NO_TRADE", "direction": "NONE", "reason": "bar incomplete or unavailable at decision time"}
    if level.observed_at >= bar_start:
        return {"strategy": "NO_TRADE", "direction": "NONE", "reason": "level was not known before sweep bar"}
    if low > min(open_price, close) or high < max(open_price, close) or low > high:
        return {"strategy": "NO_TRADE", "direction": "NONE", "reason": "invalid OHLC"}
    if level.kind in {"prior_high", "equal_highs", "session_high"}:
        excursion = high - level.price
        if excursion > min_excursion and close < level.price:
            return {"strategy": "LIQUIDITY_SWEEP", "direction": "SHORT", "reference": level.price,
                    "excursion": excursion, "reason": "high swept pre-existing level and completed close returned below"}
    else:
        excursion = level.price - low
        if excursion > min_excursion and close > level.price:
            return {"strategy": "LIQUIDITY_SWEEP", "direction": "LONG", "reference": level.price,
                    "excursion": excursion, "reason": "low swept pre-existing level and completed close returned above"}
    return {"strategy": "NO_TRADE", "direction": "NONE", "reason": "sweep and close-back-through not confirmed"}


def resolve_signal_conflict(orb: dict[str, object], sweep: dict[str, object]) -> dict[str, object]:
    """Conservative policy: conflicting directional candidates always resolve to NO_TRADE."""
    def direction(signal: dict[str, object]) -> str:
        d = signal.get("direction", "NONE")
        return d if d in {"LONG", "SHORT"} and signal.get("strategy") != "NO_TRADE" else "NONE"
    a, b = direction(orb), direction(sweep)
    if a != "NONE" and b != "NONE" and a != b:
        return {"strategy": "NO_TRADE", "direction": "NONE", "reason": "conflicting ORB and sweep directions"}
    if a != "NONE" and b != "NONE":
        return {"strategy": "NO_TRADE", "direction": "NONE", "reason": "multiple active modules; precedence not validated"}
    if a != "NONE":
        return dict(orb)
    if b != "NONE":
        return dict(sweep)
    return {"strategy": "NO_TRADE", "direction": "NONE", "reason": "no valid candidate"}
