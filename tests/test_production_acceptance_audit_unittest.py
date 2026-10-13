import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

from scripts.deriv_auth_prerequisites import build_evidence
from runtime.adapters.deriv_session import DerivSessionError, get_authenticated_ws_url
from runtime.adapters.session_manager import DerivSessionManager, DerivSessionManagerError
from runtime.core.paths import state_path

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


    def test_nested_or_nonstandard_deriv_websocket_path_is_rejected(self):
        from runtime.adapters.deriv_session import validate_modern_options_ws_url

        for url in (
            "wss://api.derivws.com:444/trading/v1/options/ws/real",
            "wss://api.derivws.com/trading/v1/options/ws/extra/real",
            "wss://user@api.derivws.com/trading/v1/options/ws/real",
            "wss://api.derivws.com/trading/v1/options/ws/real#fragment",
        ):
            with self.subTest(url=url):
                with self.assertRaises(DerivSessionError):
                    validate_modern_options_ws_url(url)

    def test_deriv_pat_alias_is_used_for_otp_bootstrap(self):
        from runtime.adapters.deriv_session import get_authenticated_ws_url

        response = unittest.mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = (
            b'{"data":{"url":"wss://api.derivws.com/trading/v1/options/ws/real?otp=redacted"}}'
        )
        with patch.dict("os.environ", {"DERIV_AUTH_MODE": "pat"}, clear=True):
            with patch(
                "runtime.adapters.deriv_session.get_optional_secret",
                side_effect=lambda name: {"DERIV_PAT": "test-pat"}.get(name),
            ), patch(
                "runtime.adapters.deriv_session.urlopen", return_value=response
            ) as open_url:
                result = get_authenticated_ws_url("CR123", app_id="test-app")
        self.assertEqual(result.account_id, "CR123")
        self.assertIn("DERIV_PAT", repr(open_url.call_args))
        self.assertNotIn("test-pat", repr(result))

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



class DurableStatePathTests(unittest.TestCase):
    def test_state_path_defaults_outside_os_temp_directory(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(
                str(state_path("AURELIA_JOURNAL_PATH", "events.ndjson")),
                "/var/lib/aurelia/events.ndjson",
            )

    def test_state_path_honors_state_directory_and_explicit_override(self):
        with patch.dict("os.environ", {"AURELIA_STATE_DIR": "/data/aurelia"}, clear=True):
            self.assertEqual(
                str(state_path("AURELIA_JOURNAL_PATH", "events.ndjson")),
                "/data/aurelia/events.ndjson",
            )
        with patch.dict(
            "os.environ",
            {
                "AURELIA_STATE_DIR": "/data/aurelia",
                "AURELIA_JOURNAL_PATH": "/custom/journal.ndjson",
            },
            clear=True,
        ):
            self.assertEqual(
                str(state_path("AURELIA_JOURNAL_PATH", "events.ndjson")),
                "/custom/journal.ndjson",
            )

if __name__ == "__main__":
    unittest.main()
