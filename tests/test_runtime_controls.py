from datetime import datetime, timedelta, timezone
import tempfile
import unittest

from runtime.core.authority import authorization_gate, decision_economics_gate, probability_is_valid
from runtime.core.capabilities import Capability, RESEARCH_CAPABILITIES
from runtime.core.events import event_envelope, sha256
from runtime.core.fencing import ExecutionFence
from runtime.core.health import HealthSnapshot, refresh_runtime_health
from runtime.core.idempotency import IdempotencyStore
from runtime.core.invariants import (
    check_pre_submission_invariants,
    no_duplicate_economic_effects,
    no_order_after_kill_switch,
    no_research_capital_authority,
)
from runtime.core.journal import AppendOnlyJournal
from runtime.core.limits import ExecutionLimits
from runtime.core.models import (
    AccountIdentity,
    AuthorizationContext,
    CapitalSnapshot,
    Decision,
    OrderIntent,
    RuntimeState,
)
from runtime.core.state import RuntimeStateMachine
from runtime.validation.decision_replay import replay_equivalent
from runtime.validation.probability import calibration_metrics, detect_drift
from runtime.validation.property_sequences import (
    bounded_effect_sequences,
    randomized_state_machine_trials,
)
from runtime.validation.walk_forward import OOSCell, validate_prospective_oos

UTC = timezone.utc


def ident(kind: str = "real") -> AccountIdentity:
    return AccountIdentity("CR123", kind, "USD", kind)


def cap(balance: float = 10.0, age: float = 0.0) -> CapitalSnapshot:
    return CapitalSnapshot(
        balance,
        "USD",
        balance,
        datetime.now(UTC) - timedelta(seconds=age),
        "test",
        ident(),
    )


def dec(probability: float = 0.60, stake: float = 2.0) -> Decision:
    return Decision(
        "D1",
        "strategy",
        "0.1.0",
        "strategyhash",
        "R_100",
        "CALL",
        probability,
        datetime.now(UTC),
        "markethash",
        stake,
        ("TEST",),
        2.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.8,
    )


