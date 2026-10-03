from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from .intraday_bias_measurement import ForwardObservation, calculate_statistics

@dataclass(frozen=True)
class CostModel:
    proportional_cost: float = 0.0
    fixed_cost_return: float = 0.0
    slippage_return: float = 0.0

    def adjusted_returns(self, observations: Sequence[ForwardObservation]) -> list[float]:
        friction = self.proportional_cost + self.fixed_cost_return + self.slippage_return
        if friction < 0:
            raise ValueError("costs cannot be negative")
        return [x.raw_return - friction for x in observations]

def cost_adjusted_statistics(observations: Sequence[ForwardObservation], model: CostModel):
    return calculate_statistics(model.adjusted_returns(observations))
