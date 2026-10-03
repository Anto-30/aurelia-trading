from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum


class IncidentSeverity(IntEnum):
    P0 = 0
    P1 = 1
    P2 = 2
    P3 = 3
    P4 = 4


@dataclass(frozen=True)
class Incident:
    incident_id: str
    severity: IncidentSeverity
    code: str
    detected_at: datetime
    correlation_id: str
    requires_capital_protection: bool
    resolved: bool = False

    @property
    def utc(self) -> datetime:
        return self.detected_at.astimezone(timezone.utc)


def severity_for(code: str) -> IncidentSeverity:
    if code.startswith(("CAPITAL_", "BROKER_UNKNOWN", "UNAUTHORIZED_", "DUPLICATE_")):
        return IncidentSeverity.P0
    if code.startswith(("EXECUTION_", "RECONCILIATION_")):
        return IncidentSeverity.P1
    if code.startswith(("RUNTIME_", "DATA_")):
        return IncidentSeverity.P2
    if code.startswith("RESEARCH_"):
        return IncidentSeverity.P3
    return IncidentSeverity.P4
