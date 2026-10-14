"""Regression test for the specified $1 initial-risk net-expectancy example."""
import unittest
from runtime.core.economics import TradeEconomics

class MasterExpectancyExampleTests(unittest.TestCase):
    def test_1_to_2_hypothetical_net_expectancy_is_minus_five_cents(self):
        economics = TradeEconomics(probability=0.35, average_win=2.0, average_loss=1.0, execution_cost=0.10)
        self.assertAlmostEqual(economics.expected_value, -0.05, places=12)
        self.assertEqual(economics.gate(), (False, "EXPECTED_VALUE_NON_POSITIVE"))

    def test_negative_cost_is_rejected(self):
        economics = TradeEconomics(probability=0.35, average_win=2.0, average_loss=1.0, execution_cost=-0.10)
        self.assertEqual(economics.gate(), (False, "ECONOMICS_COST_INVALID"))

if __name__ == "__main__":
    unittest.main()
