from __future__ import annotations
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class ResourceBudget:
    orders_per_hour:int=120
    broker_requests_per_minute:int=300
    reconnects_per_hour:int=60
    cpu_fraction:float=0.90
    memory_fraction:float=0.90

@dataclass
class ResourceUsage:
    orders:int=0
    broker_requests:int=0
    reconnects:int=0
    cpu_fraction:float=0.0
    memory_fraction:float=0.0
    def within(self,budget:ResourceBudget)->bool:
        return (0<=self.orders<=budget.orders_per_hour and
                0<=self.broker_requests<=budget.broker_requests_per_minute and
                0<=self.reconnects<=budget.reconnects_per_hour and
                isfinite(self.cpu_fraction) and isfinite(self.memory_fraction) and
                0<=self.cpu_fraction<=budget.cpu_fraction and
                0<=self.memory_fraction<=budget.memory_fraction)
