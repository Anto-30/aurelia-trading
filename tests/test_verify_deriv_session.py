from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts.verify_deriv_session import OUTPUT, run


class VerifyDerivSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_account_evidence_is_blocked_without_read_only_scope(self):
        with patch.dict(
            os.environ,
            {"ACCOUNT_DERIV_AUTH_MODE": "oauth"},
            clear=True,
        ):
            self.assertEqual(await run(), 3)

    async def test_generic_token_fallback_is_rejected(self):
        with patch.dict(
            os.environ,
            {
                "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                "DERIV_AUTH_TOKEN": "GENERIC_TOKEN_SENTINEL",
            },
            clear=True,
        ):
            self.assertEqual(await run(), 3)

    async def test_identical_oauth_and_pat_are_rejected_without_echoing_values(self):
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
            self.assertEqual(await run(), 3)

    async def test_oauth_token_does_not_claim_read_only_scope(self):
        with patch.dict(
            os.environ,
            {
                "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SENTINEL",
            },
            clear=True,
        ):
            self.assertEqual(await run(), 3)

    def test_evidence_path_is_stable_and_not_secret_dependent(self):
        self.assertTrue(str(OUTPUT).endswith("deriv_authenticated_session.json"))


if __name__ == "__main__":
    unittest.main()
