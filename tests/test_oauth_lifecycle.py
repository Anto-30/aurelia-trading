from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet

from runtime.core.account_binding_store import EncryptedAccountBindingStore
from runtime.core.persistent import BrokerUUIDToLoginBinding
from runtime.oauth.allowlist import OAuthAllowlist
from runtime.oauth.client import DerivOAuthError, DerivOAuthExtension


CALLBACK = "https://aurelia.example.com/oauth/callback"
APP_ID = "test-app-123"
PRINCIPAL = "0e8b5f21-34d7-4e8c-9c1b-6cc2fe4c7c10"
SESSION = "S" * 64


class FakeAdapter:
    def __init__(self):
        self.transport = object()
        self.attached = None

    def attach_oauth_extension(self, extension):
        if self.attached is not None:
            raise ValueError("duplicate extension")
        self.attached = extension


class OAuthLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = BrokerUUIDToLoginBinding(
            EncryptedAccountBindingStore(
                self.root / "bindings.enc", Fernet.generate_key()
            )
        )
        config = self.root / "oauth_allowlist.yaml"
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
        self.adapter = FakeAdapter()

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_extension(self, token_exchange=None):
        return DerivOAuthExtension(
            existing_adapter=self.adapter,
            binding_store=self.store,
            allowlist=self.allowlist,
            principal_uuid=PRINCIPAL,
            token_exchange=token_exchange,
        )

    def start_flow(self, extension):
        url = extension.initiate_authorization(
            redirect_uri=CALLBACK, session_binding=SESSION
        )
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        self.assertEqual(parts.scheme, "https")
        self.assertEqual(parts.netloc, "auth.deriv.com")
        self.assertEqual(query["scope"], ["trade"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["response_type"], ["code"])
        self.assertNotIn("code_verifier", query)
        return query

    async def test_pkce_callback_persists_encrypted_credential_and_returns_receipt_only(self):
        captured = {}

        def exchange(form):
            captured.update(form)
            return {
                "access_token": "fixtureValueDemo123",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "trade",
            }

        extension = self.make_extension(exchange)
        query = self.start_flow(extension)
        receipt = await extension.complete_authorization(
            auth_code="fixtureAuthCode123",
            state=query["state"][0],
            redirect_uri=CALLBACK,
            session_binding=SESSION,
        )
        self.assertEqual(receipt.scopes, ("trade",))
        self.assertEqual(receipt.scope_source, "provider_response")
        self.assertEqual(captured["grant_type"], "authorization_code")
        self.assertTrue(captured["code_verifier"])
        self.assertNotIn("client_secret", captured)
        self.assertEqual(extension.get_access_token_for_server(), "fixtureValueDemo123")

        ciphertext = self.store.existing_store.oauth_path.read_bytes()
        self.assertNotIn(b"fixtureValueDemo123", ciphertext)
        self.assertNotIn(b"fixtureAuthCode123", ciphertext)

    async def test_callback_is_session_bound_and_state_is_one_use(self):
        extension = self.make_extension(lambda _: {
            "access_token": "fixtureValueDemo123",
            "token_type": "Bearer",
            "expires_in": 3600,
        })
        query = self.start_flow(extension)
        state = query["state"][0]

        with self.assertRaisesRegex(DerivOAuthError, "STATE_INVALID"):
            await extension.complete_authorization(
                auth_code="fixtureAuthCode123", state=state,
                redirect_uri=CALLBACK, session_binding="T" * 64,
            )

        await extension.complete_authorization(
            auth_code="fixtureAuthCode123", state=state,
            redirect_uri=CALLBACK, session_binding=SESSION,
        )
        with self.assertRaisesRegex(DerivOAuthError, "REPLAYED"):
            await extension.complete_authorization(
                auth_code="fixtureAuthCode123", state=state,
                redirect_uri=CALLBACK, session_binding=SESSION,
            )

    async def test_provider_extra_scope_is_rejected(self):
        extension = self.make_extension(lambda _: {
            "access_token": "fixtureValueDemo123",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "trade account_manage",
        })
        query = self.start_flow(extension)
        with self.assertRaisesRegex(DerivOAuthError, "SCOPE_NOT_ALLOWLISTED"):
            await extension.complete_authorization(
                auth_code="fixtureAuthCode123", state=query["state"][0],
                redirect_uri=CALLBACK, session_binding=SESSION,
            )
        self.assertIsNone(self.store.get_oauth_access_token(
            principal_uuid=PRINCIPAL, app_id=APP_ID
        ))

    async def test_unexpected_refresh_field_is_rejected(self):
        extension = self.make_extension(lambda _: {
            "access_token": "fixtureValueDemo123",
            "refresh_token": "fixtureRefreshFieldValue",
            "token_type": "Bearer",
            "expires_in": 3600,
        })
        query = self.start_flow(extension)
        with self.assertRaisesRegex(DerivOAuthError, "REFRESH_TOKEN_UNSUPPORTED"):
            await extension.complete_authorization(
                auth_code="fixtureAuthCode123", state=query["state"][0],
                redirect_uri=CALLBACK, session_binding=SESSION,
            )
        self.assertIsNone(self.store.get_oauth_access_token(
            principal_uuid=PRINCIPAL, app_id=APP_ID
        ))

    def test_expired_credential_is_deleted_and_requires_new_authorization(self):
        now = datetime.now(timezone.utc)
        self.store.store_oauth_access_token(
            principal_uuid=PRINCIPAL,
            app_id=APP_ID,
            access_token="fixtureExpiredValue",
            token_type="Bearer",
            scopes=["trade"],
            scope_source="provider_response",
            issued_at_utc=(now - timedelta(hours=2)).isoformat(),
            expires_at_utc=(now - timedelta(hours=1)).isoformat(),
        )
        self.assertIsNone(self.store.get_oauth_access_token(
            principal_uuid=PRINCIPAL, app_id=APP_ID
        ))


if __name__ == "__main__":
    unittest.main()
