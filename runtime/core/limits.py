from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class ExecutionLimits:
    minimum_stake: float = 1.50
    maximum_stake: float | None = None

    def validate(self, stake: float, verified_balance: float) -> tuple[bool, str]:
        if not isfinite(stake) or stake <= 0:
            return False, "INVALID_STAKE"
        if stake < self.minimum_stake:
            return False, "STAKE_BELOW_BROKER_MINIMUM"
        if not isfinite(verified_balance) or verified_balance < 0:
            return False, "BALANCE_UNVERIFIED"
        if stake > verified_balance:
            return False, "STAKE_ABOVE_VERIFIED_AVAILABLE_BALANCE"
        if self.maximum_stake is not None and stake > self.maximum_stake:
            return False, "STAKE_ABOVE_DETERMINISTIC_MAXIMUM"
        return True, "PERMITTED"
