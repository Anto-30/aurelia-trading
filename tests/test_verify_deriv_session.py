from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts.verify_deriv_session import run


class VerifyDerivSessionTests(unittest.TestCase):
    def test_verifier_fails_closed_before_reading_credentials_or_network(self) -> None:
        marker = "SYNTHETIC_DERIV_SECRET_SENTINEL"
        with patch.dict(
            os.environ,
            {
                "DERIV_AUTH_TOKEN": marker,
                "DERIV_PAT": marker,
                "DERIV_OAUTH_ACCESS_TOKEN": marker,
                "DERIV_APP_ID": "SYNTHETIC_APP_ID",
                "DERIV_EXPECTED_LOGINID": "SYNTHETIC_ACCOUNT_ID",
                "DERIV_EXPECTED_CURRENCY": "USD",
            },
            clear=True,
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                result = run()

        self.assertEqual(result, 3)
        text = output.getvalue()
        self.assertIn(
            "DERIV_AUTH_SESSION_REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            text,
        )
        self.assertIn("DERIV_ORDERS_SUBMITTED=0", text)
        self.assertIn("DERIV_CAPITAL_AUTHORITY_GRANTED=false", text)
        self.assertIn("LIVE_EXECUTION=BLOCKED", text)
        self.assertIn("FINAL_EXECUTION_AUTHORIZATION=false", text)
        self.assertNotIn(marker, text)
        self.assertNotIn("SYNTHETIC_APP_ID", text)
        self.assertNotIn("SYNTHETIC_ACCOUNT_ID", text)

    def test_verifier_blocks_when_no_environment_is_configured(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            output = io.StringIO()
            with redirect_stdout(output):
                result = run()
        self.assertEqual(result, 3)
        self.assertIn(
            "DERIV_AUTH_SESSION_REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            output.getvalue(),
        )

    def test_verifier_does_not_expose_or_use_authenticated_adapter(self) -> None:
        import inspect
        import scripts.verify_deriv_session as module

        source = inspect.getsource(module)
        self.assertNotIn("get_optional_secret", source)
        self.assertNotIn("DerivSessionManager", source)
        self.assertNotIn("DerivAdapter", source)
        self.assertNotIn("DERIV_AUTH_TOKEN", source)
        self.assertNotIn("DERIV_PAT", source)


if __name__ == "__main__":
    unittest.main()
