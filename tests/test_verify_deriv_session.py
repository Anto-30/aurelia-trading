import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from runtime.adapters.deriv_session import AuthenticatedWebSocketUrl
from scripts.verify_deriv_session import verify


class VerifyDerivSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_requires_explicit_login_binding(self):
        with patch.dict(
            os.environ,
            {
                "DERIV_AUTH_TOKEN": "TOKEN",
                "DERIV_AUTH_MODE": "oauth",
                "DERIV_ENVIRONMENT": "real",
                "DERIV_EXPECTED_LOGINID": "",
                "DERIV_EXPECTED_CURRENCY": "USD",
            },
            clear=True,
        ):
            with self.assertRaises(RuntimeError):
                await verify()

    async def test_verified_session_never_authorizes_capital(self):
        fake_session = type(
            "S",
            (),
            {
                "binding": type(
                    "B",
                    (),
                    {
                        "loginid": "CRREAL",
                        "environment": "real",
                        "account_type": "real",
                        "currency": "USD",
                    },
                )(),
                "websocket": AuthenticatedWebSocketUrl(
                    "CRREAL",
                    "wss://api.derivws.com/trading/v1/options/ws/real?otp=secret",
                ),
            },
        )()

        fake_identity = type(
            "I",
            (),
            {"loginid": "CRREAL", "environment": "real", "account_type": "real", "currency": "USD"},
        )()
        fake_balance = type(
            "C",
            (),
            {
                "is_valid": lambda self: True,
                "source": "deriv:balance",
                "currency": "USD",
                "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            },
        )()

        with patch.dict(
            os.environ,
            {
                "DERIV_AUTH_TOKEN": "TOKEN",
                "DERIV_AUTH_MODE": "oauth",
                "DERIV_ENVIRONMENT": "real",
                "DERIV_EXPECTED_LOGINID": "CRREAL",
                "DERIV_EXPECTED_CURRENCY": "USD",
            },
            clear=True,
        ), patch(
            "scripts.verify_deriv_session.DerivSessionManager.bootstrap",
            return_value=fake_session,
        ), patch(
            "scripts.verify_deriv_session.DerivAdapter.connect",
            new=AsyncMock(return_value=fake_identity),
        ), patch(
            "scripts.verify_deriv_session.DerivAdapter.get_balance",
            new=AsyncMock(return_value=fake_balance),
        ), patch(
            "scripts.verify_deriv_session.DerivAdapter.close",
            new=AsyncMock(),
        ):
            result = await verify()

        self.assertEqual(result["status"], "DERIV_AUTHENTICATED_SESSION_VERIFIED")
        self.assertEqual(result["capital_authorization"]["FINAL_EXECUTION_AUTHORIZATION"], False)
        self.assertEqual(result["capital_authorization"]["LIVE_EXECUTION"], "BLOCKED")
        self.assertNotIn("secret", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
