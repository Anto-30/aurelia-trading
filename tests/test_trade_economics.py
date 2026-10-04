import unittest

from runtime.core.economics import TradeEconomics


class TradeEconomicsTests(unittest.TestCase):
    def test_positive_expected_value(self):
        economics = TradeEconomics(
            probability=0.60,
            average_win=2.0,
            average_loss=1.0,
            execution_cost=0.05,
        )
        self.assertAlmostEqual(economics.expected_value, 0.75)
        self.assertEqual(economics.gate(), (True, "EXPECTED_VALUE_POSITIVE"))

    def test_zero_or_negative_expected_value_is_blocked(self):
        economics = TradeEconomics(
            probability=0.50,
            average_win=1.0,
            average_loss=1.0,
        )
        self.assertEqual(economics.gate(), (False, "EXPECTED_VALUE_NON_POSITIVE"))

    def test_invalid_economics_are_fail_closed(self):
        economics = TradeEconomics(
            probability=0.60,
            average_win=0.0,
            average_loss=1.0,
        )
        self.assertEqual(economics.gate(), (False, "ECONOMICS_AVERAGE_WIN_INVALID"))


if __name__ == "__main__":
    unittest.main()
