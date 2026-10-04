from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


@dataclass
class LatencyMetrics:
    samples_ms: dict[str, list[float]] = field(default_factory=dict)

    def observe(self, stage: str, milliseconds: float) -> None:
        if milliseconds < 0:
            raise ValueError("NEGATIVE_LATENCY")
        values = self.samples_ms.setdefault(stage, [])
        values.append(float(milliseconds))
        if len(values) > 1000:
            del values[:-1000]

    def percentile(self, stage: str, percentile: float) -> float | None:
        values = sorted(self.samples_ms.get(stage, ()))
        if not values:
            return None
        if not 0 <= percentile <= 100:
            raise ValueError("INVALID_PERCENTILE")
        if percentile == 50:
            return float(median(values))
        rank = (len(values) - 1) * percentile / 100.0
        lower = int(rank)
        upper = min(lower + 1, len(values) - 1)
        fraction = rank - lower
        return values[lower] + (values[upper] - values[lower]) * fraction

    def summary(self, stage: str) -> dict[str, float | int | None]:
        values = self.samples_ms.get(stage, ())
        return {
            "count": len(values),
            "p50_ms": self.percentile(stage, 50),
            "p95_ms": self.percentile(stage, 95),
            "p99_ms": self.percentile(stage, 99),
        }
