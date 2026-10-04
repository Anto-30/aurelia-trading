import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from runtime.core.models import AccountIdentity, CapitalSnapshot
from scripts.verify_deriv_session import run
from assurance.evidence_writer import payload_sha256


class VerifyDerivSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_token_is_not_verified(self):
        with patch.dict(
            os.environ,
            {
                "DERIV_AUTH_TOKEN": "",
                "DERIV_EXPECTED_LOGINID": "CRREAL",
                "DERIV_ENVIRONMENT": "real",
                "DERIV_EXPECTED_CURRENCY": "USD",
            },
            clear=True,
        ):
            self.assertEqual(await run(), 2)

    async def test_real_session_verifies_without_authorizing_capital(self):
        account = AccountIdentity(
            loginid="CRREAL",
            account_type="real",
            currency="USD",
            environment="real",
        )
        snapshot = CapitalSnapshot(
            balance=8.01,
            currency="USD",
            available_balance=8.01,
            captured_at=datetime.now(timezone.utc),
            source="deriv:balance",
            account=account,
        )
        bootstrap = SimpleNamespace(
            binding=account,
            websocket=SimpleNamespace(
                url="wss://api.derivws.com/trading/v1/options/ws/real?otp=SECRET",
                source="deriv:options:otp",
            ),
            safe_websocket_url="wss://api.derivws.com/trading/v1/options/ws/real",
        )

        captured = {}

        with patch.dict(
            os.environ,
            {
                "DERIV_AUTH_TOKEN": "TOKEN",
                "DERIV_EXPECTED_LOGINID": "CRREAL",
                "DERIV_ENVIRONMENT": "real",
                "DERIV_EXPECTED_CURRENCY": "USD",
                "DERIV_AUTH_MODE": "pat",
                "DERIV_APP_ID": "APP-TEST",
                "GITHUB_SHA": "TEST",
                "DERIV_EVIDENCE_OUT": "/tmp/aurelia-test-evidence.json",
            },
            clear=True,
        ), patch(
            "scripts.verify_deriv_session.DerivSessionManager.bootstrap",
            return_value=bootstrap,
        ), patch(
            "scripts.verify_deriv_session.DerivAdapter.connect",
            new=AsyncMock(return_value=account),
        ), patch(
            "scripts.verify_deriv_session.DerivAdapter.get_balance",
            new=AsyncMock(return_value=snapshot),
        ), patch(
            "scripts.verify_deriv_session.DerivAdapter.close",
            new=AsyncMock(),
        ), patch(
            "scripts.verify_deriv_session.write_evidence",
            side_effect=lambda path, record: captured.update(record=dict(record)),
        ):
            result = await run()

        self.assertEqual(result, 0)
        record = captured["record"]
        self.assertEqual(
            record["record_hash"],
            payload_sha256({key: value for key, value in record.items() if key != "record_hash"}),
        )
        self.assertFalse(record["capital_authority_granted"])
        self.assertEqual(record["orders_submitted"], 0)
        self.assertEqual(record["provenance"]["origin"], "ci")
        self.assertEqual(record["provenance"]["source_commit"], "TEST")


    async def test_demo_session_verifies_without_authorizing_capital(self):
        account = AccountIdentity(
            loginid="CRDEMO",
            account_type="demo",
            currency="USD",
            environment="demo",
        )
        snapshot = CapitalSnapshot(
            balance=10000.0,
            currency="USD",
            available_balance=10000.0,
            captured_at=datetime.now(timezone.utc),
            source="deriv:balance",
            account=account,
        )
        bootstrap = SimpleNamespace(
            binding=account,
            websocket=SimpleNamespace(
                url="wss://api.derivws.com/trading/v1/options/ws/demo?otp=SECRET",
                source="deriv:options:otp",
            ),
            safe_websocket_url="wss://api.derivws.com/trading/v1/options/ws/demo",
        )
        captured = {}

        with patch.dict(
            os.environ,
            {
                "DERIV_AUTH_TOKEN": "TOKEN",
                "DERIV_EXPECTED_LOGINID": "CRDEMO",
                "DERIV_ENVIRONMENT": "demo",
                "DERIV_EXPECTED_CURRENCY": "USD",
                "DERIV_AUTH_MODE": "pat",
                "DERIV_APP_ID": "APP-TEST",
                "GITHUB_SHA": "TEST-DEMO",
                "DERIV_EVIDENCE_OUT": "/tmp/aurelia-demo-test-evidence.json",
            },
            clear=True,
        ), patch(
            "scripts.verify_deriv_session.DerivSessionManager.bootstrap",
            return_value=bootstrap,
        ), patch(
            "scripts.verify_deriv_session.DerivAdapter.connect",
            new=AsyncMock(return_value=account),
        ), patch(
            "scripts.verify_deriv_session.DerivAdapter.get_balance",
            new=AsyncMock(return_value=snapshot),
        ), patch(
            "scripts.verify_deriv_session.DerivAdapter.close",
            new=AsyncMock(),
        ), patch(
            "scripts.verify_deriv_session.write_evidence",
            side_effect=lambda path, record: captured.update(record=dict(record)),
        ):
            result = await run()

        self.assertEqual(result, 0)
        record = captured["record"]
        self.assertEqual(record["verification_scope"], "AUTHENTICATED_DERIV_DEMO_SESSION")
        self.assertFalse(record["capital_authority_granted"])
        self.assertFalse(record["order_submission_permitted"])
        self.assertEqual(record["orders_submitted"], 0)


if __name__ == "__main__":
    unittest.main()
