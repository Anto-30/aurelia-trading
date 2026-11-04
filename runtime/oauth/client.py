from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from runtime.oauth.allowlist import OAuthAllowlist
from runtime.oauth.pkce import PKCEChallenge




class _RejectOAuthRedirectHandler(HTTPRedirectHandler):
    """Never forward an OAuth code or PKCE verifier to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DerivOAuthError(RuntimeError):
    """Sanitized OAuth flow failure; provider response bodies are never propagated."""


@dataclass(frozen=True)
class OAuthAuthorizationResult:
    """Non-secret authorization receipt safe for an authenticated server response."""

    principal_uuid: str
    app_id: str
    scopes: tuple[str, ...]
    scope_source: str
    token_type: str
    issued_at_utc: str
    expires_at_utc: str


class DerivOAuthExtension:
    """Server-side Authorization Code + PKCE service for one existing adapter.

    The adapter WebSocket transport is not replaced. HTTPS code exchange uses
    the standard-library HTTP client. The access token and PKCE verifier are
    persisted only through the existing Fernet-backed binding store.
    session_binding must be a high-entropy server-authenticated secret, such
    as a Secure, HttpOnly, SameSite=Lax cookie or equivalent server session.
    It must not be supplied or chosen by an unauthenticated browser.
    """

    def __init__(
        self,
        *,
        existing_adapter: Any,
        binding_store: Any,
        allowlist: OAuthAllowlist,
        principal_uuid: str,
        timeout_seconds: float = 10.0,
        token_exchange: Callable[[dict[str, str]], Mapping[str, Any]] | None = None,
    ) -> None:
        if existing_adapter is None:
            raise ValueError("EXISTING_DERIV_ADAPTER_REQUIRED")
        required = (
            "create_pending_oauth_authorization",
            "consume_pending_oauth_authorization",
            "store_oauth_access_token",
            "get_oauth_access_token",
            "delete_oauth_access_token",
        )
        if any(not callable(getattr(binding_store, name, None)) for name in required):
            raise TypeError("ENCRYPTED_OAUTH_BINDING_STORE_INTERFACE_REQUIRED")
        if not isinstance(allowlist, OAuthAllowlist):
            raise TypeError("DERIV_OAUTH_ALLOWLIST_REQUIRED")
        if not isinstance(principal_uuid, str) or not principal_uuid.strip():
            raise ValueError("AURELIA_OAUTH_PRINCIPAL_UUID_REQUIRED")
        try:
            self.principal_uuid = str(UUID(principal_uuid))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("AURELIA_OAUTH_PRINCIPAL_UUID_INVALID") from exc
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not 1 <= timeout_seconds <= 30
        ):
            raise ValueError("DERIV_OAUTH_HTTP_TIMEOUT_INVALID")

        self.adapter = existing_adapter
        self.binding_store = binding_store
        self.allowlist = allowlist
        self.timeout_seconds = float(timeout_seconds)
        self._token_exchange = token_exchange or self._exchange_authorization_code
        attach = getattr(existing_adapter, "attach_oauth_extension", None)
        if not callable(attach):
            raise TypeError("DERIV_ADAPTER_OAUTH_EXTENSION_HOOK_REQUIRED")
        attach(self)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _validate_session_binding(session_binding: str) -> None:
        if (
            not isinstance(session_binding, str)
            or len(session_binding) < 32
            or len(session_binding) > 512
        ):
            raise DerivOAuthError("OAUTH_SERVER_SESSION_BINDING_INVALID")

    def initiate_authorization(self, *, redirect_uri: str, session_binding: str) -> str:
        self._validate_session_binding(session_binding)
        if not self.allowlist.validate_redirect_uri(redirect_uri):
            raise DerivOAuthError("OAUTH_REDIRECT_URI_NOT_ALLOWLISTED")

        challenge = PKCEChallenge.generate()
        now = self._now()
        expires = now + timedelta(
            seconds=self.allowlist.pending_authorization_ttl_seconds
        )
        try:
            self.binding_store.create_pending_oauth_authorization(
                state=challenge.state,
                code_verifier=challenge.code_verifier,
                code_challenge=challenge.code_challenge,
                code_challenge_method=challenge.code_challenge_method,
                redirect_uri=redirect_uri,
                session_binding=session_binding,
                app_id=self.allowlist.app_id,
                principal_uuid=self.principal_uuid,
                requested_scopes=list(self.allowlist.permitted_scopes),
                created_at_utc=now.isoformat(),
                expires_at_utc=expires.isoformat(),
            )
        except (ValueError, RuntimeError, TypeError):
            raise DerivOAuthError(
                "OAUTH_PENDING_AUTHORIZATION_PERSISTENCE_FAILED"
            ) from None

        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.allowlist.app_id,
                "redirect_uri": redirect_uri,
                "scope": " ".join(self.allowlist.permitted_scopes),
                "code_challenge": challenge.code_challenge,
                "code_challenge_method": "S256",
                "state": challenge.state,
            }
        )
        return self.allowlist.authorize_endpoint + "?" + query

    def _exchange_authorization_code(self, form: dict[str, str]) -> Mapping[str, Any]:
        request = Request(
            self.allowlist.token_endpoint,
            data=urlencode(form).encode("ascii"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            opener = build_opener(_RejectOAuthRedirectHandler())
            with opener.open(request, timeout=self.timeout_seconds) as response:
                if getattr(response, "status", 200) != 200:
                    raise DerivOAuthError("DERIV_OAUTH_TOKEN_EXCHANGE_REJECTED")
                raw = response.read(65537)
        except (HTTPError, URLError, TimeoutError, OSError):
            raise DerivOAuthError("DERIV_OAUTH_TOKEN_EXCHANGE_UNAVAILABLE") from None
        if len(raw) > 65536:
            raise DerivOAuthError("DERIV_OAUTH_TOKEN_RESPONSE_TOO_LARGE")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise DerivOAuthError("DERIV_OAUTH_TOKEN_RESPONSE_INVALID") from None
        if not isinstance(value, dict):
            raise DerivOAuthError("DERIV_OAUTH_TOKEN_RESPONSE_INVALID")
        return value

    async def complete_authorization(
        self,
        *,
        auth_code: str,
        state: str,
        redirect_uri: str,
        session_binding: str,
    ) -> OAuthAuthorizationResult:
        self._validate_session_binding(session_binding)
        if (
            not isinstance(auth_code, str)
            or not auth_code.strip()
            or len(auth_code) > 4096
            or any(char.isspace() for char in auth_code)
        ):
            raise DerivOAuthError("OAUTH_AUTHORIZATION_CODE_INVALID")
        if not self.allowlist.validate_redirect_uri(redirect_uri):
            raise DerivOAuthError("OAUTH_REDIRECT_URI_NOT_ALLOWLISTED")

        # Consume before network exchange. Every failure then requires fresh consent.
        try:
            pending = self.binding_store.consume_pending_oauth_authorization(
                state=state,
                session_binding=session_binding,
                consumed_at_utc=self._now().isoformat(),
            )
        except (ValueError, RuntimeError, TypeError):
            raise DerivOAuthError("OAUTH_STATE_INVALID_EXPIRED_OR_REPLAYED") from None

        if (
            pending.get("principal_uuid") != self.principal_uuid
            or pending.get("app_id") != self.allowlist.app_id
            or pending.get("redirect_uri") != redirect_uri
            or pending.get("requested_scopes") != list(self.allowlist.permitted_scopes)
        ):
            raise DerivOAuthError("OAUTH_PENDING_AUTHORIZATION_BINDING_MISMATCH")

        challenge = PKCEChallenge(
            code_verifier=pending.get("code_verifier"),
            code_challenge=pending.get("code_challenge"),
            code_challenge_method=pending.get("code_challenge_method"),
            state=state,
        )
        if challenge.verify_challenge() is not True:
            raise DerivOAuthError("OAUTH_PKCE_CHALLENGE_VERIFICATION_FAILED")

        form = {
            "grant_type": "authorization_code",
            "client_id": self.allowlist.app_id,
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "code_verifier": challenge.code_verifier,
        }
        try:
            token_data = await asyncio.to_thread(self._token_exchange, form)
            if inspect.isawaitable(token_data):
                token_data = await token_data
        except DerivOAuthError:
            raise
        except Exception:
            raise DerivOAuthError("DERIV_OAUTH_TOKEN_EXCHANGE_FAILED") from None
        if not isinstance(token_data, Mapping):
            raise DerivOAuthError("DERIV_OAUTH_TOKEN_RESPONSE_INVALID")
        if "refresh_token" in token_data:
            raise DerivOAuthError("DERIV_REFRESH_TOKEN_UNSUPPORTED_BY_DERIV")

        access_token = token_data.get("access_token")
        token_type = token_data.get("token_type")
        expires_in = token_data.get("expires_in")
        if not isinstance(access_token, str) or not access_token.strip():
            raise DerivOAuthError("DERIV_OAUTH_ACCESS_TOKEN_MISSING")
        if not isinstance(token_type, str) or token_type.lower() != "bearer":
            raise DerivOAuthError("DERIV_OAUTH_TOKEN_TYPE_UNSUPPORTED")
        if (
            isinstance(expires_in, bool)
            or not isinstance(expires_in, int)
            or not 60 <= expires_in <= self.allowlist.max_access_token_ttl_seconds
        ):
            raise DerivOAuthError("DERIV_OAUTH_TOKEN_EXPIRY_INVALID")

        response_scope = token_data.get("scope")
        if response_scope is None:
            scopes = list(self.allowlist.permitted_scopes)
            scope_source = "authorization_request"
        elif isinstance(response_scope, str):
            scopes = response_scope.split()
            scope_source = "provider_response"
        elif isinstance(response_scope, list) and all(
            isinstance(item, str) for item in response_scope
        ):
            scopes = response_scope
            scope_source = "provider_response"
        else:
            raise DerivOAuthError("DERIV_OAUTH_SCOPE_RESPONSE_INVALID")
        if not self.allowlist.validate_scopes(scopes):
            raise DerivOAuthError("DERIV_OAUTH_SCOPE_NOT_ALLOWLISTED")

        issued = self._now()
        expires = issued + timedelta(seconds=expires_in)
        try:
            self.binding_store.store_oauth_access_token(
                principal_uuid=self.principal_uuid,
                app_id=self.allowlist.app_id,
                access_token=access_token,
                token_type="Bearer",
                scopes=scopes,
                scope_source=scope_source,
                issued_at_utc=issued.isoformat(),
                expires_at_utc=expires.isoformat(),
            )
        except (ValueError, RuntimeError, TypeError):
            raise DerivOAuthError("DERIV_OAUTH_CREDENTIAL_PERSISTENCE_FAILED") from None

        return OAuthAuthorizationResult(
            principal_uuid=self.principal_uuid,
            app_id=self.allowlist.app_id,
            scopes=tuple(scopes),
            scope_source=scope_source,
            token_type="Bearer",
            issued_at_utc=issued.isoformat(),
            expires_at_utc=expires.isoformat(),
        )

    def get_access_token_for_server(self) -> str:
        """Return the secret only to a server-side authenticated broker component."""
        row = self.binding_store.get_oauth_access_token(
            principal_uuid=self.principal_uuid,
            app_id=self.allowlist.app_id,
        )
        if row is None:
            raise DerivOAuthError("DERIV_OAUTH_REAUTHORIZATION_REQUIRED")
        token = row.get("access_token")
        if not isinstance(token, str) or not token:
            raise DerivOAuthError("DERIV_OAUTH_ACCESS_TOKEN_INVALID")
        return token

    def clear_access_token(self) -> bool:
        """Delete the local encrypted credential; this does not claim provider revocation."""
        return bool(
            self.binding_store.delete_oauth_access_token(
                principal_uuid=self.principal_uuid,
                app_id=self.allowlist.app_id,
            )
        )
