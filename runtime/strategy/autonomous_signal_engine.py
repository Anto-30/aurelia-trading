from __future__ import annotations

"""AURELIA's deterministic research signal hunter.

This module is deliberately upstream of the capital plane. It continuously
turns fresh Deriv ticks into auditable research candidates, but it cannot
authorize, size, submit, or release a live order. A candidate is executable
only after the existing AURELIA qualification/calibration/control chain
produces a separate DECISION_PROPOSAL and the capital executor authorizes it.
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite, log, sqrt
from typing import Any


@dataclass(frozen=True)
class SignalCandidate:
    symbol: str
    direction: str
    score: float
    probability: float
    probability_status: str
    quote: float
    observed_ticks: int
    created_at: datetime
    rationale_codes: tuple[str, ...]


class AutonomousSignalHunter:
    def __init__(
        self,
        *,
        window: int = 64,
        min_observations: int = 20,
        threshold: float = 1.5,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.window = max(8, int(window))
        self.min_observations = max(8, int(min_observations))
        self.threshold = max(0.1, float(threshold))
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self._prices: dict[str, deque[float]] = {}
        self._last_emitted: dict[str, datetime] = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def observe(self, *, symbol: str, quote: float, received_at: datetime | None = None) -> SignalCandidate | None:
        if not symbol or not isfinite(quote) or quote <= 0:
            return None
        now = received_at or self._now()
        if now.tzinfo is None:
            return None

        prices = self._prices.setdefault(symbol, deque(maxlen=self.window))
        prices.append(float(quote))
        if len(prices) < self.min_observations:
            return None

        prior = prices[-2]
        if prior <= 0:
            return None
        returns = [log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
        if not returns:
            return None

        mean = sum(returns) / len(returns)
        variance = sum((x - mean) ** 2 for x in returns) / max(1, len(returns) - 1)
        volatility = sqrt(max(variance, 0.0))
        if not isfinite(volatility) or volatility <= 0:
            return None

        score = returns[-1] / volatility
        if not isfinite(score) or abs(score) < self.threshold:
            return None

        last = self._last_emitted.get(symbol)
        if last is not None and (now - last).total_seconds() < self.cooldown_seconds:
            return None

        direction = "CALL" if score > 0 else "PUT"
        # This is intentionally an uncalibrated research confidence. It is
        # never presented to the capital plane as a calibrated probability.
        probability = min(0.75, max(0.55, 0.55 + 0.20 * min(abs(score) / 4.0, 1.0)))
        candidate = SignalCandidate(
            symbol=symbol,
            direction=direction,
            score=score,
            probability=probability,
            probability_status="UNCALIBRATED_RESEARCH_ONLY",
            quote=float(quote),
            observed_ticks=len(prices),
            created_at=now,
            rationale_codes=("TICK_RETURN_SHOCK", "VOL_NORMALIZED", "RESEARCH_ONLY"),
        )
        self._last_emitted[symbol] = now
        return candidate

    def as_message_payload(self, candidate: SignalCandidate) -> dict[str, Any]:
        return {
            "symbol": candidate.symbol,
            "direction": candidate.direction,
            "score": candidate.score,
            "probability": candidate.probability,
            "probability_status": candidate.probability_status,
            "quote": candidate.quote,
            "observed_ticks": candidate.observed_ticks,
            "decision_time": candidate.created_at.isoformat(),
            "rationale_codes": list(candidate.rationale_codes),
            "capital_authority": False,
            "order_submission_permitted": False,
            "research_only": True,
        }
