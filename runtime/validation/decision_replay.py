from dataclasses import dataclass
from runtime.core.events import sha256
from runtime.core.models import Decision
@dataclass(frozen=True)
class DecisionReplay: input_hash:str; output_hash:str; equivalent:bool
def decision_fingerprint(d:Decision):return sha256({"decision_id":d.decision_id,"strategy_id":d.strategy_id,"strategy_version":d.strategy_version,"strategy_hash":d.strategy_hash,"symbol":d.symbol,"direction":d.direction,"probability":d.probability,"decision_time":d.decision_time.isoformat(),"market_snapshot_hash":d.market_snapshot_hash,"risk_requested_stake":d.risk_requested_stake,"rationale_codes":list(d.rationale_codes)})
def replay_equivalent(a,b):
 x,y=decision_fingerprint(a),decision_fingerprint(b);return DecisionReplay(x,y,x==y)
