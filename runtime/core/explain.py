from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any
import json

@dataclass(frozen=True)
class DecisionExplanation:
    decision_id:str
    timestamp_utc:str
    strategy_id:str
    strategy_version:str
    strategy_hash:str
    symbol:str
    probability:float
    probability_valid:bool
    requested_stake:float
    risk_status:str
    capital_status:str
    authorization_status:str
    final_decision:str
    reason_codes:tuple[str,...]
    inputs_hash:str

    def to_dict(self)->dict[str,Any]: return asdict(self)
    def to_json(self)->str: return json.dumps(self.to_dict(),sort_keys=True)
