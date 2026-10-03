from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class ClockIntegrity:
    system_utc:datetime
    broker_utc:datetime
    max_drift_seconds:float=2.0
    def valid(self)->bool:
        if self.system_utc.tzinfo is None or self.broker_utc.tzinfo is None: return False
        return abs((self.system_utc.astimezone(timezone.utc)-self.broker_utc.astimezone(timezone.utc)).total_seconds())<=self.max_drift_seconds

@dataclass(frozen=True)
class EventSequence:
    sequence:int
    occurred_at:datetime
    def monotonic_after(self,previous:"EventSequence")->bool:
        return self.sequence>previous.sequence and self.occurred_at>=previous.occurred_at
