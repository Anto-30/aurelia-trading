import json
import unittest
from unittest.mock import patch

from runtime.adapters.deriv_session import (
    DerivSessionError,
    AuthenticatedWebSocketUrl,
    get_authenticated_ws_url,
)
from runtime.adapters.deriv_lifecycle import BrokerLifecycleRecord
from runtime.core.models import BrokerOutcome


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class SessionLifecycleTests(unittest.TestCase):
    def test_otp_requires_token(self):
        with patch.dict("os.environ", {"DERIV_AUTH_TOKEN": ""}, clear=True):
            with self.assertRaises(DerivSessionError):
                get_authenticated_ws_url("CR123")

    def test_otp_uses_provided_token_and_validates_returned_url(self):
        response = FakeResponse({
            "data": {
                "url": "wss://api.derivws.com/trading/v1/options/ws/real?otp=ONE-TIME"
            }
        })
        with patch.dict("os.environ", {"DERIV_AUTH_MODE": "pat"}, clear=True), patch(
            "runtime.adapters.deriv_session.urlopen", return_value=response
        ) as urlopen:
            auth = get_authenticated_ws_url(
                "CR123", bearer_token="TEST-TOKEN", app_id="APP-123"
            )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertIn("Bearer TEST-TOKEN", str(request.header_items()))
        self.assertEqual(auth.account_id, "CR123")
        self.assertEqual(auth.safe_url(), "wss://api.derivws.com/trading/v1/options/ws/real")

    def test_safe_url_does_not_expose_otp(self):
        auth = AuthenticatedWebSocketUrl("CR123", "wss://example/ws/real?otp=SECRET")
        self.assertEqual(auth.safe_url(), "wss://example/ws/real")

    def test_lifecycle_transitions(self):
        record = BrokerLifecycleRecord("I1", proposal_id="P1")
        accepted = record.with_broker_acceptance("TX1", "C1")
        settled = accepted.settled()
        self.assertEqual(accepted.outcome, BrokerOutcome.ACCEPTED)
        self.assertEqual(settled.outcome, BrokerOutcome.SETTLED)


if __name__ == "__main__":
    unittest.main()
