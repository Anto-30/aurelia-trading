from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from runtime.oauth.allowlist import OAuthAllowlist
from runtime.oauth.pkce import PKCEChallenge
from runtime.core.models import DerivAccountIdentifier




class _RejectOAuthRedirectHandler(HTTPRedirectHandler):
    """Never forward an OAuth code or PKCE verifier to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DerivOAuthError(RuntimeError):
    """Sanitized OAuth flow failure; provider response bodies are never propagated."""


@dataclass(frozen=True)
class DerivDemoAccountSession:
    """Account snapshot plus a one-use OTP URL; repr deliberately hides OTP."""

    account: DerivAccountIdentifier
    websocket_url: str = field(repr=False)


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
        provider_request: Callable[
            [str, str, dict[str, str], dict[str, Any] | None],
            Mapping[str, Any],
        ] | None = None,
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
        self._provider_request = provider_request or self._request_deriv_rest
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

    def _request_deriv_rest(
        self,
        method: str,
        endpoint: str,
        headers: dict[str, str],
        body: dict[str, Any] | None,
    ) -> Mapping[str, Any]:
        """Call only a fixed Deriv Options REST endpoint without redirects."""
        if method not in {"GET", "POST"}:
            raise DerivOAuthError("DERIV_REST_METHOD_NOT_ALLOWED")
        allowed = {
            "GET": "https://api.derivws.com/trading/v1/options/accounts",
        }
        if method == "GET" and endpoint != allowed["GET"]:
            raise DerivOAuthError("DERIV_REST_ENDPOINT_NOT_ALLOWED")
        if method == "POST" and not endpoint.startswith(
            "https://api.derivws.com/trading/v1/options/accounts/"
        ):
            raise DerivOAuthError("DERIV_REST_ENDPOINT_NOT_ALLOWED")
        if method == "POST" and not endpoint.endswith("/otp"):
            raise DerivOAuthError("DERIV_REST_ENDPOINT_NOT_ALLOWED")

        payload = None if body is None else json.dumps(
            body, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        request_headers = {
            "Accept": "application/json",
            **headers,
        }
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
        request = Request(
            endpoint,
            data=payload,
            headers=request_headers,
            method=method,
        )
        try:
            opener = build_opener(_RejectOAuthRedirectHandler())
            with opener.open(request, timeout=self.timeout_seconds) as response:
                if getattr(response, "status", 200) != 200:
                    raise DerivOAuthError("DERIV_REST_REQUEST_REJECTED")
                raw = response.read(65537)
        except HTTPError as exc:
            # Do not expose provider response text: it may echo sensitive request data.
            if exc.code in {401, 403}:
                raise DerivOAuthError("DERIV_OAUTH_PROVIDER_AUTHORIZATION_REJECTED") from None
            raise DerivOAuthError("DERIV_REST_REQUEST_REJECTED") from None
        except (URLError, TimeoutError, OSError):
            raise DerivOAuthError("DERIV_REST_REQUEST_UNAVAILABLE") from None
        if len(raw) > 65536:
            raise DerivOAuthError("DERIV_REST_RESPONSE_TOO_LARGE")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise DerivOAuthError("DERIV_REST_RESPONSE_INVALID") from None
        if not isinstance(decoded, dict):
            raise DerivOAuthError("DERIV_REST_RESPONSE_INVALID")
        if "errors" in decoded:
            raise DerivOAuthError("DERIV_REST_PROVIDER_ERROR")
        return decoded

    def _provider_headers(self) -> dict[str, str]:
        token = self.get_access_token_for_server()
        return {
            "Authorization": "Bearer " + token,
            # Deriv's REST reference mandates the app identifier for PAT
            # auth; including the registered app id is also safe with OAuth.
            "Deriv-App-ID": self.allowlist.app_id,
        }

    @staticmethod
    def _account_from_options_row(row: object) -> DerivAccountIdentifier:
        if not isinstance(row, dict):
            raise DerivOAuthError("OPTIONS_ACCOUNT_SCHEMA_INVALID")
        required = {
            "account_id", "account_type", "status", "group", "currency", "balance"
        }
        if not required.issubset(row):
            raise DerivOAuthError("OPTIONS_ACCOUNT_SCHEMA_INVALID")
        account_id = row.get("account_id")
        account_type = row.get("account_type")
        status = row.get("status")
        group = row.get("group")
        currency = row.get("currency")
        balance = row.get("balance")
        if (
            not isinstance(account_id, str)
            or not account_id
            or not account_id.isascii()
            or not account_id.isalnum()
            or account_id != account_id.upper()
            or account_type not in {"real", "demo"}
            or status not in {"active", "inactive"}
            or not isinstance(group, str)
            or not group.strip()
            or not isinstance(currency, str)
            or len(currency) != 3
            or not currency.isalpha()
            or currency != currency.upper()
            or isinstance(balance, bool)
            or not isinstance(balance, (int, float))
            or not isfinite(float(balance))
            or float(balance) < 0
        ):
            raise DerivOAuthError("OPTIONS_ACCOUNT_SCHEMA_INVALID")
        try:
            account = DerivAccountIdentifier(
                account_id=account_id,
                account_type=account_type,
                status=status,
                group=group,
                currency=currency,
                balance=float(balance),
            )
        except (TypeError, ValueError):
            raise DerivOAuthError("OPTIONS_ACCOUNT_SCHEMA_INVALID") from None
        if account.validate() is not True:
            raise DerivOAuthError("OPTIONS_ACCOUNT_SCHEMA_INVALID")
        return account

    def create_authenticated_demo_session(
        self,
        *,
        account_id: str,
        expected_currency: str,
    ) -> DerivDemoAccountSession:
        """Request a one-use authenticated demo WS URL for one exact Options account.

        This method only discovers the caller's accounts and obtains a demo
        OTP. It does not connect, submit, authorize or manage broker orders.
        Real accounts are explicitly rejected by this demo-only bootstrap.
        """
        if (
            not isinstance(account_id, str)
            or not account_id
            or not account_id.isascii()
            or not account_id.isalnum()
            or account_id != account_id.upper()
        ):
            raise DerivOAuthError("DERIV_OPTIONS_ACCOUNT_ID_REQUIRED")
        currency = str(expected_currency or "").strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise DerivOAuthError("EXPECTED_ACCOUNT_CURRENCY_REQUIRED")

        headers = self._provider_headers()
        try:
            response = self._provider_request(
                "GET",
                "https://api.derivws.com/trading/v1/options/accounts",
                headers,
                None,
            )
        except DerivOAuthError:
            raise
        except Exception:
            raise DerivOAuthError("DERIV_ACCOUNT_LIST_UNAVAILABLE") from None
        if not isinstance(response, Mapping):
            raise DerivOAuthError("OPTIONS_ACCOUNT_LIST_RESPONSE_INVALID")
        rows = response.get("data")
        if not isinstance(rows, list):
            raise DerivOAuthError("OPTIONS_ACCOUNT_LIST_RESPONSE_INVALID")

        parsed = [self._account_from_options_row(row) for row in rows]
        matches = [account for account in parsed if account.account_id == account_id]
        if not matches:
            raise DerivOAuthError("ACCOUNT_ID_NOT_FOUND")
        if len(matches) != 1:
            raise DerivOAuthError("ACCOUNT_ID_AMBIGUOUS")
        account = matches[0]
        if account.account_type != "demo":
            raise DerivOAuthError("DEMO_ACCOUNT_REQUIRED")
        if account.status != "active":
            raise DerivOAuthError("ACCOUNT_NOT_ACTIVE")
        if account.currency != currency:
            raise DerivOAuthError("ACCOUNT_CURRENCY_MISMATCH")

        from urllib.parse import quote
        endpoint = (
            "https://api.derivws.com/trading/v1/options/accounts/"
            + quote(account.account_id, safe="")
            + "/otp"
        )
        try:
            otp_response = self._provider_request("POST", endpoint, headers, None)
        except DerivOAuthError:
            raise
        except Exception:
            raise DerivOAuthError("DERIV_OTP_REQUEST_UNAVAILABLE") from None
        if not isinstance(otp_response, Mapping):
            raise DerivOAuthError("DERIV_OTP_RESPONSE_INVALID")
        otp_data = otp_response.get("data")
        if not isinstance(otp_data, Mapping):
            raise DerivOAuthError("DERIV_OTP_RESPONSE_INVALID")
        websocket_url = otp_data.get("url")
        if not isinstance(websocket_url, str) or not websocket_url:
            raise DerivOAuthError("DERIV_OTP_URL_MISSING")
        try:
            parts = urlsplit(websocket_url)
            query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            raise DerivOAuthError("DERIV_OTP_URL_INVALID") from None
        if (
            parts.scheme != "wss"
            or parts.hostname != "api.derivws.com"
            or parts.port is not None
            or parts.username is not None
            or parts.password is not None
            or parts.fragment
            or parts.path != "/trading/v1/options/ws/demo"
            or set(query) != {"otp"}
            or len(query.get("otp", [])) != 1
            or not query["otp"][0]
            or len(query["otp"][0]) > 512
            or any(ch.isspace() for ch in query["otp"][0])
        ):
            raise DerivOAuthError("DERIV_OTP_URL_UNTRUSTED_OR_NOT_DEMO")
        return DerivDemoAccountSession(
            account=account,
            websocket_url=websocket_url,
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
