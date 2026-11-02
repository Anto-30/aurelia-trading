from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from runtime.security.deriv_auth_gate import (
    AuthModeMismatchError,
    DerivAuthenticationGate,
    SecurityError,
)

OTP_ENDPOINT = "https://api.derivws.com/trading/v1/options/accounts/{account_id}/otp"
MODERN_OPTIONS_WS_HOST = "api.derivws.com"
MODERN_OPTIONS_WS_PREFIX = "/trading/v1/options/ws/"


class DerivSessionError(ValueError):
    """Deriv session validation error."""


@dataclass(frozen=True)
class AuthenticatedWebSocketUrl:
    account_id: str
    url: str
    source: str = "deriv:options:otp"

    def safe_url(self) -> str:
        return redact_ws_url(self.url)


def redact_ws_url(url: str) -> str:
    """Remove OTP parameter from WebSocket URL for safe logging."""
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    query.pop("otp", None)
    safe_query = "&".join(
        f"{key}={value[-1]}" for key, value in query.items() if value
    )
    return f"{parts.scheme}://{parts.netloc}{parts.path}" + (
        f"?{safe_query}" if safe_query else ""
    )


def derive_ws_environment(url: str) -> str:
    """Extract and validate the environment from a Deriv authenticated URL."""
    if not isinstance(url, str) or not url:
        raise DerivSessionError("DERIV_WS_URL_MISSING")
    validate_modern_options_ws_url(url)
    path = urlsplit(url).path.lower().rstrip("/")
    return path.rsplit("/", 1)[-1]


def validate_modern_options_ws_url(
    url: str,
    *,
    expected_environment: str | None = None,
) -> bool:
    """Require the current Deriv Options WebSocket host and path."""
    if not isinstance(url, str) or not url:
        raise DerivSessionError("DERIV_WS_URL_MISSING")
    parts = urlsplit(url)
    if parts.scheme != "wss" or parts.hostname != MODERN_OPTIONS_WS_HOST:
        raise DerivSessionError("LEGACY_OR_UNSUPPORTED_DERIV_WS_ENDPOINT")
    path = parts.path.rstrip("/")
    prefix = MODERN_OPTIONS_WS_PREFIX.rstrip("/")
    if not path.startswith(prefix + "/"):
        raise DerivSessionError("DERIV_OPTIONS_WS_PATH_INVALID")
    environment = path.rsplit("/", 1)[-1].lower()
    if environment not in {"real", "demo"}:
        raise DerivSessionError("UNKNOWN_DERIV_WS_ENVIRONMENT")
    if expected_environment and environment != expected_environment.lower():
        raise DerivSessionError("AUTHENTICATED_URL_ENVIRONMENT_MISMATCH")
    return True


def get_authenticated_ws_url(
    account_id: str,
    *,
    bearer_token: str | None = None,
    app_id: str | None = None,
    timeout_seconds: float = 10.0,
) -> AuthenticatedWebSocketUrl:
    """Fail closed until Deriv offers read-only permissions for account OTP.

    The parameters remain for API compatibility only. They are never read,
    logged, forwarded, or used as a fallback credential.
    """
    if not account_id:
        raise DerivSessionError("ACCOUNT_ID_REQUIRED")
    try:
        DerivAuthenticationGate(plane="account").get_client()
    except (AuthModeMismatchError, SecurityError) as exc:
        raise DerivSessionError(str(exc)) from exc
    raise DerivSessionError("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")
