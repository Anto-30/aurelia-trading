from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class DataIntegrityResult:
    valid:bool
    reason_codes:tuple[str,...]

def validate_tick_sequence(previous_epoch:int|None,current_epoch:int,previous_quote:float|None,current_quote:float)->DataIntegrityResult:
    reasons=[]
    if current_epoch<=0: reasons.append("INVALID_TIMESTAMP")
    if previous_epoch is not None and current_epoch<previous_epoch: reasons.append("OUT_OF_ORDER_TICK")
    if previous_quote is not None and current_quote<0: reasons.append("INVALID_QUOTE")
    if current_quote!=current_quote: reasons.append("NAN_QUOTE")
    return DataIntegrityResult(not reasons,tuple(reasons))
