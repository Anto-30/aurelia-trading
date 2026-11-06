from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts.verify_deriv_transaction_lifecycle import run


class DerivTransactionLifecycleGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_account_lifecycle_is_blocked_even_for_oauth_until_scope_is_proven(self):
        with patch.dict(
            os.environ,
            {
                "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SENTINEL",
                "DERIV_LIFECYCLE_MODE": "VERIFY_ONLY",
            },
            clear=True,
        ):
            self.assertEqual(await run(), 2)

    async def test_equal_pat_and_oauth_credentials_are_blocked(self):
        marker = "SAME_CREDENTIAL_SENTINEL"
        with patch.dict(
            os.environ,
            {
                "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                "DERIV_OAUTH_ACCESS_TOKEN": marker,
                "DERIV_PAT": marker,
            },
            clear=True,
        ):
            self.assertEqual(await run(), 2)


if __name__ == "__main__":
    unittest.main()
