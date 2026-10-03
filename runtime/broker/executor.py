from __future__ import annotations
from dataclasses import dataclass
from runtime.core.authority import GateResult,authorization_gate,build_intent
from runtime.core.events import event_envelope
from runtime.core.fencing import ExecutionFence
from runtime.core.invariants import check_pre_submission_invariants
from runtime.core.idempotency import IdempotencyStore
from runtime.core.journal import AppendOnlyJournal
from runtime.core.ledger import InMemoryLedger
from runtime.core.models import AuthorizationContext,BrokerOutcome,CapitalSnapshot,Decision,LedgerEvent,OrderIntent,RuntimeState
from runtime.core.reconcile import Reconciler,ReconciliationResult
from runtime.core.state import RuntimeStateMachine
@dataclass
class ExecutionOutcome: allowed:bool; status:str; reasons:tuple[str,...]; intent_id:str|None=None; broker_transaction_id:str|None=None
class CapitalPlaneExecutor:
 def __init__(self,broker,*,journal,ledger,idempotency,fence,state,reconciler,source_hash,config_hash):
  self.broker=broker; self.journal=journal; self.ledger=ledger; self.idempotency=idempotency; self.fence=fence; self.state=state; self.reconciler=reconciler; self.source_hash=source_hash; self.config_hash=config_hash; self.kill_switch=True
 def _log(self,t,p): self.journal.append(event_envelope(event_type=t,event_id=f"{t}:{len(self.journal.read_all())+1}",correlation_id=p.get("intent_id") or p.get("decision_id") or t,payload=p,source_hash=self.source_hash,config_hash=self.config_hash))
 def activate_kill_switch(self,reason):
  self.kill_switch=True; self.fence.revoke(); self.state.transition(RuntimeState.CAPITAL_PROTECTED) if self.state.state not in {RuntimeState.CAPITAL_PROTECTED,RuntimeState.SHUTDOWN} and self.state.state in {RuntimeState.SELF_CHECK,RuntimeState.BROKER_CONNECTING,RuntimeState.BROKER_VERIFIED,RuntimeState.MARKET_READY,RuntimeState.DECISION_READY,RuntimeState.AUTHORIZED,RuntimeState.EXECUTING,RuntimeState.SETTLING,RuntimeState.RECONCILING,RuntimeState.HEALTHY} else None; self._log("KILL_SWITCH_ACTIVATED",{"reason":reason})
 async def authorize_and_build_intent(self,*,decision,capital,runtime_config_hash,account,risk_approved,firewall_approved,reconciliation_healthy,final_execution_authorization,live_trading_enabled,proposal_id=None,mode="LIVE"):
  gate,ctx=authorization_gate(decision=decision,account=account,capital=capital,config_hash=self.config_hash,runtime_config_hash=runtime_config_hash,kill_switch_off=not self.kill_switch,risk_approved=risk_approved,firewall_approved=firewall_approved,reconciliation_healthy=reconciliation_healthy,final_execution_authorization=final_execution_authorization,live_trading_enabled=live_trading_enabled)
  self._log("AUTHORIZATION_DECISION",{"decision_id":decision.decision_id,"allowed":gate.allowed,"reasons":gate.reason_codes})
  return (gate,None,None) if not gate.allowed or ctx is None else (gate,ctx,build_intent(ctx,proposal_id=proposal_id,mode=mode))
 async def execute(self,intent,context,fence_token):
  v=check_pre_submission_invariants(context=context,intent=intent,kill_switch_off=not self.kill_switch,broker_state_unknown=False,single_writer_token_valid=self.fence.valid(fence_token))
  if v: self._log("PRE_SUBMISSION_BLOCKED",{"intent_id":intent.intent_id,"reasons":[x.code for x in v]}); return ExecutionOutcome(False,"BLOCKED",tuple(x.code for x in v),intent.intent_id)
  existing=self.idempotency.register_intent(intent.intent_id)
  if existing.broker_transaction_id: return ExecutionOutcome(True,"ALREADY_ACCEPTED",(),intent.intent_id,existing.broker_transaction_id)
  try: result=await self.broker.submit_authorized_order({"proposal_id":intent.proposal_id,"stake":intent.stake})
  except Exception as exc: self.state.transition(RuntimeState.RECOVERY); return ExecutionOutcome(False,"RECOVERY_REQUIRED",(type(exc).__name__,),intent.intent_id)
  if result.outcome==BrokerOutcome.UNKNOWN: self.state.transition(RuntimeState.RECOVERY); self._log("BROKER_OUTCOME_UNKNOWN",{"intent_id":intent.intent_id}); return ExecutionOutcome(False,"RECOVERY_REQUIRED",("BROKER_OUTCOME_UNKNOWN",),intent.intent_id)
  if result.broker_transaction_id: self.idempotency.attach_broker_transaction(intent.intent_id,result.broker_transaction_id)
  if result.outcome==BrokerOutcome.ACCEPTED:
   self.idempotency.record_economic_effect(intent.intent_id); self.ledger.post(LedgerEvent(f"broker:{result.broker_transaction_id or result.request_id}",intent.intent_id,intent.account,"INTENT_RESERVED",intent.stake,intent.account.currency,result.broker_timestamp or intent.created_at,result.broker_transaction_id)); self._log("BROKER_ACCEPTED",{"intent_id":intent.intent_id,"broker_transaction_id":result.broker_transaction_id,"contract_id":result.contract_id}); return ExecutionOutcome(True,"ACCEPTED",(),intent.intent_id,result.broker_transaction_id)
  return ExecutionOutcome(False,"REJECTED",("BROKER_REJECTED",),intent.intent_id)
 async def reconcile(self,*,broker_capital,prior_authoritative_balance,explainable_delta=0.0):
  r=self.reconciler.compare(broker=broker_capital,prior_authoritative_balance=prior_authoritative_balance,explainable_delta=explainable_delta); self._log("RECONCILIATION",{"healthy":r.healthy,"difference":r.difference,"reason":r.reason})
  if not r.healthy and self.state.state!=RuntimeState.CAPITAL_PROTECTED:
   try:self.state.transition(RuntimeState.CAPITAL_PROTECTED)
   except ValueError:pass
  return r
