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


if __name__ == "__main__":
    unittest.main()
