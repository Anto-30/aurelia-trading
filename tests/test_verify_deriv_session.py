import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from runtime.core.models import AccountIdentity, CapitalSnapshot
from scripts.verify_deriv_session import run, safe_deriv_error_reason
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

    async def test_missing_currency_is_not_verified_before_broker_calls(self):
        with patch.dict(
            os.environ,
            {
                "DERIV_AUTH_TOKEN": "TOKEN",
                "DERIV_APP_ID": "APP-ID-TEST",
                "DERIV_EXPECTED_LOGINID": "CRREAL",
                "DERIV_ENVIRONMENT": "real",
            },
            clear=True,
        ), patch("scripts.verify_deriv_session.DerivSessionManager.bootstrap") as bootstrap:
            self.assertEqual(await run(), 2)
            bootstrap.assert_not_called()

    async def test_unsupported_currency_is_blocked_before_broker_calls(self):
        with patch.dict(
            os.environ,
            {
                "DERIV_AUTH_TOKEN": "TOKEN",
                "DERIV_APP_ID": "APP-ID-TEST",
                "DERIV_EXPECTED_LOGINID": "CRREAL",
                "DERIV_ENVIRONMENT": "real",
                "DERIV_EXPECTED_CURRENCY": "EUR",
            },
            clear=True,
        ), patch("scripts.verify_deriv_session.DerivSessionManager.bootstrap") as bootstrap:
            self.assertEqual(await run(), 3)
            bootstrap.assert_not_called()

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
                "DERIV_APP_ID": "APP-ID-TEST",
                "DERIV_EXPECTED_LOGINID": "CRREAL",
                "DERIV_ENVIRONMENT": "real",
                "DERIV_EXPECTED_CURRENCY": "USD",
                "GITHUB_SHA": "TEST",
                "DERIV_EVIDENCE_OUT": "/tmp/aurelia-test-evidence.json",
            },
            clear=True,
        ), patch(
            "scripts.verify_deriv_session.DerivSessionManager.bootstrap",
            return_value=bootstrap,
        ), patch(
            "scripts.verify_deriv_session.DerivAdapter.__init__",
            return_value=None,
        ) as adapter_init, patch(
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
        self.assertEqual(
            adapter_init.call_args.kwargs.get("auth_token"),
            "",
            "An OTP URL already authenticates the Options WebSocket; never send the PAT again over that socket.",
        )
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
                "DERIV_APP_ID": "APP-ID-TEST",
                "DERIV_EXPECTED_LOGINID": "CRDEMO",
                "DERIV_ENVIRONMENT": "demo",
                "DERIV_EXPECTED_CURRENCY": "USD",
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


    def test_safe_error_reason_preserves_allowlisted_internal_code(self):
        self.assertEqual(
            safe_deriv_error_reason(ValueError("ACCOUNT_ENVIRONMENT_MISMATCH")),
            "ACCOUNT_ENVIRONMENT_MISMATCH",
        )

    def test_safe_error_reason_preserves_allowlisted_otp_code(self):
        self.assertEqual(
            safe_deriv_error_reason(RuntimeError("OTP_REQUEST_FAILED")),
            "OTP_REQUEST_FAILED",
        )

    def test_safe_error_reason_masks_unrecognized_value_error_message(self):
        private_text = "SYNTHETIC_SECRET_VALUE_DO_NOT_LOG"
        result = safe_deriv_error_reason(ValueError(private_text))
        self.assertEqual(result, "UNCLASSIFIED_VALUEERROR")
        self.assertNotIn(private_text, result)

    def test_safe_error_reason_masks_multiple_exception_arguments(self):
        result = safe_deriv_error_reason(
            ValueError("ACCOUNT_ENVIRONMENT_MISMATCH", "SYNTHETIC_ACCOUNT_IDENTIFIER")
        )
        self.assertEqual(result, "UNCLASSIFIED_VALUEERROR")
        self.assertNotIn("SYNTHETIC_ACCOUNT_IDENTIFIER", result)

    async def test_failed_session_output_never_prints_unrecognized_exception_details(self):
        import io
        from contextlib import redirect_stdout

        private_text = "SYNTHETIC_SECRET_VALUE_DO_NOT_LOG"
        output = io.StringIO()
        with patch.dict(
            os.environ,
            {
                "DERIV_AUTH_TOKEN": "SYNTHETIC_TOKEN_VALUE",
                "DERIV_APP_ID": "SYNTHETIC_APP_ID",
                "DERIV_EXPECTED_LOGINID": "SYNTHETIC_ACCOUNT_ID",
                "DERIV_ENVIRONMENT": "real",
                "DERIV_EXPECTED_CURRENCY": "USD",
            },
            clear=True,
        ), patch(
            "scripts.verify_deriv_session.DerivSessionManager.bootstrap",
            side_effect=ValueError(private_text),
        ), redirect_stdout(output):
            result = await run()

        rendered = output.getvalue()
        self.assertEqual(result, 1)
        self.assertIn("DERIV_AUTH_SESSION=FAILED", rendered)
        self.assertIn(
            "DERIV_AUTH_SESSION_REASON=UNCLASSIFIED_VALUEERROR",
            rendered,
        )
        self.assertNotIn(private_text, rendered)
        self.assertNotIn("SYNTHETIC_TOKEN_VALUE", rendered)
        self.assertNotIn("SYNTHETIC_ACCOUNT_ID", rendered)


if __name__ == "__main__":
    unittest.main()
