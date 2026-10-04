from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class TradeEconomics:
    probability: float
    average_win: float
    average_loss: float
    execution_cost: float = 0.0
    slippage_cost: float = 0.0
    quote_cost: float = 0.0

    def validate(self) -> tuple[bool, str]:
        values = (
            self.probability,
            self.average_win,
            self.average_loss,
            self.execution_cost,
            self.slippage_cost,
            self.quote_cost,
        )
        if not all(isfinite(float(value)) for value in values):
            return False, "ECONOMICS_NON_FINITE"
        if not 0.0 <= self.probability <= 1.0:
            return False, "ECONOMICS_PROBABILITY_INVALID"
        if self.average_win <= 0.0:
            return False, "ECONOMICS_AVERAGE_WIN_INVALID"
        if self.average_loss <= 0.0:
            return False, "ECONOMICS_AVERAGE_LOSS_INVALID"
        if min(self.execution_cost, self.slippage_cost, self.quote_cost) < 0.0:
            return False, "ECONOMICS_COST_INVALID"
        return True, "VALID"

    @property
    def expected_value(self) -> float:
        return (
            self.probability * self.average_win
            - (1.0 - self.probability) * self.average_loss
            - self.execution_cost
            - self.slippage_cost
            - self.quote_cost
        )

    def gate(self) -> tuple[bool, str]:
        valid, reason = self.validate()
        if not valid:
            return False, reason
        if not isfinite(self.expected_value):
            return False, "EXPECTED_VALUE_NON_FINITE"
        if self.expected_value <= 0.0:
            return False, "EXPECTED_VALUE_NON_POSITIVE"
        return True, "EXPECTED_VALUE_POSITIVE"
