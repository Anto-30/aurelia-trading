import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

from scripts.deriv_auth_prerequisites import build_evidence
from runtime.adapters.deriv_session import DerivSessionError, get_authenticated_ws_url
from runtime.adapters.session_manager import DerivSessionManager, DerivSessionManagerError

ROOT = Path(__file__).resolve().parents[1]


class ProductionAcceptanceAuditTests(unittest.TestCase):
    def test_production_acceptance_audit_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/production_acceptance_audit.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("AURELIA_PRODUCTION_ACCEPTANCE=AUDIT_PASS", result.stdout)
        self.assertIn("PROBABILITY_POLICY_RANGE=0.55..0.75", result.stdout)
        self.assertIn("CAPITAL_MOVEMENT_PERMITTED=false", result.stdout)
        self.assertIn("LIVE_EXECUTION=BLOCKED", result.stdout)


class DerivAuthPrerequisitesAliasTests(unittest.TestCase):
    def _env(self, **overrides):
        env = {
            "DERIV_AUTH_TOKEN": "",
            "DERIV_PAT": "",
            "DERIV_EXPECTED_LOGINID": "ACCOUNT_SENTINEL",
            "DERIV_AUTHORIZED_ACCOUNT_ID": "",
            "DERIV_AUTH_MODE": "pat",
            "DERIV_APP_ID": "APP_ID_SENTINEL",
            "DERIV_EXPECTED_CURRENCY": "USD",
        }
        env.update(overrides)
        return env

    def test_deriv_auth_token_configures_prerequisites_without_exposing_secret(self):
        secret = "TOKEN_SECRET_SENTINEL"
        result = build_evidence(self._env(DERIV_AUTH_TOKEN=secret))
        self.assertTrue(result["configured"])
        self.assertTrue(result["requirements"]["token_present"])
        self.assertNotIn(secret, repr(result))
        self.assertNotIn("ACCOUNT_SENTINEL", repr(result))
        self.assertNotIn("APP_ID_SENTINEL", repr(result))

    def test_deriv_pat_alias_configures_prerequisites(self):
        secret = "PAT_SECRET_SENTINEL"
        result = build_evidence(self._env(DERIV_PAT=secret))
        self.assertTrue(result["configured"])
        self.assertTrue(result["requirements"]["token_present"])
        self.assertNotIn(secret, repr(result))

    def test_missing_both_token_names_remains_not_ready(self):
        result = build_evidence(self._env())
        self.assertFalse(result["configured"])
        self.assertFalse(result["requirements"]["token_present"])

    def test_unsupported_currency_stays_not_ready(self):
        result = build_evidence(
            self._env(DERIV_PAT="PAT_SECRET", DERIV_EXPECTED_CURRENCY="KES")
        )
        self.assertFalse(result["configured"])
        self.assertFalse(result["requirements"]["expected_currency_present"])
        self.assertNotIn("PAT_SECRET", repr(result))


class DerivEndpointHardeningTests(unittest.TestCase):
    def test_account_id_path_injection_is_rejected_before_network(self):
        with patch("runtime.adapters.deriv_session.urlopen") as open_url:
            with self.assertRaisesRegex(DerivSessionError, "ACCOUNT_ID_INVALID"):
                get_authenticated_ws_url(
                    "CR123/../../attacker?x=1",
                    bearer_token="test-token",
                    app_id="test-app",
                )
            open_url.assert_not_called()

    def test_non_deriv_host_is_rejected_before_sending_bearer_token(self):
        manager = DerivSessionManager(
            expected_loginid="CR123",
            expected_environment="real",
            expected_currency="USD",
        )
        with patch("runtime.adapters.session_manager.urlopen") as open_url:
            with self.assertRaisesRegex(
                DerivSessionManagerError, "DERIV_ACCOUNT_ENDPOINT_INVALID"
            ):
                manager._request_json(
                    method="GET",
                    url="https://attacker.example/accounts",
                    bearer_token="test-token",
                    app_id="test-app",
                )
            open_url.assert_not_called()

    def test_malformed_port_is_rejected_without_leaking_parser_error(self):
        manager = DerivSessionManager(
            expected_loginid="CR123",
            expected_environment="real",
            expected_currency="USD",
        )
        with patch("runtime.adapters.session_manager.urlopen") as open_url:
            with self.assertRaisesRegex(
                DerivSessionManagerError, "DERIV_ACCOUNT_ENDPOINT_INVALID"
            ):
                manager._request_json(
                    method="GET",
                    url="https://api.derivws.com:invalid/accounts",
                    bearer_token="test-token",
                    app_id="test-app",
                )
            open_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
