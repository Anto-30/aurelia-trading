from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts.verify_deriv_transaction_lifecycle import run


class DerivTransactionLifecycleCurrencyTests(unittest.IsolatedAsyncioTestCase):

    async def test_unclassified_exception_details_are_never_printed(self):
        from scripts.verify_deriv_session import safe_deriv_error_reason

        private_text = "SYNTHETIC_PRIVATE_TOKEN_DO_NOT_LOG"
        self.assertEqual(
            safe_deriv_error_reason(ValueError(private_text)),
            "UNCLASSIFIED_VALUEERROR",
        )
        self.assertNotIn(private_text, safe_deriv_error_reason(ValueError(private_text)))

        output = io.StringIO()
        with patch(
            "scripts.verify_deriv_transaction_lifecycle.get_optional_secret"
        ) as secret_reader, patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivSessionManager.bootstrap"
        ) as bootstrap, redirect_stdout(output):
            result = await run()

        rendered = output.getvalue()
        self.assertEqual(result, 2)
        self.assertIn("REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", rendered)
        self.assertNotIn(private_text, rendered)
        secret_reader.assert_not_called()
        bootstrap.assert_not_called()


    async def test_allowlisted_deriv_internal_reason_is_preserved(self):
        from scripts.verify_deriv_session import safe_deriv_error_reason

        self.assertEqual(
            safe_deriv_error_reason(ValueError("ACCOUNT_ENVIRONMENT_MISMATCH")),
            "ACCOUNT_ENVIRONMENT_MISMATCH",
        )


    async def test_read_only_scope_gate_precedes_broker_and_secret_access(self):
        env = {
            "DERIV_LIFECYCLE_MODE": "VERIFY_ONLY",
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "EUR",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "scripts.verify_deriv_transaction_lifecycle.get_optional_secret",
            return_value="test-token",
        ), patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivSessionManager.bootstrap"
        ) as bootstrap:
            self.assertEqual(await run(), 2)
            bootstrap.assert_not_called()


    async def test_lifecycle_remains_held_before_credentials_or_broker_calls(self):
        import io
        from contextlib import redirect_stdout
        output = io.StringIO()
        with patch(
            "scripts.verify_deriv_transaction_lifecycle.get_optional_secret"
        ) as secret_reader, patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivSessionManager.bootstrap"
        ) as bootstrap, redirect_stdout(output):
            self.assertEqual(await run(), 2)
        secret_reader.assert_not_called()
        bootstrap.assert_not_called()
        self.assertIn("REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", output.getvalue())

if __name__ == "__main__":
    unittest.main()
