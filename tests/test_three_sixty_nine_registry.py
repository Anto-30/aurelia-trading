from __future__ import annotations

import unittest

from runtime.strategy.registry import StrategyQualificationRegistry


class ThreeSixtyNineRegistryTests(unittest.TestCase):
    def test_369_is_registered_as_research_only_and_cannot_pass_live_gate(self):
        registry = StrategyQualificationRegistry.from_file()
        row = registry.get("THREE_SIXTY_NINE_MSNR")
        self.assertIsNotNone(row)
        self.assertEqual(row["version"], "0.1.0")
        self.assertEqual(row["implementation_status"], "RESEARCH_ONLY")
        self.assertEqual(row["qualification_status"], "RESEARCH_ONLY_UNQUALIFIED")
        self.assertEqual(row["instrument_compatibility_status"], "UNKNOWN")
        self.assertEqual(row["cost_profile_status"], "UNKNOWN")
        self.assertEqual(row["out_of_sample_status"], "NOT_RUN")
        self.assertEqual(row["walk_forward_status"], "NOT_RUN")
        self.assertEqual(row["runtime_soak_status"], "NOT_RUN")

        result = registry.eligibility(
            "THREE_SIXTY_NINE_MSNR",
            "0.1.0",
            "R_100",
            strategy_hash="0" * 64,
        )
        self.assertFalse(result["eligible"])
        self.assertIn("STRATEGY_NOT_QUALIFIED_FOR_LIVE", result["reasons"])
        self.assertIn("STRATEGY_IMPLEMENTATION_NOT_VERIFIED", result["reasons"])
        self.assertIn("STRATEGY_INSTRUMENT_COMPATIBILITY_NOT_VERIFIED", result["reasons"])

    def test_369_research_registration_has_no_capital_or_execution_authority(self):
        registry = StrategyQualificationRegistry.from_file()
        self.assertFalse(registry.capital_authority)
        self.assertFalse(registry.execution_authority)
        row = registry.get("THREE_SIXTY_NINE_MSNR")
        self.assertFalse(row.get("capital_authority", False))
        self.assertFalse(row.get("execution_authority", False))


if __name__ == "__main__":
    unittest.main()
