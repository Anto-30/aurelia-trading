from dataclasses import dataclass
from .models import CapitalSnapshot
@dataclass(frozen=True)
class ReconciliationResult: healthy:bool; difference:float; reason:str
class Reconciler:
 def __init__(self,tolerance=.01): self.tolerance=tolerance
 def compare(self,*,broker:CapitalSnapshot,prior_authoritative_balance:float,explainable_delta:float=0.0):
  difference=broker.available_balance-prior_authoritative_balance-explainable_delta; healthy=abs(difference)<=self.tolerance
  return ReconciliationResult(healthy,difference,"RECONCILED" if healthy else "CAPITAL_MISMATCH")
