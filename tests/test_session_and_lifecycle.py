import unittest
from unittest.mock import patch

from runtime.adapters.deriv_session import (
    DerivSessionError,
    AuthenticatedWebSocketUrl,
    get_authenticated_ws_url,
)
from runtime.adapters.deriv_lifecycle import BrokerLifecycleRecord
from runtime.core.models import BrokerOutcome


class SessionLifecycleTests(unittest.TestCase):
    def test_otp_always_blocks_without_read_only_account_scope(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(
                DerivSessionError,
                "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            ):
                get_authenticated_ws_url("CR123")

    def test_otp_does_not_compare_oauth_and_pat_values(self):
        marker = "SAME_SECRET_SENTINEL"
        with patch.dict(
            "os.environ",
            {
                "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                "DERIV_OAUTH_ACCESS_TOKEN": marker,
                "DERIV_PAT": marker,
            },
            clear=True,
        ):
            with self.assertRaisesRegex(DerivSessionError, "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"):
                get_authenticated_ws_url("CR123")

    def test_otp_never_uses_generic_token_fallback(self):
        with patch.dict(
            "os.environ",
            {
                "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                "DERIV_AUTH_TOKEN": "GENERIC_TOKEN_SENTINEL",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(DerivSessionError, "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"):
                get_authenticated_ws_url("CR123")

    def test_otp_fails_closed_for_oauth_without_read_only_scope(self):
        with patch.dict(
            "os.environ",
            {
                "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SECRET_SENTINEL",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                DerivSessionError,
                "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            ):
                get_authenticated_ws_url("CR123")

    def test_safe_url_does_not_expose_otp(self):
        auth = AuthenticatedWebSocketUrl(
            "CR123",
            "wss://example/ws/real?otp=SECRET",
        )
        self.assertEqual(auth.safe_url(), "wss://example/ws/real")

    def test_lifecycle_transitions(self):
        record = BrokerLifecycleRecord("I1", proposal_id="P1")
        accepted = record.with_broker_acceptance("TX1", "C1")
        settled = accepted.settled()
        self.assertEqual(accepted.outcome, BrokerOutcome.ACCEPTED)
        self.assertEqual(settled.outcome, BrokerOutcome.SETTLED)
        self.assertEqual(settled.transaction_id, "TX1")


if __name__ == "__main__":
    unittest.main()
