from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from runtime.core.authority import MAX_PROBABILITY, MIN_PROBABILITY

ROOT = Path(__file__).resolve().parents[1]


class ProbabilityPolicyConsistencyTests(unittest.TestCase):
    def test_runtime_config_matches_deterministic_authority(self):
        runtime = (ROOT / "config" / "runtime.yaml").read_text(encoding="utf-8")
        minimum = re.search(r"(?m)^  min_trade_probability: ([0-9.]+)\\s*$", runtime)
        maximum = re.search(r"(?m)^  max_trade_probability: ([0-9.]+)\\s*$", runtime)
        clipping = re.search(r"(?m)^  clipping: (true|false)\\s*$", runtime)
        self.assertIsNotNone(minimum)
        self.assertIsNotNone(maximum)
        self.assertIsNotNone(clipping)
        self.assertAlmostEqual(float(minimum.group(1)), MIN_PROBABILITY)
        self.assertAlmostEqual(float(maximum.group(1)), MAX_PROBABILITY)
        self.assertEqual(clipping.group(1), "false")
        self.assertAlmostEqual(MIN_PROBABILITY, 0.55)
        self.assertAlmostEqual(MAX_PROBABILITY, 0.75)

    def test_source_of_truth_matches_authority_and_runtime_config(self):
        truth = json.loads((ROOT / "AURELIA_SOURCE_OF_TRUTH.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(truth["probability_min"], MIN_PROBABILITY)
        self.assertAlmostEqual(truth["probability_max"], MAX_PROBABILITY)
        self.assertIs(truth["probability_clipping"], False)


if __name__ == "__main__":
    unittest.main()
