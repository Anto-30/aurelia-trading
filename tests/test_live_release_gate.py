import os
import unittest
from unittest.mock import patch

import scripts.live_release_gate as gate


class LiveReleaseGateTests(unittest.TestCase):
    def test_current_repository_is_fail_closed(self):
        with self.assertRaises(RuntimeError) as ctx:
            gate.check_certification_evidence()
        self.assertIn("strict certification evidence block", str(ctx.exception))

    def test_invalid_deriv_auth_mode_is_rejected(self):
        env = {
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
            "DERIV_AUTH_MODE": "deriv_auth_token",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(RuntimeError, "DERIV_AUTH_MODE must be pat or oauth"):
                gate.check_environment()

    def test_oauth_mode_does_not_require_pat_application_id(self):
        env = {
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
            "DERIV_AUTH_MODE": "oauth",
            "DERIV_APP_ID": "",
        }
        with patch.dict(os.environ, env, clear=False):
            gate.check_environment()

    def test_release_gate_cannot_use_missing_session_evidence(self):
        original = gate.SESSION_EVIDENCE_PATH
        try:
            gate.SESSION_EVIDENCE_PATH = gate.ROOT / "artifacts" / "definitely-missing-session.json"
            with self.assertRaises(RuntimeError):
                gate.check_session_evidence()
        finally:
            gate.SESSION_EVIDENCE_PATH = original


if __name__ == "__main__":
    unittest.main()