class TestControls(unittest.TestCase):
    def test_probability_no_clipping(self):
        self.assertTrue(probability_is_valid(0.55))
        self.assertTrue(probability_is_valid(0.75))
        self.assertFalse(probability_is_valid(0.76))
        self.assertFalse(probability_is_valid(0.82))

    def test_low_balance_is_not_readiness_blocker(self):
        from assurance.aurelia_invariants import capital_readiness_blocker_for_balance
        self.assertFalse(capital_readiness_blocker_for_balance(1))

    def test_stake_policy_uses_one_dollar_floor(self):
        limits = ExecutionLimits()
        self.assertEqual(limits.minimum_stake, 1.00)
        self.assertTrue(limits.validate(1.00, 1.45)[0])
        self.assertFalse(limits.validate(1.00, 0.99)[0])

    def test_full_balance_ceiling(self):
        from assurance.aurelia_hardening import requested_stake_is_balance_permitted
        self.assertTrue(requested_stake_is_balance_permitted(8, 8))
        self.assertFalse(requested_stake_is_balance_permitted(8, 8.01))
        self.assertTrue(requested_stake_is_balance_permitted(1.49, 1.49))

    def test_demo_blocked(self):
        gate, _ = authorization_gate(
            decision=dec(),
            account=ident("demo"),
            capital=cap(),
            config_hash="h",
            runtime_config_hash="h",
            kill_switch_off=True,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=True,
            live_trading_enabled=True,
        )
        self.assertIn("ACCOUNT_NOT_REAL", gate.reason_codes)

    def test_stale_capital_blocked(self):
        gate, _ = authorization_gate(
            decision=dec(),
            account=ident(),
            capital=cap(age=30),
            config_hash="h",
            runtime_config_hash="h",
            kill_switch_off=True,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=True,
            live_trading_enabled=True,
            probability_calibrated=True,
            probability_fresh=True,
            probability_drift_ok=True,
            market_data_validated=True,
            exposure_approved=True,
        )
        self.assertIn("CAPITAL_TRUTH_NOT_FRESH", gate.reason_codes)

    def test_probability_validation_is_hard_gate(self):
        common = dict(
            account=ident(),
            capital=cap(),
            config_hash="h",
            runtime_config_hash="h",
            kill_switch_off=True,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=True,
            live_trading_enabled=True,
        )
        gate, _ = authorization_gate(decision=dec(), **common)
        self.assertIn("PROBABILITY_NOT_CALIBRATED", gate.reason_codes)
        self.assertIn("PROBABILITY_NOT_FRESH", gate.reason_codes)
        self.assertIn("PROBABILITY_DRIFT_DETECTED_OR_UNVERIFIED", gate.reason_codes)
        self.assertIn("MARKET_DATA_NOT_VALIDATED", gate.reason_codes)
        self.assertIn("EXPOSURE_NOT_APPROVED", gate.reason_codes)

    def test_live_economics_malformed_input_fails_closed(self):
        decision = dec()
        malformed = Decision(
            decision.decision_id, decision.strategy_id, decision.strategy_version,
            decision.strategy_hash, decision.symbol, decision.direction,
            decision.probability, decision.decision_time, decision.market_snapshot_hash,
            decision.risk_requested_stake, decision.rationale_codes,
            decision.average_win, decision.average_loss, None, 0.0, 0.0, None,
        )
        allowed, reason, computed = decision_economics_gate(malformed)
        self.assertFalse(allowed)
        self.assertEqual(reason, "ECONOMICS_INPUTS_INVALID")
        self.assertIsNone(computed)

    def test_live_gate_requires_positive_expected_value(self):
        negative = dec()
        negative = Decision(
            negative.decision_id, negative.strategy_id, negative.strategy_version,
            negative.strategy_hash, negative.symbol, negative.direction,
            0.55, negative.decision_time, negative.market_snapshot_hash,
            negative.risk_requested_stake, negative.rationale_codes,
            0.5, 1.0, 0.0, 0.0, 0.0, -0.175,
        )
        gate, _ = authorization_gate(
            decision=negative,
            account=ident(),
            capital=cap(),
            config_hash="h",
            runtime_config_hash="h",
            kill_switch_off=True,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=True,
            live_trading_enabled=True,
            probability_calibrated=True,
            probability_fresh=True,
            probability_drift_ok=True,
            market_data_validated=True,
            exposure_approved=True,
        )
        self.assertNotIn("PROBABILITY_OUTSIDE_HARD_POLICY", gate.reason_codes)
        self.assertIn("EXPECTED_VALUE_NON_POSITIVE", gate.reason_codes)

    def test_live_gate_requires_healthy_reconciliation(self):
        gate, _ = authorization_gate(
            decision=dec(),
            account=ident(),
            capital=cap(),
            config_hash="h",
            runtime_config_hash="h",
            kill_switch_off=True,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=False,
            final_execution_authorization=True,
            live_trading_enabled=True,
            probability_calibrated=True,
            probability_fresh=True,
            probability_drift_ok=True,
            market_data_validated=True,
            exposure_approved=True,
        )
        self.assertFalse(gate.allowed)
        self.assertIn("RECONCILIATION_UNHEALTHY", gate.reason_codes)

    def test_full_gate_can_pass_only_with_all_validation_inputs(self):
        gate, ctx = authorization_gate(
            decision=dec(),
            account=ident(),
            capital=cap(),
            config_hash="h",
            runtime_config_hash="h",
            kill_switch_off=True,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=True,
            live_trading_enabled=True,
            probability_calibrated=True,
            probability_fresh=True,
            probability_drift_ok=True,
            market_data_validated=True,
            exposure_approved=True,
        )
        self.assertTrue(gate.allowed)
        self.assertIsNotNone(ctx)

    def test_locked_baseline(self):
        gate, ctx = authorization_gate(
            decision=dec(),
            account=ident(),
            capital=cap(),
            config_hash="h",
            runtime_config_hash="h",
            kill_switch_off=True,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=False,
            live_trading_enabled=False,
        )
        self.assertFalse(gate.allowed)
        self.assertIsNone(ctx)
        self.assertIn("FINAL_EXECUTION_AUTHORIZATION_FALSE", gate.reason_codes)

    def test_event_hash(self):
        event = event_envelope(
            event_type="T",
            event_id="1",
            correlation_id="c",
            payload={"x": 1},
            source_hash="s",
            config_hash="c",
        )
        unsigned = {key: value for key, value in event.items() if key != "record_hash"}
        self.assertEqual(event["record_hash"], sha256(unsigned))

    def test_journal(self):
        with tempfile.TemporaryDirectory() as td:
            journal = AppendOnlyJournal(td + "/x.ndjson")
            event = event_envelope(
                event_type="T",
                event_id="1",
                correlation_id="c",
                payload={"x": 1},
                source_hash="s",
                config_hash="c",
            )
            journal.append(event)
            self.assertEqual(len(journal.read_all()), 1)

    def test_idempotency_duplicate_rejected(self):
        store = IdempotencyStore()
        store.register_intent("I")
        store.record_economic_effect("I")
        with self.assertRaises(RuntimeError):
            store.record_economic_effect("I")

    def test_fencing(self):
        fence = ExecutionFence()
        a = fence.acquire("A")
        b = fence.acquire("B")
        self.assertFalse(fence.valid(a))
        self.assertTrue(fence.valid(b))
        fence.revoke()
        self.assertFalse(fence.valid(b))

    def test_invariants_require_proposal(self):
        context = AuthorizationContext(
            dec(),
            ident(),
            cap(),
            "h",
            "a",
            datetime.now(UTC),
            datetime.now(UTC) + timedelta(seconds=5),
            True,
            True,
            True,
            True,
            True,
        )
        intent = OrderIntent(
            "I",
            "D1",
            ident(),
            "R_100",
            "CALL",
            2.0,
            datetime.now(UTC),
            "strategyhash",
            "h",
            "LIVE",
            None,
        )
        violations = check_pre_submission_invariants(
            context=context,
            intent=intent,
            kill_switch_off=True,
            broker_state_unknown=False,
            single_writer_token_valid=True,
        )
        self.assertIn("PROPOSAL_ID_MISSING", [item.code for item in violations])

    def test_state_machine(self):
        machine = RuntimeStateMachine()
        machine.transition(RuntimeState.SELF_CHECK)
        machine.transition(RuntimeState.CAPITAL_PROTECTED)
        machine.transition(RuntimeState.RECOVERY)
        machine.transition(RuntimeState.VERIFIED)
        machine.transition(RuntimeState.HEALTHY)
        self.assertEqual(machine.state, RuntimeState.HEALTHY)

    def test_runtime_health_requires_fresh_capital_market_data_and_reconciliation(self):
        health = HealthSnapshot(datetime.now(UTC))
        refresh_runtime_health(
            health,
            broker_session=True,
            capital=cap(age=0),
            market_data_received_at=datetime.now(UTC),
            ledger_healthy=True,
            reconciliation_healthy=True,
            kill_switch_off=True,
        )
        self.assertTrue(health.broker_session)
        self.assertTrue(health.capital_fresh)
        self.assertTrue(health.market_data_fresh)
        self.assertTrue(health.ledger_healthy)
        self.assertTrue(health.reconciliation_healthy)
        self.assertTrue(health.kill_switch_off)

        refresh_runtime_health(
            health,
            broker_session=True,
            capital=cap(age=30),
            market_data_received_at=datetime.now(UTC) - timedelta(seconds=30),
            ledger_healthy=True,
            reconciliation_healthy=False,
            kill_switch_off=False,
        )
        self.assertFalse(health.capital_fresh)
        self.assertFalse(health.market_data_fresh)
        self.assertFalse(health.reconciliation_healthy)
        self.assertFalse(health.kill_switch_off)

    def test_health_unknown(self):
        health = HealthSnapshot(datetime.now(UTC))
        health.critical_unknowns.add("X")
        self.assertFalse(health.readiness())

    def test_replay(self):
        decision = dec()
        self.assertTrue(replay_equivalent(decision, decision).equivalent)

    def test_oos_cell(self):
        result = validate_prospective_oos(
            [OOSCell("S", "R_100", "RANGE", 100)],
            sealed_prospective_data=True,
            retuning_after_seal=False,
        )
        self.assertTrue(result.qualified)

    def test_oos_retune_reject(self):
        result = validate_prospective_oos(
            [OOSCell("S", "R_100", "RANGE", 100)],
            sealed_prospective_data=True,
            retuning_after_seal=True,
        )
        self.assertFalse(result.qualified)

    def test_calibration(self):
        self.assertTrue(calibration_metrics([0.5, 0.9], [0, 1]).valid)
        self.assertTrue(detect_drift(0.55, 0.70))
        self.assertFalse(detect_drift(0.55, 0.58))

    def test_property_sequences(self):
        self.assertEqual(randomized_state_machine_trials(trials=50)["failures"], 0)
        self.assertTrue(bounded_effect_sequences(trials=50))

    def test_invariants(self):
        self.assertTrue(no_duplicate_economic_effects(1))
        self.assertFalse(no_duplicate_economic_effects(2))
        self.assertFalse(no_order_after_kill_switch(True, True))
        self.assertTrue(no_research_capital_authority(False))
        self.assertFalse(no_research_capital_authority(True))

    def test_research_cannot_submit(self):
        self.assertFalse(RESEARCH_CAPABILITIES.allows(Capability.SUBMIT_ORDER))


class TestRuntimeState(unittest.TestCase):
    def test_invalid_transition(self):
        machine = RuntimeStateMachine()
        with self.assertRaises(ValueError):
            machine.transition(RuntimeState.HEALTHY)


if __name__ == "__main__":
    unittest.main()
