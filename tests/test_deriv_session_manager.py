import unittest

from runtime.adapters.deriv_session import DerivSessionError
from runtime.adapters.session_manager import (
    DerivSessionManager,
    DerivSessionManagerError,
    derive_ws_environment,
    redact_ws_url,
)


class SessionManagerContractTests(unittest.TestCase):
    def test_derives_real_environment_from_otp_url(self):
        self.assertEqual(
            derive_ws_environment("wss://api.derivws.com/trading/v1/options/ws/real?otp=abc"),
            "real",
        )

    def test_derives_demo_environment_from_otp_url(self):
        self.assertEqual(
            derive_ws_environment("wss://api.derivws.com/trading/v1/options/ws/demo?otp=abc"),
            "demo",
        )

    def test_rejects_unknown_environment(self):
        with self.assertRaises(DerivSessionError):
            derive_ws_environment("wss://api.derivws.com/trading/v1/options/ws/test?otp=abc")

    def test_redacts_otp_from_logs(self):
        value = "wss://api.derivws.com/trading/v1/options/ws/real?otp=SECRET-ONE-TIME"
        self.assertEqual(redact_ws_url(value), "wss://api.derivws.com/trading/v1/options/ws/real")

    def test_manager_refuses_real_account_without_explicit_binding(self):
        manager = DerivSessionManager(expected_loginid="", expected_environment="real")
        with self.assertRaises(ValueError):
            manager.validate_binding(loginid="CRREAL", environment="real")

    def test_manager_accepts_exact_real_binding(self):
        manager = DerivSessionManager(expected_loginid="CRREAL", expected_environment="real")
        self.assertTrue(manager.validate_binding(loginid="CRREAL", environment="real"))

    def test_account_selection_requires_explicit_expected_currency(self):
        manager = DerivSessionManager(expected_loginid="CRREAL", expected_environment="real", expected_currency="")
        with self.assertRaisesRegex(DerivSessionManagerError, "EXPECTED_CURRENCY_REQUIRED"):
            manager.select_account([{"account_id": "CRREAL", "account_type": "real", "currency": "USD"}])

    def test_account_selection_rejects_missing_observed_currency(self):
        manager = DerivSessionManager(expected_loginid="CRREAL", expected_environment="real", expected_currency="USD")
        with self.assertRaisesRegex(DerivSessionManagerError, "ACCOUNT_CURRENCY_UNVERIFIED"):
            manager.select_account([{"account_id": "CRREAL", "account_type": "real"}])

    def test_account_selection_normalizes_observed_currency(self):
        manager = DerivSessionManager(expected_loginid="CRREAL", expected_environment="real", expected_currency="usd")
        binding = manager.select_account([{"account_id": "CRREAL", "account_type": "real", "currency": "USD"}])
        self.assertEqual(binding.currency, "USD")

    def test_manager_rejects_account_environment_mismatch(self):
        manager = DerivSessionManager(expected_loginid="CRREAL", expected_environment="real")
        with self.assertRaises(ValueError):
            manager.validate_binding(loginid="CRREAL", environment="demo")


    def test_oauth_account_list_omits_pat_only_app_id_header(self):
        import json
        import os
        from unittest.mock import patch

        from runtime.adapters.session_manager import ACCOUNTS_ENDPOINT

        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"data": []}).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response()

        manager = DerivSessionManager(expected_environment="real", expected_currency="USD")
        with patch.dict(os.environ, {"DERIV_AUTH_MODE": "oauth"}, clear=False):
            with patch("runtime.adapters.session_manager.urlopen", side_effect=fake_urlopen):
                self.assertEqual(
                    manager.list_accounts(bearer_token="opaque-token", app_id="12345"),
                    [],
                )

        request = captured["request"]
        self.assertEqual(request.full_url, ACCOUNTS_ENDPOINT)
        self.assertIsNone(request.get_header("Deriv-app-id"))
        self.assertEqual(request.get_header("Authorization"), "Bearer opaque-token")

    def test_pat_account_list_includes_app_id_header(self):
        import json
        import os
        from unittest.mock import patch

        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"data": []}).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return Response()

        manager = DerivSessionManager(expected_environment="real", expected_currency="USD")
        with patch.dict(os.environ, {"DERIV_AUTH_MODE": "pat"}, clear=False):
            with patch("runtime.adapters.session_manager.urlopen", side_effect=fake_urlopen):
                manager.list_accounts(bearer_token="opaque-token", app_id="12345")

        self.assertEqual(captured["request"].get_header("Deriv-app-id"), "12345")

    def test_unknown_auth_mode_fails_closed_before_account_request(self):
        import os
        from unittest.mock import patch

        manager = DerivSessionManager(expected_environment="real", expected_currency="USD")
        with patch.dict(os.environ, {"DERIV_AUTH_MODE": "unknown"}, clear=False):
            with patch("runtime.adapters.session_manager.urlopen") as mocked_urlopen:
                with self.assertRaisesRegex(DerivSessionManagerError, "UNSUPPORTED_AUTH_MODE"):
                    manager.list_accounts(bearer_token="opaque-token", app_id="12345")
        mocked_urlopen.assert_not_called()


    def test_otp_session_rejects_unknown_auth_mode_before_network_request(self):
        import os
        from unittest.mock import patch

        from runtime.adapters.deriv_session import get_authenticated_ws_url

        with patch.dict(os.environ, {"DERIV_AUTH_MODE": "unknown"}, clear=False):
            with patch("runtime.adapters.deriv_session.urlopen") as mocked_urlopen:
                with self.assertRaisesRegex(DerivSessionError, "UNSUPPORTED_AUTH_MODE"):
                    get_authenticated_ws_url(
                        "CR123456",
                        bearer_token="opaque-token",
                        app_id="12345",
                    )
        mocked_urlopen.assert_not_called()

    def test_missing_auth_mode_fails_closed_before_account_request(self):
        import os
        from unittest.mock import patch

        manager = DerivSessionManager(expected_environment="real", expected_currency="USD")
        with patch.dict(os.environ, {}, clear=True):
            with patch("runtime.adapters.session_manager.urlopen") as mocked_urlopen:
                with self.assertRaisesRegex(DerivSessionManagerError, "UNSUPPORTED_AUTH_MODE"):
                    manager.list_accounts(bearer_token="opaque-token", app_id="12345")
        mocked_urlopen.assert_not_called()

    def test_missing_auth_mode_fails_closed_before_otp_network_request(self):
        import os
        from unittest.mock import patch
        from runtime.adapters.deriv_session import get_authenticated_ws_url

        with patch.dict(os.environ, {}, clear=True):
            with patch("runtime.adapters.deriv_session.urlopen") as mocked_urlopen:
                with self.assertRaisesRegex(DerivSessionError, "UNSUPPORTED_AUTH_MODE"):
                    get_authenticated_ws_url(
                        "CR123456", bearer_token="opaque-token", app_id="12345"
                    )
        mocked_urlopen.assert_not_called()

    def test_oauth_bootstrap_uses_oauth_token_and_never_passes_pat_app_id(self):
        import os
        from types import SimpleNamespace
        from unittest.mock import patch

        manager = DerivSessionManager(
            expected_loginid="CRREAL",
            expected_environment="real",
            expected_currency="USD",
        )
        rows = [{"account_id": "CRREAL", "account_type": "real", "currency": "USD"}]
        websocket = SimpleNamespace(
            url="wss://api.derivws.com/trading/v1/options/ws/real?otp=opaque"
        )
        with patch.dict(
            os.environ,
            {
                "DERIV_AUTH_MODE": "oauth",
                "DERIV_AUTH_TOKEN": "opaque-oauth",
                "DERIV_PAT": "opaque-pat",
                "DERIV_APP_ID": "pat-only-app",
            },
            clear=True,
        ):
            with patch.object(manager, "list_accounts", return_value=rows) as list_accounts:
                with patch(
                    "runtime.adapters.session_manager.get_authenticated_ws_url",
                    return_value=websocket,
                ) as otp:
                    manager.bootstrap()
        list_accounts.assert_called_once_with(
            bearer_token="opaque-oauth",
            app_id=None,
        )
        otp.assert_called_once_with(
            "CRREAL",
            bearer_token="opaque-oauth",
            app_id=None,
            timeout_seconds=manager.timeout_seconds,
        )

    def test_missing_auth_mode_blocks_bootstrap_before_account_request(self):
        import os
        from unittest.mock import patch

        manager = DerivSessionManager(
            expected_loginid="CRREAL",
            expected_environment="real",
            expected_currency="USD",
        )
        with patch.dict(
            os.environ,
            {"DERIV_AUTH_TOKEN": "opaque-oauth", "DERIV_PAT": "opaque-pat"},
            clear=True,
        ):
            with patch.object(manager, "list_accounts") as list_accounts:
                with self.assertRaisesRegex(
                    DerivSessionManagerError, "UNSUPPORTED_AUTH_MODE"
                ):
                    manager.bootstrap()
        list_accounts.assert_not_called()

if __name__ == "__main__":
    unittest.main()
