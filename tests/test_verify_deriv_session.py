import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts.verify_deriv_session import run


class VerifyDerivSessionTests(unittest.IsolatedAsyncioTestCase):
    async def _assert_blocked_without_secret_access(self) -> None:
        output = io.StringIO()
        with patch(
            "scripts.verify_deriv_session.get_optional_secret"
        ) as secret_reader, redirect_stdout(output):
            result = await run()
        self.assertEqual(result, 3)
        self.assertIn(
            "DERIV_AUTH_SESSION_REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            output.getvalue(),
        )
        secret_reader.assert_not_called()

    async def test_real_account_verification_is_blocked_before_reading_credentials(self):
        with patch.dict(os.environ, {"DERIV_ENVIRONMENT": "real"}, clear=True):
            await self._assert_blocked_without_secret_access()

    async def test_demo_account_verification_is_also_blocked_before_reading_credentials(self):
        with patch.dict(os.environ, {"DERIV_ENVIRONMENT": "demo"}, clear=True):
            await self._assert_blocked_without_secret_access()


if __name__ == "__main__":
    unittest.main()
