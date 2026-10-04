import unittest

from runtime.ops.latency import LatencyMetrics


class LatencyMetricsTests(unittest.TestCase):
    def test_percentiles(self):
        metrics = LatencyMetrics()
        for value in (1, 2, 3, 4, 5):
            metrics.observe("broker_submission", value)
        summary = metrics.summary("broker_submission")
        self.assertEqual(summary["count"], 5)
        self.assertEqual(summary["p50_ms"], 3.0)
        self.assertIsNotNone(summary["p95_ms"])
        self.assertIsNotNone(summary["p99_ms"])

    def test_invalid_latency_rejected(self):
        metrics = LatencyMetrics()
        with self.assertRaises(ValueError):
            metrics.observe("broker_submission", -1)


if __name__ == "__main__":
    unittest.main()
