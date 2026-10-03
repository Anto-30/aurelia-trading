import unittest

from assurance.adversarial_matrix import SCENARIOS, matrix_is_complete
from assurance.aurelia_hardening import (
    EvidenceRecord,
    ExposureSnapshot,
    MarketDataIntegrity,
    configuration_hash_matches,
    evidence_chain_complete,
    evidence_is_current,
    exactly_once_economic_effect,
    exposure_within_limit,
    full_balance_stake_is_affordable,
    kill_switch_resume_requires_new_authorization,
    market_data_safe,
    mtf_snapshot_is_decision_time_safe,
    privilege_allows,
    requested_stake_is_balance_permitted,
    shadow_decision_equivalent,
    stake_ceiling_from_verified_balance,
    unknown_broker_state_is_actionable,
)
from assurance.evidence_writer import build_evidence, payload_sha256


class HardeningControlsTest(unittest.TestCase):
    def _evidence(self, status="CURRENT"):
        return EvidenceRecord(
            evidence_id="E-1",
            source_hash="source",
            artifact_hash="artifact",
            config_hash="config",
            data_hash="data",
            environment="ci",
            started_at_utc="2026-10-03T10:00:00Z",
            ended_at_utc="2026-10-03T10:05:00Z",
            status=status,
            valid_until_utc="2026-10-03T11:00:00Z",
        )

    def test_evidence_requires_complete_chain(self):
        self.assertTrue(evidence_chain_complete(self._evidence()))
        self.assertTrue(evidence_is_current(self._evidence(), "2026-10-03T10:30:00Z"))
        self.assertFalse(evidence_is_current(self._evidence(), "2026-10-03T11:00:00Z"))
        self.assertFalse(evidence_is_current(self._evidence("EXPIRED"), "2026-10-03T10:30:00Z"))

    def test_market_data_fails_closed(self):
        self.assertTrue(market_data_safe(MarketDataIntegrity(False, False, False, False, True, True)))
        self.assertFalse(market_data_safe(MarketDataIntegrity(True, False, False, False, True, True)))
        self.assertFalse(market_data_safe(MarketDataIntegrity(False, True, False, False, True, True)))

    def test_mtf_cannot_see_future(self):
        self.assertTrue(mtf_snapshot_is_decision_time_safe(
            ["2026-10-03T10:00:00Z", "2026-10-03T10:05:00Z"], "2026-10-03T10:05:00Z"
        ))
        self.assertFalse(mtf_snapshot_is_decision_time_safe(
            ["2026-10-03T10:06:00Z"], "2026-10-03T10:05:00Z"
        ))

    def test_full_balance_is_a_valid_affordability_ceiling(self):
        self.assertEqual(stake_ceiling_from_verified_balance(8.00), 8.00)
        self.assertTrue(full_balance_stake_is_affordable(8.00))
        self.assertTrue(requested_stake_is_balance_permitted(8.00, 8.00))
        self.assertTrue(requested_stake_is_balance_permitted(8.00, 7.99))
        self.assertTrue(requested_stake_is_balance_permitted(1.49, 1.49))
        self.assertFalse(requested_stake_is_balance_permitted(1.49, 0.99))
        self.assertFalse(requested_stake_is_balance_permitted(None, 8.00))

    def test_exposure_is_aggregated(self):
        self.assertTrue(exposure_within_limit(ExposureSnapshot(1, 1, 1, 1, 1, 5)))
        self.assertFalse(exposure_within_limit(ExposureSnapshot(1, 1, 1, 1, 1.01, 5)))

    def test_exactly_once_and_unknown(self):
        self.assertTrue(exactly_once_economic_effect(1, 1))
        self.assertTrue(exactly_once_economic_effect(1, 0))
        self.assertFalse(exactly_once_economic_effect(1, 2))
        self.assertFalse(unknown_broker_state_is_actionable(True))
        self.assertTrue(unknown_broker_state_is_actionable(False))

    def test_kill_switch_requires_fresh_authorization(self):
        self.assertFalse(kill_switch_resume_requires_new_authorization(True, True, True))
        self.assertTrue(kill_switch_resume_requires_new_authorization(False, False, False))
        self.assertTrue(kill_switch_resume_requires_new_authorization(False, True, True))

    def test_config_and_shadow(self):
        self.assertTrue(configuration_hash_matches("a", "a"))
        self.assertFalse(configuration_hash_matches("a", "b"))
        self.assertTrue(shadow_decision_equivalent("BUY", "BUY", "DENY", "DENY"))
        self.assertFalse(shadow_decision_equivalent("BUY", "SELL", "DENY", "DENY"))

    def test_privilege_boundary(self):
        authority = {"research": False, "execution": True, "grok": False}
        self.assertFalse(privilege_allows("SUBMIT_ORDER", actor="grok", capital_authority=authority))
        self.assertTrue(privilege_allows("SUBMIT_ORDER", actor="execution", capital_authority=authority))
        self.assertTrue(privilege_allows("READ_RESEARCH", actor="grok", capital_authority=authority))

    def test_evidence_writer_is_deterministic(self):
        record = build_evidence(
            evidence_id="E1", source_hash="s", artifact_hash="a", config_hash="c", data_hash="d",
            environment="ci", started_at_utc="2026-10-03T10:00:00Z",
            ended_at_utc="2026-10-03T10:01:00Z", status="CURRENT",
        )
        self.assertEqual(record["record_hash"], payload_sha256({k:v for k,v in record.items() if k != "record_hash"}))

    def test_adversarial_matrix(self):
        self.assertTrue(matrix_is_complete())
        self.assertGreaterEqual(len(SCENARIOS), 20)

    def test_operational_state_replay_restore_and_degradation(self):
        from assurance.operational_hardening import (
            backup_restore_reconciled,
            canonical_state_hash,
            decision_replay_matches,
            no_silent_degradation,
        )
        state = {"symbol": "R_100", "probability": 0.60, "decision_time": "2026-10-03T10:00:00Z"}
        self.assertEqual(canonical_state_hash(state), canonical_state_hash(dict(state)))
        self.assertTrue(decision_replay_matches(state, dict(state)))
        self.assertFalse(decision_replay_matches(state, {**state, "probability": 0.61}))
        self.assertTrue(backup_restore_reconciled(8.0, 8.0, ["tx1"], ["tx1"]))
        self.assertFalse(backup_restore_reconciled(8.0, 7.9, ["tx1"], ["tx1"]))
        self.assertTrue(no_silent_degradation(subsystem_states={"broker": "AVAILABLE", "data": "VALID"}))
        self.assertFalse(no_silent_degradation(subsystem_states={"broker": "DEGRADED"}))


if __name__ == "__main__":
    unittest.main()
