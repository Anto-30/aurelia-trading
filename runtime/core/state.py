from dataclasses import dataclass,field
from .models import RuntimeState
_ALLOWED={
 RuntimeState.BOOT:{RuntimeState.SELF_CHECK,RuntimeState.SHUTDOWN},
 RuntimeState.SELF_CHECK:{RuntimeState.BROKER_CONNECTING,RuntimeState.DEGRADED,RuntimeState.CAPITAL_PROTECTED},
 RuntimeState.BROKER_CONNECTING:{RuntimeState.BROKER_VERIFIED,RuntimeState.DEGRADED,RuntimeState.CAPITAL_PROTECTED},
 RuntimeState.BROKER_VERIFIED:{RuntimeState.MARKET_READY,RuntimeState.DEGRADED,RuntimeState.CAPITAL_PROTECTED},
 RuntimeState.MARKET_READY:{RuntimeState.DECISION_READY,RuntimeState.DEGRADED,RuntimeState.CAPITAL_PROTECTED},
 RuntimeState.DECISION_READY:{RuntimeState.AUTHORIZED,RuntimeState.HEALTHY,RuntimeState.CAPITAL_PROTECTED},
 RuntimeState.AUTHORIZED:{RuntimeState.EXECUTING,RuntimeState.DEGRADED,RuntimeState.CAPITAL_PROTECTED},
 RuntimeState.EXECUTING:{RuntimeState.SETTLING,RuntimeState.RECOVERY,RuntimeState.CAPITAL_PROTECTED},
 RuntimeState.SETTLING:{RuntimeState.RECONCILING,RuntimeState.RECOVERY,RuntimeState.CAPITAL_PROTECTED},
 RuntimeState.RECONCILING:{RuntimeState.HEALTHY,RuntimeState.VERIFIED,RuntimeState.RECOVERY,RuntimeState.CAPITAL_PROTECTED},
 RuntimeState.HEALTHY:{RuntimeState.DECISION_READY,RuntimeState.DEGRADED,RuntimeState.CAPITAL_PROTECTED,RuntimeState.SHUTDOWN},
 RuntimeState.DEGRADED:{RuntimeState.CAPITAL_PROTECTED,RuntimeState.RECOVERY,RuntimeState.SHUTDOWN},
 RuntimeState.CAPITAL_PROTECTED:{RuntimeState.RECOVERY,RuntimeState.SHUTDOWN},
 RuntimeState.RECOVERY:{RuntimeState.VERIFIED,RuntimeState.CAPITAL_PROTECTED,RuntimeState.SHUTDOWN},
 RuntimeState.VERIFIED:{RuntimeState.HEALTHY,RuntimeState.CAPITAL_PROTECTED,RuntimeState.SHUTDOWN},
 RuntimeState.SHUTDOWN:set(),}
@dataclass
class RuntimeStateMachine:
 state:RuntimeState=RuntimeState.BOOT
 history:list[tuple[RuntimeState,RuntimeState]]=field(default_factory=list)
 def transition(self,new_state):
  if new_state not in _ALLOWED[self.state]: raise ValueError(f"INVALID_RUNTIME_TRANSITION:{self.state.value}->{new_state.value}")
  old=self.state; self.state=new_state; self.history.append((old,new_state))
