from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from runtime.strategy.autonomous_signal_engine import AutonomousSignalHunter


class AutonomousSignalHunterTests(unittest.TestCase):
    def test_warmup_produces_no_candidate(self):
        hunter = AutonomousSignalHunter(min_observations=20)
        now = datetime.now(timezone.utc)
        for i in range(10):
            self.assertIsNone(
                hunter.observe(symbol="R_100", quote=100.0 + i * 0.01, received_at=now + timedelta(seconds=i))
            )

    def test_candidate_is_explicitly_research_only(self):
        hunter = AutonomousSignalHunter(min_observations=20, threshold=1.0, cooldown_seconds=0)
        now = datetime.now(timezone.utc)
        prices = [100.0 + (i * 0.01) for i in range(25)]
        prices[-1] = 100.2
        candidate = None
        for i, price in enumerate(prices):
            candidate = hunter.observe(
                symbol="R_100", quote=price, received_at=now + timedelta(seconds=i)
            ) or candidate
        self.assertIsNotNone(candidate)
        payload = hunter.as_message_payload(candidate)
        self.assertEqual(payload["probability_status"], "UNCALIBRATED_RESEARCH_ONLY")
        self.assertFalse(payload["capital_authority"])
        self.assertFalse(payload["order_submission_permitted"])
        self.assertTrue(payload["research_only"])

    def test_out_of_policy_confidence_is_rejected_not_clipped(self):
        hunter = AutonomousSignalHunter(min_observations=20, threshold=0.1, cooldown_seconds=0)
        now = datetime.now(timezone.utc)
        candidate = None
        for i in range(19):
            candidate = hunter.observe(
                symbol="R_100", quote=100.0, received_at=now + timedelta(seconds=i)
            ) or candidate
        candidate = hunter.observe(
            symbol="R_100", quote=110.0, received_at=now + timedelta(seconds=19)
        )
        self.assertIsNone(candidate)

    def test_invalid_tick_is_rejected(self):
        hunter = AutonomousSignalHunter()
        self.assertIsNone(hunter.observe(symbol="", quote=100.0))
        self.assertIsNone(hunter.observe(symbol="R_100", quote=0.0))
        self.assertIsNone(hunter.observe(symbol="R_100", quote=float("nan")))


if __name__ == "__main__":
    unittest.main()
