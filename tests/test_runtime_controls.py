from datetime import datetime,timedelta,timezone
import tempfile,unittest
from runtime.core.authority import authorization_gate,probability_is_valid
from runtime.core.events import event_envelope,sha256
from runtime.core.fencing import ExecutionFence
from runtime.core.health import HealthSnapshot
from runtime.core.idempotency import IdempotencyStore
from runtime.core.invariants import check_pre_submission_invariants,no_duplicate_economic_effects,no_order_after_kill_switch,no_research_capital_authority
from runtime.core.journal import AppendOnlyJournal
from runtime.core.models import AccountIdentity,AuthorizationContext,CapitalSnapshot,Decision,OrderIntent
from runtime.core.state import RuntimeStateMachine
from runtime.core.models import RuntimeState
from runtime.validation.decision_replay import replay_equivalent
from runtime.validation.probability import calibration_metrics,detect_drift
from runtime.validation.property_sequences import randomized_state_machine_trials,bounded_effect_sequences
from runtime.validation.walk_forward import OOSCell,validate_prospective_oos
UTC=timezone.utc

def ident(kind="real"):return AccountIdentity("CR123",kind,"USD",kind)
def cap(balance=10,age=0):return CapitalSnapshot(balance,"USD",balance,datetime.now(UTC)-timedelta(seconds=age),"test",ident())
def dec(p=.60,stake=2):return Decision("D1","strategy","0.1.0","strategyhash","R_100","CALL",p,datetime.now(UTC),"markethash",stake,("TEST",))
class TestControls(unittest.TestCase):
 def test_probability_no_clipping(self):self.assertTrue(probability_is_valid(.55));self.assertTrue(probability_is_valid(.75));self.assertFalse(probability_is_valid(.76));self.assertFalse(probability_is_valid(.82))
 def test_low_balance_is_not_readiness_blocker(self):from assurance.aurelia_invariants import capital_readiness_blocker_for_balance;self.assertFalse(capital_readiness_blocker_for_balance(1))
 def test_full_balance_ceiling(self):from assurance.aurelia_hardening import requested_stake_is_balance_permitted;self.assertTrue(requested_stake_is_balance_permitted(8,8));self.assertFalse(requested_stake_is_balance_permitted(8,8.01));self.assertFalse(requested_stake_is_balance_permitted(1.49,1.49))
 def test_demo_blocked(self):g,_=authorization_gate(decision=dec(),account=ident("demo"),capital=cap(),config_hash="h",runtime_config_hash="h",kill_switch_off=True,risk_approved=True,firewall_approved=True,reconciliation_healthy=True,final_execution_authorization=True,live_trading_enabled=True);self.assertIn("ACCOUNT_NOT_REAL",g.reason_codes)
 def test_stale_capital_blocked(self):g,_=authorization_gate(decision=dec(),account=ident(),capital=cap(age=30),config_hash="h",runtime_config_hash="h",kill_switch_off=True,risk_approved=True,firewall_approved=True,reconciliation_healthy=True,final_execution_authorization=True,live_trading_enabled=True);self.assertIn("CAPITAL_TRUTH_NOT_FRESH",g.reason_codes)
 def test_locked_baseline(self):g,c=authorization_gate(decision=dec(),account=ident(),capital=cap(),config_hash="h",runtime_config_hash="h",kill_switch_off=True,risk_approved=True,firewall_approved=True,reconciliation_healthy=True,final_execution_authorization=False,live_trading_enabled=False);self.assertFalse(g.allowed);self.assertIsNone(c);self.assertIn("FINAL_EXECUTION_AUTHORIZATION_FALSE",g.reason_codes)
 def test_event_hash(self):e=event_envelope(event_type="T",event_id="1",correlation_id="c",payload={"x":1},source_hash="s",config_hash="c");self.assertEqual(e["record_hash"],sha256({k:v for k,v in e.items() if k!="record_hash"}))
 def test_journal(self):
  with tempfile.TemporaryDirectory() as td:
   j=AppendOnlyJournal(td+"/x.ndjson");e=event_envelope(event_type="T",event_id="1",correlation_id="c",payload={"x":1},source_hash="s",config_hash="c");j.append(e);self.assertEqual(len(j.read_all()),1)
 def test_idempotency_single_effect(self):s=IdempotencyStore();s.register_intent("I");s.record_economic_effect("I");with_raised=False
 def test_idempotency_duplicate_rejected(self):
  s=IdempotencyStore();s.register_intent("I");s.record_economic_effect("I")
  with self.assertRaises(RuntimeError):s.record_economic_effect("I")
 def test_fencing(self):f=ExecutionFence();a=f.acquire("A");b=f.acquire("B");self.assertFalse(f.valid(a));self.assertTrue(f.valid(b));f.revoke();self.assertFalse(f.valid(b))
 def test_invariants_require_proposal(self):
  ctx=AuthorizationContext(dec(),ident(),cap(),"h","a",datetime.now(UTC),datetime.now(UTC)+timedelta(seconds=5),True,True,True,True,True);i=OrderIntent("I","D1",ident(),"R_100","CALL",2,datetime.now(UTC),"strategyhash","h","LIVE",None);v=check_pre_submission_invariants(context=ctx,intent=i,kill_switch_off=True,broker_state_unknown=False,single_writer_token_valid=True);self.assertIn("PROPOSAL_ID_MISSING",[x.code for x in v])
 def test_state_machine(self):s=RuntimeStateMachine();s.transition(RuntimeState.SELF_CHECK);s.transition(RuntimeState.CAPITAL_PROTECTED);s.transition(RuntimeState.RECOVERY);s.transition(RuntimeState.VERIFIED);s.transition(RuntimeState.HEALTHY);self.assertEqual(s.state,RuntimeState.HEALTHY)
 def test_health_unknown(self):h=HealthSnapshot(datetime.now(UTC));h.critical_unknowns.add("X");self.assertFalse(h.readiness())
 def test_replay(self):d=dec();self.assertTrue(replay_equivalent(d,d).equivalent)
 def test_oos_cell(self):self.assertTrue(validate_prospective_oos([OOSCell("S","R_100","RANGE",100)],sealed_prospective_data=True,retuning_after_seal=False).qualified)
 def test_oos_retune_reject(self):self.assertFalse(validate_prospective_oos([OOSCell("S","R_100","RANGE",100)],sealed_prospective_data=True,retuning_after_seal=True).qualified)
 def test_calibration(self):self.assertTrue(calibration_metrics([.5,.9],[0,1]).valid);self.assertTrue(detect_drift(.55,.70));self.assertFalse(detect_drift(.55,.58))
 def test_property_sequences(self):self.assertEqual(randomized_state_machine_trials(trials=50)["failures"],0);self.assertTrue(bounded_effect_sequences(trials=50))
 def test_invariants(self):self.assertTrue(no_duplicate_economic_effects(1));self.assertFalse(no_duplicate_economic_effects(2));self.assertFalse(no_order_after_kill_switch(True,True));self.assertTrue(no_research_capital_authority(False));self.assertFalse(no_research_capital_authority(True))
class TestRuntimeState(unittest.TestCase):
 def test_invalid_transition(self):
  s=RuntimeStateMachine()
  with self.assertRaises(ValueError):s.transition(RuntimeState.HEALTHY)
if __name__=="__main__":unittest.main()
