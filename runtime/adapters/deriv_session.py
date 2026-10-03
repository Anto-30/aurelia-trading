from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

OTP_ENDPOINT = "https://api.derivws.com/trading/v1/options/accounts/{account_id}/otp"
MODERN_OPTIONS_WS_HOST = "api.derivws.com"
MODERN_OPTIONS_WS_PREFIX = "/trading/v1/options/ws/"


class DerivSessionError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthenticatedWebSocketUrl:
    account_id: str
    url: str
    source: str = "deriv:options:otp"

    def safe_url(self) -> str:
        return self.url.split("?otp=", 1)[0] if "?otp=" in self.url else self.url


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
    token = bearer_token if bearer_token is not None else os.getenv("DERIV_AUTH_TOKEN", "")
    application_id = app_id if app_id is not None else os.getenv("DERIV_APP_ID", "")
    if not account_id:
        raise DerivSessionError("ACCOUNT_ID_REQUIRED")
    if not token:
        raise DerivSessionError("DERIV_BEARER_TOKEN_MISSING")

    headers = {"Authorization": f"Bearer {token}"}
    if application_id:
        headers["Deriv-App-ID"] = application_id

    request = Request(
        OTP_ENDPOINT.format(account_id=account_id),
        method="POST",
        headers=headers,
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DerivSessionError("OTP_REQUEST_FAILED") from exc

    url = ((payload.get("data") or {}).get("url") if isinstance(payload, dict) else None)
    if not isinstance(url, str) or not url.startswith("wss://"):
        raise DerivSessionError("OTP_RESPONSE_MISSING_WS_URL")
    validate_modern_options_ws_url(url)
    return AuthenticatedWebSocketUrl(account_id=account_id, url=url)
