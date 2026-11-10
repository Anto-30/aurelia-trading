from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from runtime.core.authority import MAX_PROBABILITY, MIN_PROBABILITY, probability_is_valid


ROOT = Path(__file__).resolve().parents[1]


class MinimumProbabilityPolicyTests(unittest.TestCase):
    def test_production_authority_uses_goals_minimum_of_point_55(self):
        self.assertEqual(MIN_PROBABILITY, 0.55)
        self.assertTrue(probability_is_valid(0.55))
        self.assertFalse(probability_is_valid(0.549999))
        self.assertFalse(probability_is_valid(0.50))

    def test_production_authority_keeps_point_75_upper_bound_without_clipping(self):
        self.assertEqual(MAX_PROBABILITY, 0.75)
        self.assertTrue(probability_is_valid(0.75))
        self.assertFalse(probability_is_valid(0.750001))

    def test_runtime_configuration_matches_the_authoritative_probability_policy(self):
        text = (ROOT / "config" / "runtime.yaml").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^  min_trade_probability:\s*0\.55\s*$")
        self.assertRegex(text, r"(?m)^  max_trade_probability:\s*0\.75\s*$")
        self.assertRegex(text, r"(?m)^  clipping:\s*false\s*$")

    def test_source_of_truth_matches_the_authoritative_probability_policy(self):
        data = json.loads((ROOT / "AURELIA_SOURCE_OF_TRUTH.json").read_text(encoding="utf-8"))
        self.assertEqual(data["probability_min"], 0.55)
        self.assertEqual(data["probability_max"], 0.75)
        self.assertFalse(data["probability_clipping"])

    def test_goals_document_the_same_probability_floor_and_ceiling(self):
        goals = (ROOT / "GOALS.md").read_text(encoding="utf-8")
        self.assertIn("`MIN_TRADE_PROBABILITY=0.55`", goals)
        self.assertIn("`MAX_TRADE_PROBABILITY=0.75`", goals)


if __name__ == "__main__":
    unittest.main()
