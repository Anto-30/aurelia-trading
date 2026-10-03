import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.core.capabilities import Capability, CapabilitySet, EXECUTION_CAPABILITIES, RESEARCH_CAPABILITIES
from runtime.core.data_integrity import validate_tick_sequence
from runtime.core.money import Money, parse_money
from runtime.core.resources import ResourceBudget, ResourceUsage
from runtime.core.release_gate import read_live_release
from runtime.core.temporal import ClockIntegrity, EventSequence
from runtime.core.unknowns import UnknownCondition, UnknownRegistry
from runtime.strategy.governance import StrategyGovernance, StrategyStage


class OperationalControlTests(unittest.TestCase):
    def test_research_cannot_submit(self):
        self.assertTrue(RESEARCH_CAPABILITIES.allows(Capability.RUN_BACKTEST))
        self.assertFalse(RESEARCH_CAPABILITIES.allows(Capability.SUBMIT_ORDER))
        self.assertTrue(EXECUTION_CAPABILITIES.allows(Capability.SUBMIT_ORDER))

    def test_live_lock_cannot_move_capital(self):
        state = read_live_release(Path("config/LIVE_LOCK.yaml"))
        self.assertFalse(state.may_move_capital)
        self.assertFalse(state.live_trading_enabled)
        self.assertFalse(state.final_execution_authorization)

    def test_unknown_registry(self):
        registry = UnknownRegistry()
        registry.add(UnknownCondition("BROKER_OUTCOME", "ambiguous", True))
        self.assertTrue(registry.any_capital_critical())
        registry.resolve("BROKER_OUTCOME")
        self.assertFalse(registry.any_capital_critical())

    def test_temporal_integrity(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(ClockIntegrity(now, now).valid())
        self.assertFalse(ClockIntegrity(now, now + timedelta(seconds=3)).valid())
        self.assertTrue(EventSequence(2, now).monotonic_after(EventSequence(1, now)))

    def test_data_integrity(self):
        self.assertTrue(validate_tick_sequence(100, 101, 1.0, 1.1).valid)
        self.assertFalse(validate_tick_sequence(101, 100, 1.0, 1.1).valid)

    def test_resource_budget(self):
        self.assertTrue(ResourceUsage(1, 2, 1, 0.2, 0.3).within(ResourceBudget()))
        self.assertFalse(ResourceUsage(121, 2, 1, 0.2, 0.3).within(ResourceBudget()))

    def test_money_normalization(self):
        money = parse_money("1.239", "USD").normalized()
        self.assertEqual(str(money.amount), "1.23")
        self.assertEqual(money.currency, "USD")

    def test_strategy_promotion_requires_evidence(self):
        governance = StrategyGovernance({})
        with self.assertRaises(ValueError):
            governance.promote("S", (), "reviewer")
        stage = governance.promote("S", ("E1",), "reviewer")
        self.assertEqual(stage, StrategyStage.REPLAYABLE)

    def test_strategy_demotion(self):
        governance = StrategyGovernance({"S": StrategyStage.PRODUCTION})
        self.assertEqual(governance.demote("S", StrategyStage.SUSPENDED), StrategyStage.SUSPENDED)


if __name__ == "__main__":
    unittest.main()
