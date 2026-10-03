from __future__ import annotations

import unittest

from runtime.adapters.deriv_session import (
    MODERN_OPTIONS_WS_HOST,
    validate_modern_options_ws_url,
)


class ModernDerivEndpointPolicyTests(unittest.TestCase):
    def test_real_modern_endpoint_is_accepted(self) -> None:
        url = (
            f"wss://{MODERN_OPTIONS_WS_HOST}"
            "/trading/v1/options/ws/real?otp=redacted"
        )
        self.assertTrue(
            validate_modern_options_ws_url(url, expected_environment="real")
        )

    def test_demo_modern_endpoint_is_accepted(self) -> None:
        url = (
            f"wss://{MODERN_OPTIONS_WS_HOST}"
            "/trading/v1/options/ws/demo?otp=redacted"
        )
        self.assertTrue(
            validate_modern_options_ws_url(url, expected_environment="demo")
        )

    def test_legacy_endpoint_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            validate_modern_options_ws_url(
                "wss://ws.derivws.com/websockets/v3/legacy"
            )

    def test_wrong_modern_path_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            validate_modern_options_ws_url(
                "wss://api.derivws.com/websockets/v3/"
            )

    def test_otp_is_not_required_in_documented_validator(self) -> None:
        # OTP is supplied by the broker's authenticated bootstrap response.
        # The validator must validate the host/path, not persist or require the
        # secret query value itself.
        url = (
            f"wss://{MODERN_OPTIONS_WS_HOST}"
            "/trading/v1/options/ws/real"
        )
        self.assertTrue(
            validate_modern_options_ws_url(url, expected_environment="real")
        )


if __name__ == "__main__":
    unittest.main()
