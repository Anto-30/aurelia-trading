from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet

from runtime.core.account_binding_store import EncryptedAccountBindingStore
from runtime.core.persistent import BrokerUUIDToLoginBinding
from runtime.oauth.allowlist import OAuthAllowlist
from runtime.oauth.client import DerivOAuthError, DerivOAuthExtension


APP_ID = "bootstrap-test-app"
PRINCIPAL = "0e8b5f21-34d7-4e8c-9c1b-6cc2fe4c7c10"
ACCOUNT_ID = "DOT90004580"


class FakeAdapter:
    def __init__(self):
        self.attached = None

    def attach_oauth_extension(self, extension):
        self.attached = extension


class DerivOAuthAccountBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.store = BrokerUUIDToLoginBinding(
            EncryptedAccountBindingStore(root / "bindings.enc", Fernet.generate_key())
        )
        config = root / "oauth_allowlist.yaml"
        config.write_text(
            """oauth_application:
  name: aurelia-trading-runtime
  provider: deriv
  app_id_env_var: DERIV_OAUTH_APP_ID
  redirect_uris:
    - "https://aurelia.example.com/oauth/callback"
token_scope:
  permitted:
    - "trade"
endpoints:
  authorize: "https://auth.deriv.com/oauth2/auth"
  token: "https://auth.deriv.com/oauth2/token"
token_policy:
  pending_authorization_ttl_seconds: 600
  max_access_token_ttl_seconds: 7776000
""",
            encoding="utf-8",
        )
        self.allowlist = OAuthAllowlist.load(
            str(config), environ={"DERIV_OAUTH_APP_ID": APP_ID}
        )
        now = datetime.now(timezone.utc)
        self.store.store_oauth_access_token(
            principal_uuid=PRINCIPAL,
            app_id=APP_ID,
            access_token="unit-test-abc123",
            token_type="Bearer",
            scopes=["trade"],
            scope_source="provider_response",
            issued_at_utc=now.isoformat(),
            expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        )
        self.adapter = FakeAdapter()
        self.requests = []

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_extension(self, provider_request=None):
        return DerivOAuthExtension(
            existing_adapter=self.adapter,
            binding_store=self.store,
            allowlist=self.allowlist,
            principal_uuid=PRINCIPAL,
            provider_request=provider_request,
        )

    @staticmethod
    def demo_account(account_id=ACCOUNT_ID, *, currency="USD", status="active", account_type="demo"):
        return {
            "account_id": account_id,
            "balance": 1000.0,
            "currency": currency,
            "group": "row",
            "status": status,
            "account_type": account_type,
        }

    def fake_provider(self, *, accounts=None, otp_url=None):
        rows = accounts if accounts is not None else [self.demo_account()]
        url = otp_url or (
            "wss://api.derivws.com/trading/v1/options/ws/demo?otp=single-use-demo-otp"
        )

        def request(method, endpoint, headers, body):
            self.requests.append((method, endpoint, dict(headers), body))
            self.assertEqual(headers.get("Authorization"), "Bearer unit-test-abc123")
            self.assertEqual(headers.get("Deriv-App-ID"), APP_ID)
            if method == "GET":
                self.assertEqual(
                    endpoint,
                    "https://api.derivws.com/trading/v1/options/accounts",
                )
                return {"data": rows, "meta": {}}
            if method == "POST":
                self.assertEqual(
                    endpoint,
                    "https://api.derivws.com/trading/v1/options/accounts/"
                    + ACCOUNT_ID + "/otp",
                )
                self.assertIsNone(body)
                return {"data": {"url": url}, "meta": {}}
            self.fail("Unexpected provider method")
        return request

    def test_exact_demo_account_is_selected_and_one_time_url_is_returned(self):
        extension = self.make_extension(self.fake_provider())
        session = extension.create_authenticated_demo_session(
            account_id=ACCOUNT_ID,
            expected_currency="USD",
        )

        self.assertEqual(session.account.account_id, ACCOUNT_ID)
        self.assertEqual(session.account.account_type, "demo")
        self.assertEqual(session.account.currency, "USD")
        self.assertEqual(session.account.balance, 1000.0)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[0][0], "GET")
        self.assertEqual(self.requests[1][0], "POST")
        self.assertNotIn("single-use-demo-otp", repr(session))

    def test_account_id_must_be_supplied_exactly_and_must_exist(self):
        extension = self.make_extension(self.fake_provider())
        with self.assertRaisesRegex(DerivOAuthError, "ACCOUNT_ID_NOT_FOUND"):
            extension.create_authenticated_demo_session(
                account_id="DOT99999999",
                expected_currency="USD",
            )
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0][0], "GET")

    def test_real_account_is_never_bootstrapped_by_demo_flow(self):
        extension = self.make_extension(
            self.fake_provider(accounts=[self.demo_account(account_type="real")])
        )
        with self.assertRaisesRegex(DerivOAuthError, "DEMO_ACCOUNT_REQUIRED"):
            extension.create_authenticated_demo_session(
                account_id=ACCOUNT_ID,
                expected_currency="USD",
            )
        self.assertEqual(len(self.requests), 1)

    def test_inactive_account_is_rejected_before_otp(self):
        extension = self.make_extension(
            self.fake_provider(accounts=[self.demo_account(status="inactive")])
        )
        with self.assertRaisesRegex(DerivOAuthError, "ACCOUNT_NOT_ACTIVE"):
            extension.create_authenticated_demo_session(
                account_id=ACCOUNT_ID,
                expected_currency="USD",
            )
        self.assertEqual(len(self.requests), 1)

    def test_currency_mismatch_is_rejected_before_otp(self):
        extension = self.make_extension(
            self.fake_provider(accounts=[self.demo_account(currency="EUR")])
        )
        with self.assertRaisesRegex(DerivOAuthError, "ACCOUNT_CURRENCY_MISMATCH"):
            extension.create_authenticated_demo_session(
                account_id=ACCOUNT_ID,
                expected_currency="USD",
            )
        self.assertEqual(len(self.requests), 1)

    def test_malformed_account_schema_fails_closed(self):
        extension = self.make_extension(
            self.fake_provider(accounts=[{"account_id": ACCOUNT_ID, "account_type": "demo"}])
        )
        with self.assertRaisesRegex(DerivOAuthError, "OPTIONS_ACCOUNT_SCHEMA_INVALID"):
            extension.create_authenticated_demo_session(
                account_id=ACCOUNT_ID,
                expected_currency="USD",
            )
        self.assertEqual(len(self.requests), 1)

    def test_untrusted_or_real_otp_url_is_rejected(self):
        for url in (
            "wss://attacker.example/ws/demo?otp=not-ours",
            "wss://api.derivws.com/trading/v1/options/ws/real?otp=not-demo",
            "wss://api.derivws.com/trading/v1/options/ws/demo",
            "wss://api.derivws.com/trading/v1/options/ws/demo?otp=one&otp=two",
        ):
            with self.subTest(url=url):
                self.requests.clear()
                extension = self.make_extension(self.fake_provider(otp_url=url))
                with self.assertRaises(DerivOAuthError):
                    extension.create_authenticated_demo_session(
                        account_id=ACCOUNT_ID,
                        expected_currency="USD",
                    )

    def test_missing_or_expired_oauth_credential_fails_before_rest(self):
        self.store.delete_oauth_access_token(
            principal_uuid=PRINCIPAL,
            app_id=APP_ID,
        )
        extension = self.make_extension(self.fake_provider())
        with self.assertRaisesRegex(DerivOAuthError, "REAUTHORIZATION_REQUIRED"):
            extension.create_authenticated_demo_session(
                account_id=ACCOUNT_ID,
                expected_currency="USD",
            )
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
