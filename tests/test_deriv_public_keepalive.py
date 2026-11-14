from __future__ import annotations

import unittest

from scripts.verify_deriv_public_keepalive import build_keepalive_record


class DerivPublicKeepaliveEvidenceTests(unittest.TestCase):
    def _record(self, **overrides):
        values = {
            "source_sha": "a" * 40,
            "started_at_utc": "2026-11-14T15:00:00+00:00",
            "ended_at_utc": "2026-11-14T15:01:05+00:00",
            "requested_duration_seconds": 65,
            "actual_elapsed_seconds": 65.0,
            "tick_count": 60,
            "keepalive_attempts": 2,
            "keepalive_successes": 2,
            "failure_type": None,
        }
        values.update(overrides)
        return values

    def test_pass_requires_two_successful_application_pings_and_live_ticks(self):
        record = build_keepalive_record(**self._record())
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["keepalive_attempts"], 2)
        self.assertEqual(record["keepalive_successes"], 2)
        self.assertFalse(record["authentication_used"])
        self.assertFalse(record["capital_authority_granted"])
        self.assertFalse(record["order_submission_permitted"])
        self.assertEqual(record["live_execution"], "BLOCKED")
        self.assertEqual(len(record["record_hash"]), 64)

    def test_one_successful_ping_is_not_a_two_interval_keepalive_proof(self):
        record = build_keepalive_record(**self._record(
            keepalive_attempts=1,
            keepalive_successes=1,
        ))
        self.assertEqual(record["status"], "FAIL")

    def test_no_live_ticks_is_not_a_pass(self):
        record = build_keepalive_record(**self._record(tick_count=0))
        self.assertEqual(record["status"], "FAIL")

    def test_transport_failure_is_recorded_as_failure_without_raw_error(self):
        record = build_keepalive_record(**self._record(failure_type="DerivTransportError"))
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["failure_type"], "DerivTransportError")
        self.assertNotIn("raw_error", record)


if __name__ == "__main__":
    unittest.main()
