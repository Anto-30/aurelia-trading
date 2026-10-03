import unittest

from assurance.aurelia_invariants import (
    AuthorizationInputs,
    blind_resubmit_allowed,
    capital_readiness_blocker_for_balance,
    final_execution_authorized,
    order_affordability,
    probability_policy_valid,
)
from assurance.aurelia_state_machine import ExecutionState


class AssuranceContractsTest(unittest.TestCase):
    def _valid(self):
        return AuthorizationInputs(
            account_is_real=True,
            broker_session_verified=True,
            market_data_valid=True,
            strategy_valid=True,
            probability_valid=True,
            probability=0.60,
            risk_approved=True,
            capital_authorized=True,
            stake_affordable=True,
            execution_firewall_approved=True,
            kill_switch_off=True,
            reconciliation_healthy=True,
            stale_authorization=False,
            configuration_matched=True,
            unknown_broker_state=False,
        )

    def test_full_authorization_requires_all_controls(self):
        valid = self._valid()
        self.assertTrue(final_execution_authorized(valid))

        boolean_controls = (
            "account_is_real",
            "broker_session_verified",
            "market_data_valid",
            "strategy_valid",
            "probability_valid",
            "risk_approved",
            "capital_authorized",
            "stake_affordable",
            "execution_firewall_approved",
            "kill_switch_off",
            "reconciliation_healthy",
            "configuration_matched",
        )
        for field in boolean_controls:
            denied = AuthorizationInputs(**{**valid.__dict__, field: False})
            with self.subTest(field=field):
                self.assertFalse(final_execution_authorized(denied))

        stale = AuthorizationInputs(**{**valid.__dict__, "stale_authorization": True})
        unknown = AuthorizationInputs(**{**valid.__dict__, "unknown_broker_state": True})
        self.assertFalse(final_execution_authorized(stale))
        self.assertFalse(final_execution_authorized(unknown))

    def test_probability_is_not_clipped(self):
        self.assertFalse(probability_policy_valid(None))
        self.assertFalse(probability_policy_valid(0.549999))
        self.assertTrue(probability_policy_valid(0.55))
        self.assertTrue(probability_policy_valid(0.75))
        self.assertFalse(probability_policy_valid(0.750001))
        self.assertFalse(probability_policy_valid(0.82))

    def test_low_balance_is_not_system_readiness_blocker(self):
        self.assertFalse(capital_readiness_blocker_for_balance(1.45))
        self.assertEqual(order_affordability(1.45), "AFFORDABLE")
        self.assertEqual(order_affordability(0.99), "UNAFFORDABLE")
        self.assertEqual(order_affordability(1.00), "AFFORDABLE")
        self.assertEqual(order_affordability(None), "UNKNOWN")

    def test_blind_resubmission_is_never_permitted(self):
        self.assertFalse(blind_resubmit_allowed(broker_state_unknown=True))
        self.assertFalse(blind_resubmit_allowed(broker_state_unknown=False))

    def test_invalid_state_transitions_are_rejected(self):
        s = ExecutionState()
        with self.assertRaises(ValueError):
            s.transition("SETTLED")
        s.transition("AUTHORIZED")
        s.transition("SUBMITTED")
        s.transition("UNKNOWN")
        with self.assertRaises(ValueError):
            s.transition("SUBMITTED")


if __name__ == "__main__":
    unittest.main()
