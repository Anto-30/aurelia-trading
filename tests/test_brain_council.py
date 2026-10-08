import unittest

from runtime.intelligence.brain_council import BrainCouncil, BrainStatus

class BrainCouncilTests(unittest.TestCase):
    def test_requires_both_for_capital_relevant_work(self):
        c = BrainCouncil([BrainStatus("ChatGPT", True, "AUTHENTICATED"), BrainStatus("ClaudeCode", True, "AUTHENTICATED")])
        d = c.decide(capital_relevant=True)
        self.assertEqual(d.status, "DUAL_ROUTE")
        self.assertTrue(d.require_both)

    def test_abstains_if_one_primary_is_missing_for_high_consequence(self):
        c = BrainCouncil([BrainStatus("ChatGPT", True, "AUTHENTICATED")])
        d = c.decide(high_consequence=True)
        self.assertEqual(d.status, "ABSTAIN")

    def test_normal_work_can_continue_with_one_verified_primary(self):
        c = BrainCouncil([BrainStatus("ClaudeCode", True, "AUTHENTICATED")])
        d = c.decide()
        self.assertEqual(d.status, "ROUTE")
        self.assertEqual(d.primary, "ClaudeCode")

    def test_no_verified_brains_abstain(self):
        self.assertEqual(BrainCouncil([]).decide().status, "ABSTAIN")

if __name__ == "__main__":
    unittest.main()
