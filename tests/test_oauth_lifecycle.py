from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet

from runtime.core.account_binding_store import EncryptedAccountBindingStore
from runtime.core.persistent import BrokerUUIDToLoginBinding
from runtime.oauth.allowlist import OAuthAllowlist
from runtime.oauth.client import DerivOAuthError, DerivOAuthExtension


CALLBACK = "https://aurelia.example.com/oauth/callback"
APP_ID = "test-app-123"
PRINCIPAL = "0e8b5f21-34d7-4e8c-9c1b-6cc2fe4c7c10"
SESSION = "S" * 64


def make_store(tmp_path):
    return BrokerUUIDToLoginBinding(
        EncryptedAccountBindingStore(tmp_path / "bindings.enc", Fernet.generate_key())
    )


def make_allowlist(tmp_path):
    config = tmp_path / "oauth_allowlist.yaml"
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
    return OAuthAllowlist.load(str(config), environ={"DERIV_OAUTH_APP_ID": APP_ID})


class FakeAdapter:
    def __init__(self):
        self.transport = object()
        self.attached = None

    def attach_oauth_extension(self, extension):
        if self.attached is not None:
            raise ValueError("duplicate extension")
        self.attached = extension


@pytest.mark.asyncio
async def test_pkce_callback_persists_encrypted_credential_and_returns_receipt_only(tmp_path):
    captured = {}

    def exchange(form):
        captured.update(form)
        return {
            "access_token": "fixtureValueDemo123",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "trade",
        }

    store = make_store(tmp_path)
    adapter = FakeAdapter()
    extension = DerivOAuthExtension(
        existing_adapter=adapter,
        binding_store=store,
        allowlist=make_allowlist(tmp_path),
        principal_uuid=PRINCIPAL,
        token_exchange=exchange,
    )
    authorization_url = adapter.attached.initiate_authorization(
        redirect_uri=CALLBACK, session_binding=SESSION
    )
    parts = urlsplit(authorization_url)
    query = parse_qs(parts.query)
    assert parts.netloc == "auth.deriv.com"
    assert query["scope"] == ["trade"]
    assert query["code_challenge_method"] == ["S256"]
    assert "code_verifier" not in query

    receipt = await adapter.attached.complete_oauth_authorization(
        auth_code="fixtureAuthCode123",
        state=query["state"][0],
        redirect_uri=CALLBACK,
        session_binding=SESSION,
    )
    assert receipt.scopes == ("trade",)
    assert receipt.scope_source == "provider_response"
    assert captured["grant_type"] == "authorization_code"
    assert captured["code_verifier"]
    assert "client_secret" not in captured
    assert extension.get_access_token_for_server() == "fixtureValueDemo123"

    ciphertext = store.existing_store.oauth_path.read_bytes()
    assert b"fixtureValueDemo123" not in ciphertext
    assert b"fixtureAuthCode123" not in ciphertext


@pytest.mark.asyncio
async def test_callback_is_session_bound_and_state_is_one_use(tmp_path):
    extension = DerivOAuthExtension(
        existing_adapter=FakeAdapter(),
        binding_store=make_store(tmp_path),
        allowlist=make_allowlist(tmp_path),
        principal_uuid=PRINCIPAL,
        token_exchange=lambda _: {
            "access_token": "fixtureValueDemo123",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )
    query = parse_qs(urlsplit(extension.initiate_authorization(
        redirect_uri=CALLBACK, session_binding=SESSION
    )).query)
    state = query["state"][0]

    with pytest.raises(DerivOAuthError, match="STATE_INVALID"):
        await extension.complete_authorization(
            auth_code="fixtureAuthCode123", state=state,
            redirect_uri=CALLBACK, session_binding="T" * 64,
        )

    await extension.complete_authorization(
        auth_code="fixtureAuthCode123", state=state,
        redirect_uri=CALLBACK, session_binding=SESSION,
    )
    with pytest.raises(DerivOAuthError, match="REPLAYED"):
        await extension.complete_authorization(
            auth_code="fixtureAuthCode123", state=state,
            redirect_uri=CALLBACK, session_binding=SESSION,
        )


@pytest.mark.asyncio
async def test_provider_extra_scope_is_rejected(tmp_path):
    store = make_store(tmp_path)
    extension = DerivOAuthExtension(
        existing_adapter=FakeAdapter(),
        binding_store=store,
        allowlist=make_allowlist(tmp_path),
        principal_uuid=PRINCIPAL,
        token_exchange=lambda _: {
            "access_token": "fixtureValueDemo123",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "trade account_manage",
        },
    )
    query = parse_qs(urlsplit(extension.initiate_authorization(
        redirect_uri=CALLBACK, session_binding=SESSION
    )).query)
    with pytest.raises(DerivOAuthError, match="SCOPE_NOT_ALLOWLISTED"):
        await extension.complete_authorization(
            auth_code="fixtureAuthCode123", state=query["state"][0],
            redirect_uri=CALLBACK, session_binding=SESSION,
        )
    assert store.get_oauth_access_token(
        principal_uuid=PRINCIPAL, app_id=APP_ID
    ) is None


@pytest.mark.asyncio
async def test_unexpected_refresh_field_is_rejected(tmp_path):
    store = make_store(tmp_path)
    extension = DerivOAuthExtension(
        existing_adapter=FakeAdapter(),
        binding_store=store,
        allowlist=make_allowlist(tmp_path),
        principal_uuid=PRINCIPAL,
        token_exchange=lambda _: {
            "access_token": "fixtureValueDemo123",
            "refresh_token": "fixtureRefreshFieldValue",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )
    query = parse_qs(urlsplit(extension.initiate_authorization(
        redirect_uri=CALLBACK, session_binding=SESSION
    )).query)
    with pytest.raises(DerivOAuthError, match="REFRESH_TOKEN_UNSUPPORTED"):
        await extension.complete_authorization(
            auth_code="fixtureAuthCode123", state=query["state"][0],
            redirect_uri=CALLBACK, session_binding=SESSION,
        )
    assert store.get_oauth_access_token(
        principal_uuid=PRINCIPAL, app_id=APP_ID
    ) is None


def test_expired_credential_is_deleted_and_requires_new_authorization(tmp_path):
    store = make_store(tmp_path)
    now = datetime.now(timezone.utc)
    store.store_oauth_access_token(
        principal_uuid=PRINCIPAL,
        app_id=APP_ID,
        access_token="fixtureExpiredValue",
        token_type="Bearer",
        scopes=["trade"],
        scope_source="provider_response",
        issued_at_utc=(now - timedelta(hours=2)).isoformat(),
        expires_at_utc=(now - timedelta(hours=1)).isoformat(),
    )
    assert store.get_oauth_access_token(
        principal_uuid=PRINCIPAL, app_id=APP_ID
    ) is None
