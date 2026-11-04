from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

import yaml


DERIV_AUTHORIZE_ENDPOINT = "https://auth.deriv.com/oauth2/auth"
DERIV_TOKEN_ENDPOINT = "https://auth.deriv.com/oauth2/token"
DERIV_ACCOUNT_LIST_ENDPOINT = "https://api.derivws.com/trading/v1/options/accounts"
DERIV_OPTIONS_SCOPE = "trade"


@dataclass(frozen=True)
class OAuthAllowlist:
    """Strict, version-controlled Deriv OAuth configuration.

    Deriv documents `trade`, `account_manage`, `application_read`, and
    `payment`. Options account listing and OTP both require `trade`; this
    application deliberately requests only that scope. No provider refresh
    token or token-revocation endpoint is assumed.
    """

    redirect_uris: tuple[str, ...]
    permitted_scopes: tuple[str, ...]
    authorize_endpoint: str
    token_endpoint: str
    app_id: str
    pending_authorization_ttl_seconds: int = 600
    max_access_token_ttl_seconds: int = 7_776_000

    @classmethod
    def load(
        cls,
        config_path: str = "config/oauth_allowlist.yaml",
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "OAuthAllowlist":
        path = Path(config_path)
        if not path.is_file():
            raise FileNotFoundError(f"OAUTH_ALLOWLIST_NOT_FOUND:{path}")
        env = os.environ if environ is None else environ
        try:
            config = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ValueError("OAUTH_ALLOWLIST_CONFIG_INVALID") from exc
        if not isinstance(config, dict):
            raise ValueError("OAUTH_ALLOWLIST_CONFIG_INVALID")

        application = config.get("oauth_application")
        token_scope = config.get("token_scope")
        endpoints = config.get("endpoints")
        policy = config.get("token_policy")
        if not all(isinstance(item, dict) for item in (application, token_scope, endpoints, policy)):
            raise ValueError("OAUTH_ALLOWLIST_SECTION_INVALID")
        if application.get("provider") != "deriv":
            raise ValueError("OAUTH_PROVIDER_MISMATCH")

        redirect_uris = application.get("redirect_uris")
        if not isinstance(redirect_uris, list):
            raise ValueError("OAUTH_REDIRECT_URI_ALLOWLIST_INVALID")
        if not redirect_uris:
            raise ValueError("REDIRECT_URI_ALLOWLIST_EMPTY")
        if len(redirect_uris) != len(set(redirect_uris)):
            raise ValueError("OAUTH_REDIRECT_URI_DUPLICATE")
        for uri in redirect_uris:
            if not isinstance(uri, str) or not uri.strip():
                raise ValueError("OAUTH_REDIRECT_URI_INVALID")
            parts = urlsplit(uri)
            if (
                parts.scheme != "https"
                or not parts.hostname
                or parts.username is not None
                or parts.password is not None
                or parts.query
                or parts.fragment
                or "*" in uri
            ):
                raise ValueError("OAUTH_REDIRECT_URI_MUST_BE_EXACT_HTTPS")

        permitted = token_scope.get("permitted")
        if not isinstance(permitted, list) or permitted != [DERIV_OPTIONS_SCOPE]:
            raise ValueError("DERIV_OAUTH_SCOPE_MUST_BE_TRADE_ONLY")

        authorize = endpoints.get("authorize")
        token = endpoints.get("token")
        if authorize != DERIV_AUTHORIZE_ENDPOINT or token != DERIV_TOKEN_ENDPOINT:
            raise ValueError("OAUTH_ENDPOINT_NOT_TRUSTED")

        app_id_env_var = application.get("app_id_env_var")
        if not isinstance(app_id_env_var, str) or not app_id_env_var.strip():
            raise ValueError("DERIV_OAUTH_APP_ID_ENV_NAME_REQUIRED")
        app_id = str(env.get(app_id_env_var, "")).strip()
        if not app_id:
            raise ValueError("DERIV_OAUTH_APP_ID_MISSING")

        pending_ttl = policy.get("pending_authorization_ttl_seconds")
        max_ttl = policy.get("max_access_token_ttl_seconds")
        if (
            isinstance(pending_ttl, bool)
            or not isinstance(pending_ttl, int)
            or not 60 <= pending_ttl <= 1800
        ):
            raise ValueError("OAUTH_PENDING_TTL_INVALID")
        if (
            isinstance(max_ttl, bool)
            or not isinstance(max_ttl, int)
            or not 60 <= max_ttl <= 7_776_000
        ):
            raise ValueError("OAUTH_MAX_ACCESS_TOKEN_TTL_INVALID")

        return cls(
            redirect_uris=tuple(redirect_uris),
            permitted_scopes=tuple(permitted),
            authorize_endpoint=authorize,
            token_endpoint=token,
            app_id=app_id,
            pending_authorization_ttl_seconds=pending_ttl,
            max_access_token_ttl_seconds=max_ttl,
        )

    def validate_redirect_uri(self, uri: str) -> bool:
        return isinstance(uri, str) and uri in self.redirect_uris

    def validate_scopes(self, requested_scopes: list[str] | tuple[str, ...]) -> bool:
        if not isinstance(requested_scopes, (list, tuple)):
            return False
        if any(not isinstance(scope, str) or not scope for scope in requested_scopes):
            return False
        return (
            len(requested_scopes) == 1
            and tuple(requested_scopes) == self.permitted_scopes
            and self.permitted_scopes == (DERIV_OPTIONS_SCOPE,)
        )
