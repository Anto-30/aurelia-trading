from __future__ import annotations

import json
import unittest
from pathlib import Path


class ThreeSixtyNineRegistryTests(unittest.TestCase):
    def test_strategy_is_separately_registered_and_unqualified(self):
        path = Path(__file__).resolve().parents[3] / "config" / "strategy_registry.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        matches = [
            item for item in registry["strategies"]
            if item["strategy_id"] == "THREE_SIXTY_NINE_MSNR"
        ]
        self.assertEqual(len(matches), 1)
        entry = matches[0]
        self.assertEqual(entry["implementation_status"], "RESEARCH_ONLY")
        self.assertEqual(entry["qualification_status"], "RESEARCH_ONLY_UNQUALIFIED")
        self.assertEqual(entry["instrument_compatibility_status"], "UNKNOWN")
        self.assertEqual(entry["instrument_specification_status"], "UNKNOWN")
        self.assertEqual(entry["cost_profile_status"], "UNKNOWN")
        for gate in (
            "out_of_sample_status", "walk_forward_status", "calibration_status",
            "net_economics_status", "robustness_status",
            "statistical_uncertainty_status", "forward_testing_status",
            "runtime_soak_status",
        ):
            self.assertEqual(entry[gate], "NOT_RUN", gate)
        self.assertIsNone(entry["reviewer"])
        self.assertEqual(entry["qualification_evidence_ids"], [])
        self.assertFalse(registry["capital_authority"])
        self.assertFalse(registry["execution_authority"])

    def test_existing_msnr_registration_remains_present_and_unqualified(self):
        path = Path(__file__).resolve().parents[3] / "config" / "strategy_registry.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        entry = next(
            item for item in registry["strategies"]
            if item["strategy_id"] == "MSNR_LIQUIDITY_SWEEP"
        )
        self.assertEqual(entry["implementation_path"], "research/labs/deterministic_intraday_strategies.py")
        self.assertEqual(entry["qualification_status"], "RESEARCH_ONLY_UNQUALIFIED")


if __name__ == "__main__":
    unittest.main()
