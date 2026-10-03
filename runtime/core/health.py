from dataclasses import dataclass,field
from datetime import datetime,timezone
@dataclass
class HealthSnapshot:
 process_heartbeat:datetime
 broker_session:bool=False; market_data_fresh:bool=False; capital_fresh:bool=False; ledger_healthy:bool=False; reconciliation_healthy:bool=False; kill_switch_off:bool=False; executor_lease_valid:bool=True; resource_ok:bool=True; dependencies_ok:bool=True; critical_unknowns:set[str]=field(default_factory=set)
 def liveness(self): return (datetime.now(timezone.utc)-self.process_heartbeat).total_seconds()<30
 def readiness(self): return self.liveness() and self.dependencies_ok and self.resource_ok and self.executor_lease_valid and not self.critical_unknowns
 def can_open_new_exposure(self): return self.readiness() and self.broker_session and self.market_data_fresh and self.capital_fresh and self.ledger_healthy and self.reconciliation_healthy and self.kill_switch_off
