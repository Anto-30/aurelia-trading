import unittest

from runtime.adapters.deriv_session import (
    DerivSessionError,
    derive_ws_environment,
    validate_modern_options_ws_url,
)


class ModernDerivEndpointTests(unittest.TestCase):
    def test_modern_real_endpoint_is_accepted(self):
        url = "wss://api.derivws.com/trading/v1/options/ws/real?otp=REDACTED"
        self.assertTrue(validate_modern_options_ws_url(url, expected_environment="real"))
        self.assertEqual(derive_ws_environment(url), "real")

    def test_modern_demo_endpoint_is_accepted(self):
        url = "wss://api.derivws.com/trading/v1/options/ws/demo?otp=REDACTED"
        self.assertTrue(validate_modern_options_ws_url(url, expected_environment="demo"))
        self.assertEqual(derive_ws_environment(url), "demo")

    def test_legacy_endpoint_is_rejected(self):
        url = "wss://ws.derivws.com/trading/v1/options/ws/real?otp=REDACTED"
        with self.assertRaises(DerivSessionError):
            validate_modern_options_ws_url(url, expected_environment="real")
        with self.assertRaises(DerivSessionError):
            derive_ws_environment(url)

    def test_wrong_path_is_rejected(self):
        url = "wss://api.derivws.com/legacy/options/ws/real?otp=REDACTED"
        with self.assertRaises(DerivSessionError):
            validate_modern_options_ws_url(url, expected_environment="real")


if __name__ == "__main__":
    unittest.main()
