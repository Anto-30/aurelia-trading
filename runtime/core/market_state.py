from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketDataState:
    symbol: str
    sequence: int
    epoch: int
    quote: float
    received_at_epoch: int

    def newer_than(self, previous: "MarketDataState") -> bool:
        return self.sequence > previous.sequence and self.epoch >= previous.epoch


def validate_market_update(previous: MarketDataState | None, current: MarketDataState) -> tuple[bool, str]:
    if current.sequence < 0 or current.epoch <= 0 or current.quote < 0:
        return False, "INVALID_MARKET_UPDATE"
    if previous and not current.newer_than(previous):
        return False, "OUT_OF_ORDER_MARKET_UPDATE"
    return True, "VALID"
