"""Minimal financial-event state machine for assurance testing only."""
from __future__ import annotations

from dataclasses import dataclass

VALID_TRANSITIONS = {
    "CREATED": {"AUTHORIZED", "REJECTED"},
    "AUTHORIZED": {"SUBMITTED", "REJECTED", "EXPIRED"},
    "SUBMITTED": {"ACKNOWLEDGED", "UNKNOWN", "REJECTED"},
    "ACKNOWLEDGED": {"RESULT_PENDING", "REJECTED"},
    "RESULT_PENDING": {"SETTLED", "UNKNOWN", "REJECTED"},
    "UNKNOWN": {"RECOVERY"},
    "RECOVERY": {"CONFIRMED", "REJECTED"},
    "CONFIRMED": {"SETTLED"},
    "SETTLED": {"RECONCILED"},
    "RECONCILED": set(),
    "REJECTED": set(),
    "EXPIRED": set(),
}


@dataclass
class ExecutionState:
    state: str = "CREATED"

    def transition(self, new_state: str) -> None:
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(f"Invalid execution transition: {self.state} -> {new_state}")
        self.state = new_state
