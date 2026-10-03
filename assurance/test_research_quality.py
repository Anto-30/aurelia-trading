import math
import unittest

from assurance.research_quality import (
    TradeAttribution,
    brier_score,
    log_loss,
    mean_probability_drift,
    multiple_testing_status,
    net_expectancy,
    post_trade_net_pnl,
    reliability_buckets,
    single_trade_may_promote_strategy,
)

class ResearchQualityTest(unittest.TestCase):
    def test_calibration_metrics(self):
        self.assertAlmostEqual(brier_score([0.9, 0.1], [1, 0]), 0.01)
        self.assertAlmostEqual(log_loss([0.9, 0.1], [1, 0]), -math.log(0.9))
        self.assertTrue(math.isinf(log_loss([0.0], [1])))
        buckets = reliability_buckets([0.55, 0.56, 0.75], [1, 0, 1])
        self.assertEqual(sum(b.count for b in buckets), 3)

    def test_economics_stays_unknown_without_costs(self):
        self.assertIsNone(net_expectancy(10.0, None))
        self.assertEqual(net_expectancy(10.0, 3.0), 7.0)

    def test_multiple_testing_is_explicit(self):
        self.assertEqual(multiple_testing_status(10, 4, 0), "ACCOUNTED")
        self.assertEqual(multiple_testing_status(10, 4, 2), "REUSED_OOS")

    def test_drift_and_attribution(self):
        self.assertTrue(mean_probability_drift([0.60,0.61], [0.80,0.81], 0.10))
        trade = TradeAttribution("T1", 100, 101, 105, 104, 3, 0.5, 0.25, 20)
        self.assertAlmostEqual(post_trade_net_pnl(trade), 2.25)

    def test_single_trade_cannot_promote(self):
        self.assertFalse(single_trade_may_promote_strategy(1))
        self.assertFalse(single_trade_may_promote_strategy(1000))

if __name__ == "__main__":
    unittest.main()
