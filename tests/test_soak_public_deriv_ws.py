"""Regression tests for Deriv application-level WebSocket heartbeat handling."""

import unittest

from tools import soak_public_deriv_ws as soak


class ApplicationPingTests(unittest.TestCase):
    def test_ping_builder_uses_new_api_request_shape(self):
        builder = getattr(soak, "build_application_ping_payload", None)
        self.assertTrue(
            callable(builder),
            "missing build_application_ping_payload: application-level Deriv ping is required",
        )
        self.assertEqual(builder(736002), {"ping": 1, "req_id": 736002})

    def test_response_matcher_correlates_only_successful_matching_ping(self):
        matcher = getattr(soak, "is_application_ping_response", None)
        self.assertTrue(
            callable(matcher),
            "missing is_application_ping_response: ping responses must be correlated",
        )
        self.assertTrue(matcher({"msg_type": "ping", "req_id": 736002}, 736002))
        self.assertFalse(matcher({"msg_type": "ping", "req_id": 736003}, 736002))
        self.assertFalse(matcher({"msg_type": "tick", "req_id": 736002}, 736002))
        self.assertFalse(
            matcher(
                {"msg_type": "ping", "req_id": 736002, "error": {"code": "FixtureError"}},
                736002,
            )
        )


if __name__ == "__main__":
    unittest.main()
