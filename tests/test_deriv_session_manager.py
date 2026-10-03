import unittest

from runtime.adapters.session_manager import (
    DerivSessionManager,
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
        with self.assertRaises(ValueError):
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

    def test_manager_rejects_account_environment_mismatch(self):
        manager = DerivSessionManager(expected_loginid="CRREAL", expected_environment="real")
        with self.assertRaises(ValueError):
            manager.validate_binding(loginid="CRREAL", environment="demo")


if __name__ == "__main__":
    unittest.main()
