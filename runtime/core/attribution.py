from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeAttribution:
    decision_id: str
    strategy_outcome: str
    execution_outcome: str
    broker_outcome: str
    capital_outcome: str
    realized_pnl: float | None = None
    net_cost: float | None = None

    def complete(self) -> bool:
        return all(bool(v) for v in (
            self.decision_id,
            self.strategy_outcome,
            self.execution_outcome,
            self.broker_outcome,
            self.capital_outcome,
        ))
