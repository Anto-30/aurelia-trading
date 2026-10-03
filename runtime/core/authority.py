from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from math import isfinite
from .models import AuthorizationContext,CapitalSnapshot,Decision,OrderIntent,AccountIdentity,utc_now
MIN_PROBABILITY=0.55; MAX_PROBABILITY=0.75; EXECUTION_MINIMUM_STAKE=1.50
@dataclass(frozen=True)
class GateResult: allowed:bool; reason_codes:tuple[str,...]
def probability_is_valid(p): return isfinite(p) and MIN_PROBABILITY<=p<=MAX_PROBABILITY
def requested_stake_is_permitted(r,capital,minimum_stake=EXECUTION_MINIMUM_STAKE): return bool(isfinite(r) and r>=minimum_stake and r<=capital.available_balance and capital.is_valid())
def authorization_gate(*,decision,account,capital,config_hash,runtime_config_hash,kill_switch_off,risk_approved,firewall_approved,reconciliation_healthy,final_execution_authorization,live_trading_enabled,authorization_ttl_seconds=30.0):
 reasons=[]
 if account.account_type!="real": reasons.append("ACCOUNT_NOT_REAL")
 if account.loginid!=capital.account.loginid: reasons.append("ACCOUNT_IDENTITY_MISMATCH")
 if account.currency!=capital.currency: reasons.append("CURRENCY_MISMATCH")
 if not capital.is_valid(): reasons.append("CAPITAL_TRUTH_NOT_FRESH")
 if not probability_is_valid(decision.probability): reasons.append("PROBABILITY_OUTSIDE_HARD_POLICY")
 if not decision.strategy_hash: reasons.append("STRATEGY_HASH_MISSING")
 if config_hash!=runtime_config_hash: reasons.append("CONFIG_DIGEST_MISMATCH")
 if not requested_stake_is_permitted(decision.risk_requested_stake,capital): reasons.append("STAKE_NOT_AFFORDABLE_OR_BELOW_BROKER_MINIMUM")
 if not risk_approved: reasons.append("RISK_WARDEN_REJECTED")
 if not firewall_approved: reasons.append("EXECUTION_FIREWALL_REJECTED")
 if not kill_switch_off: reasons.append("KILL_SWITCH_ON")
 if not reconciliation_healthy: reasons.append("RECONCILIATION_UNHEALTHY")
 if not final_execution_authorization: reasons.append("FINAL_EXECUTION_AUTHORIZATION_FALSE")
 if not live_trading_enabled: reasons.append("LIVE_TRADING_DISABLED")
 if reasons: return GateResult(False,tuple(reasons)),None
 now=utc_now(); return GateResult(True,()),AuthorizationContext(decision,account,capital,config_hash,f"auth:{decision.decision_id}:{int(now.timestamp()*1000)}",now,now+timedelta(seconds=authorization_ttl_seconds),True,True,True,True,True)
def build_intent(context,*,proposal_id,mode="LIVE"):
 if not context.is_current() or not context.final_execution_authorization: raise RuntimeError("CANNOT_BUILD_UNAUTHORIZED_INTENT")
 d=context.decision; return OrderIntent(f"intent:{d.decision_id}",d.decision_id,context.account,d.symbol,d.direction,d.risk_requested_stake,utc_now(),d.strategy_hash,context.config_hash,mode,proposal_id)
