from __future__ import annotations

import unittest

from runtime.strategy.registry import StrategyQualificationRegistry


def qualified_document():
    row = {
        "strategy_id": "TEST_STRATEGY", "version": "1.0",
        "qualification_status": "QUALIFIED_FOR_LIVE",
        "implementation_status": "VERIFIED", "instrument_compatibility_status": "PASS",
        "instrument_specification_status": "PASS", "timeframe_status": "PASS",
        "cost_profile_status": "PASS", "out_of_sample_status": "PASS", "walk_forward_status": "PASS",
        "calibration_status": "PASS", "net_economics_status": "PASS", "robustness_status": "PASS",
        "statistical_uncertainty_status": "PASS", "forward_testing_status": "PASS",
        "runtime_soak_status": "PASS", "risk_governance_status": "PASS",
        "instrument_categories": ["DERIV_SYNTHETIC_INDEX"], "timeframes": ["5M"],
        "verified_instrument_ids": ["R_100"], "qualification_evidence_ids": ["E-1", "E-2"],
        "reviewer": "independent-reviewer", "qualified_source_revision": "a" * 40,
        "strategy_hash": "b" * 64, "risk_profile": "loss limited to 1% verified equity",
        "data_requirements": ["closed_bars"], "execution_assumptions": ["next_bar_open", "costs_measured"],
    }
    return {"schema":"aurelia.strategy_registry.v1","registry_version":"test",
            "capital_authority":False,"execution_authority":False,"strategies":[row]}


class StrategyRegistryTests(unittest.TestCase):
    def test_canonical_registry_preserves_known_strategies_but_blocks_unqualified(self):
        registry = StrategyQualificationRegistry.from_file()
        ids = registry.strategy_ids()
        for required in ("MSNR_LIQUIDITY_SWEEP", "VWAP_PULLBACK_RECLAIM", "OPENING_RANGE_BREAKOUT",
                         "S7_LRL_IFVG", "S6_LIQUIDITY_SWEEP", "S3_DONCHIAN_LWTI",
                         "CRT", "MICRO_SCALP_R100_TICK_MOM"):
            self.assertIn(required, ids)
        for strategy_id in ids:
            row = registry.get(strategy_id)
            self.assertFalse(registry.eligibility(strategy_id, row["version"], "R_100")["eligible"])

    def test_unknown_strategy_and_version_mismatch_block(self):
        registry = StrategyQualificationRegistry.from_mapping(qualified_document())
        self.assertIn("STRATEGY_NOT_REGISTERED", registry.eligibility("UNKNOWN", "1", "R_100")["reasons"])
        result = registry.eligibility("TEST_STRATEGY", "2", "R_100")
        self.assertFalse(result["eligible"])
        self.assertIn("STRATEGY_VERSION_MISMATCH", result["reasons"])

    def test_live_eligibility_requires_every_evidence_gate(self):
        registry = StrategyQualificationRegistry.from_mapping(qualified_document())
        self.assertTrue(registry.eligibility("TEST_STRATEGY", "1.0", "R_100")["eligible"])
        doc = qualified_document()
        doc["strategies"][0]["cost_profile_status"] = "UNKNOWN"
        result = StrategyQualificationRegistry.from_mapping(doc).eligibility("TEST_STRATEGY", "1.0", "R_100")
        self.assertFalse(result["eligible"])
        self.assertIn("COST_PROFILE_STATUS_NOT_PASS", result["reasons"])

    def test_wrong_instrument_and_missing_evidence_block(self):
        doc = qualified_document()
        doc["strategies"][0]["verified_instrument_ids"] = ["EURUSD"]
        doc["strategies"][0]["qualification_evidence_ids"] = []
        result = StrategyQualificationRegistry.from_mapping(doc).eligibility("TEST_STRATEGY", "1.0", "R_100")
        self.assertFalse(result["eligible"])
        self.assertIn("INSTRUMENT_NOT_VERIFIED_FOR_STRATEGY", result["reasons"])
        self.assertIn("QUALIFICATION_EVIDENCE_IDS_MISSING", result["reasons"])

    def test_bad_authority_and_duplicate_ids_are_rejected(self):
        doc = qualified_document()
        doc["capital_authority"] = True
        with self.assertRaisesRegex(ValueError,"MUST_NOT_HAVE_CAPITAL_AUTHORITY"):
            StrategyQualificationRegistry.from_mapping(doc)
        doc = qualified_document()
        doc["strategies"].append(dict(doc["strategies"][0]))
        with self.assertRaisesRegex(ValueError,"DUPLICATE_ID"):
            StrategyQualificationRegistry.from_mapping(doc)


class FakeFederation:
    def __init__(self, message):
        self.message=message
        self.published=[]

    def messages_for(self, consumer, *, limit):
        return [self.message]

    async def publish(self, **kwargs):
        self.published.append(kwargs)


def proposal(strategy_id="MSNR_LIQUIDITY_SWEEP", version="1.0.0"):
    return {
        "message_id":"M1","sender":"specialist","message_type":"DECISION_PROPOSAL",
        "payload":{
            "decision_id":"D1","strategy_id":strategy_id,"strategy_version":version,
            "strategy_hash":"untrusted-agent-hash","symbol":"R_100","direction":"CALL","probability":0.60,
            "decision_time":"2026-10-10T11:00:00+00:00","market_snapshot_hash":"market-hash",
            "risk_requested_stake":1.0,"average_win":2.0,"average_loss":1.0,
            "proposal_parameters":{"contract_type":"CALL","currency":"USD","underlying_symbol":"R_100"},
        },
    }


class FederatedStrategyAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_unqualified_proposal_is_rejected_and_marked_seen(self):
        from types import SimpleNamespace
        from runtime.autonomous_loop import FederatedDecisionProvider
        federation=FakeFederation(proposal())
        provider=FederatedDecisionProvider(federation)
        result=await provider.next_decision(
            tick=SimpleNamespace(symbol="R_100"),
            capital=SimpleNamespace(account=SimpleNamespace(loginid="CR123")),
            account=SimpleNamespace(loginid="CR123"),
        )
        self.assertIsNone(result)
        self.assertIn("M1",provider._seen)
        self.assertEqual(len(provider._rejections),1)
        self.assertEqual(len(federation.published),1)
        self.assertEqual(federation.published[0]["message_type"],"STRATEGY_PROPOSAL_REJECTED")
        self.assertFalse(federation.published[0]["payload"]["eligible"])

    async def test_registry_read_failure_blocks_proposal(self):
        from types import SimpleNamespace
        from runtime.autonomous_loop import FederatedDecisionProvider
        federation=FakeFederation(proposal())
        provider=FederatedDecisionProvider(federation,registry_path="/missing/registry.json")
        result=await provider.next_decision(
            tick=SimpleNamespace(symbol="R_100"),
            capital=SimpleNamespace(account=SimpleNamespace(loginid="CR123")),
            account=SimpleNamespace(loginid="CR123"),
        )
        self.assertIsNone(result)
        self.assertIn("STRATEGY_REGISTRY_UNAVAILABLE",provider._rejections[-1]["reasons"])


if __name__ == "__main__":
    unittest.main()
