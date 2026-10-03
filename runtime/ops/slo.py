from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafetySLO:
    fault_to_protection_seconds: float
    recovery_to_verified_seconds: float | None
    target_fault_to_protection_seconds: float = 5.0
    target_recovery_to_verified_seconds: float = 300.0

    @property
    def protection_target_met(self) -> bool:
        return self.fault_to_protection_seconds <= self.target_fault_to_protection_seconds

    @property
    def recovery_target_met(self) -> bool:
        return self.recovery_to_verified_seconds is not None and self.recovery_to_verified_seconds <= self.target_recovery_to_verified_seconds
