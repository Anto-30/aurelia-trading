import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.live_release_gate as gate
from runtime.core.release_gate import read_live_release


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

    def test_readiness_is_recomputed_and_never_trusted_from_a_snapshot(self):
        current = {
            "final_execution_authorization": False,
            "live_execution": "BLOCKED",
            "blockers": [{"gate": "LIVE_RELEASE", "status": "FAIL"}],
        }
        with patch.object(gate, "evaluate_readiness", return_value=current) as evaluate:
            with self.assertRaisesRegex(RuntimeError, "dynamic readiness final_execution_authorization is false"):
                gate.check_readiness()
        evaluate.assert_called_once_with(gate.ROOT)

    def test_dynamic_readiness_rejects_blockers_even_if_authorization_flag_is_true(self):
        current = {
            "final_execution_authorization": True,
            "live_execution": "ENABLED",
            "blockers": [{"gate": "PROSPECTIVE_OOS", "status": "FAIL"}],
        }
        with patch.object(gate, "evaluate_readiness", return_value=current):
            with self.assertRaisesRegex(RuntimeError, "dynamic readiness blockers present"):
                gate.check_readiness()

    def test_dynamic_readiness_requires_a_well_formed_payload(self):
        with patch.object(gate, "evaluate_readiness", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "invalid payload"):
                gate.check_readiness()

    def test_unsupported_currency_is_rejected(self):
        env = {
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "EUR",
            "DERIV_ENVIRONMENT": "real",
            "DERIV_AUTH_MODE": "oauth",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(RuntimeError, "DERIV_EXPECTED_CURRENCY must be USD"):
                gate.check_environment()

    def test_release_gate_cannot_use_missing_session_evidence(self):
        original = gate.SESSION_EVIDENCE_PATH
        try:
            gate.SESSION_EVIDENCE_PATH = gate.ROOT / "artifacts" / "definitely-missing-session.json"
            with self.assertRaises(RuntimeError):
                gate.check_session_evidence()
        finally:
            gate.SESSION_EVIDENCE_PATH = original

    def test_live_release_requires_live_execution_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "LIVE_LOCK.yaml"
            lock.write_text(
                "live_trading_enabled: true\n"
                "FINAL_EXECUTION_AUTHORIZATION: true\n"
                "capital_plane_mode: LIVE\n"
                "LIVE_EXECUTION: ENABLED\n",
                encoding="utf-8",
            )
            self.assertTrue(read_live_release(lock).may_move_capital)

    def test_live_release_blocks_when_execution_field_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "LIVE_LOCK.yaml"
            lock.write_text(
                "live_trading_enabled: true\n"
                "FINAL_EXECUTION_AUTHORIZATION: true\n"
                "capital_plane_mode: LIVE\n"
                "LIVE_EXECUTION: BLOCKED\n",
                encoding="utf-8",
            )
            self.assertFalse(read_live_release(lock).may_move_capital)

    def test_live_release_blocks_when_execution_field_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "LIVE_LOCK.yaml"
            lock.write_text(
                "live_trading_enabled: true\n"
                "FINAL_EXECUTION_AUTHORIZATION: true\n"
                "capital_plane_mode: LIVE\n",
                encoding="utf-8",
            )
            self.assertFalse(read_live_release(lock).may_move_capital)


if __name__ == "__main__":
    unittest.main()
