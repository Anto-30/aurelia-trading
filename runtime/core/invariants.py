from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from .models import AuthorizationContext,OrderIntent
@dataclass(frozen=True)
class InvariantViolation: code:str; detail:str
def check_pre_submission_invariants(*,context, intent, kill_switch_off, broker_state_unknown, single_writer_token_valid):
 v=[]
 if not context.final_execution_authorization: v.append(InvariantViolation("NO_FINAL_AUTH","final authorization is false"))
 if not context.is_current(): v.append(InvariantViolation("STALE_AUTHORIZATION","authorization lease expired"))
 if not kill_switch_off: v.append(InvariantViolation("KILL_SWITCH","kill switch active"))
 if broker_state_unknown: v.append(InvariantViolation("BROKER_UNKNOWN","broker outcome unresolved"))
 if not single_writer_token_valid: v.append(InvariantViolation("STALE_EXECUTOR_FENCE","fencing token invalid"))
 if intent.proposal_id is None: v.append(InvariantViolation("PROPOSAL_ID_MISSING","broker proposal ID required"))
 if intent.stake<=0 or not isfinite(intent.stake): v.append(InvariantViolation("INVALID_STAKE","invalid stake"))
 return v
def no_duplicate_economic_effects(n): return n<=1
def no_order_after_kill_switch(submitted,kill_switch_on_at_submission): return not(submitted and kill_switch_on_at_submission)
def no_research_capital_authority(capital_authority): return capital_authority is False
