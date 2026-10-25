from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from runtime.core.secrets import get_optional_secret

OTP_ENDPOINT = "https://api.derivws.com/trading/v1/options/accounts/{account_id}/otp"
MODERN_OPTIONS_WS_HOST = "api.derivws.com"
MODERN_OPTIONS_WS_PREFIX = "/trading/v1/options/ws/"
LIVE_LOCK_PATH = Path(__file__).resolve().parents[2] / "config" / "LIVE_LOCK.yaml"

# OTP acquisition is a bounded authentication retry, not a financial transaction.
# A failed attempt's URL is never reused. HTTP input/business-rule errors are not retried.
OTP_MAX_ATTEMPTS = 3
OTP_BACKOFF_BASE_SECONDS = 0.25
OTP_BACKOFF_CAP_SECONDS = 1.0
OTP_RETRYABLE_HTTP_STATUSES = frozenset({408, 500, 502, 503, 504})
_REQUIRED_LOCK_KEYS = (
    "live_trading_enabled",
    "FINAL_EXECUTION_AUTHORIZATION",
    "LIVE_EXECUTION",
    "capital_plane_mode",
)


class DerivSessionError(ValueError):
    """Deriv session validation error with secret-free stable codes."""

    pass


@dataclass(frozen=True)
class AuthenticatedWebSocketUrl:
    account_id: str
    url: str
    source: str = "deriv:options:otp"

    def safe_url(self) -> str:
        return self.url.split("?otp=", 1)[0] if "?otp=" in self.url else self.url


def redact_ws_url(url: str) -> str:
    """Remove OTP query value from a WebSocket URL before logging."""
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
    """Extract and validate the environment from an authenticated WS URL."""
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
    """Require the current Deriv Options WebSocket host and environment path."""
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


def _read_live_lock(path: Path | None = None) -> dict[str, str]:
    """Read the small top-level live-lock contract without a YAML dependency."""
    lock_path = path or LIVE_LOCK_PATH
    try:
        lines = lock_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise DerivSessionError("LIVE_LOCK_UNREADABLE") from None

    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key not in _REQUIRED_LOCK_KEYS:
            continue
        if key in values:
            raise DerivSessionError("LIVE_LOCK_DUPLICATE_KEY")
        values[key] = value.split("#", 1)[0].strip().strip('"').strip("'")

    if any(key not in values for key in _REQUIRED_LOCK_KEYS):
        raise DerivSessionError("LIVE_LOCK_STATE_UNKNOWN")
    return values


def _assert_verify_only_lock() -> None:
    """Deny authenticated REST OTP requests unless the canonical lock is fail-closed."""
    lock = _read_live_lock()
    if lock["capital_plane_mode"] != "VERIFY_ONLY":
        raise DerivSessionError("CAPITAL_PLANE_MODE_NOT_VERIFY_ONLY")
    if (
        lock["live_trading_enabled"] != "false"
        or lock["FINAL_EXECUTION_AUTHORIZATION"] != "false"
        or lock["LIVE_EXECUTION"] != "BLOCKED"
    ):
        raise DerivSessionError("LIVE_LOCK_NOT_FAIL_CLOSED")


def _otp_retry_delay(attempt_index: int) -> float:
    """Return bounded exponential delay before retry number attempt_index + 1."""
    return min(OTP_BACKOFF_BASE_SECONDS * (2**attempt_index), OTP_BACKOFF_CAP_SECONDS)


def _request_otp_payload(
    *,
    account_id: str,
    headers: dict[str, str],
    timeout_seconds: float,
) -> object:
    """Request OTP with bounded retries for transient transport/5xx failures only."""
    for attempt_index in range(OTP_MAX_ATTEMPTS):
        # A fresh Request object is made for each attempt; the response URL is never replayed.
        request = Request(
            OTP_ENDPOINT.format(account_id=account_id),
            method="POST",
            headers=headers,
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw_body = response.read()
        except HTTPError as exc:
            if (
                exc.code in OTP_RETRYABLE_HTTP_STATUSES
                and attempt_index + 1 < OTP_MAX_ATTEMPTS
            ):
                time.sleep(_otp_retry_delay(attempt_index))
                continue
            if exc.code in OTP_RETRYABLE_HTTP_STATUSES:
                raise DerivSessionError("OTP_REQUEST_FAILED_RETRY_EXHAUSTED") from None
            # Do not log response bodies or echo auth headers.
            raise DerivSessionError(f"OTP_REQUEST_REJECTED_HTTP_{exc.code}") from None
        except (URLError, TimeoutError, ConnectionError, OSError):
            if attempt_index + 1 < OTP_MAX_ATTEMPTS:
                time.sleep(_otp_retry_delay(attempt_index))
                continue
            raise DerivSessionError("OTP_REQUEST_FAILED_RETRY_EXHAUSTED") from None

        try:
            return json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise DerivSessionError("OTP_RESPONSE_INVALID_JSON") from None

    raise DerivSessionError("OTP_REQUEST_FAILED_RETRY_EXHAUSTED")


def get_authenticated_ws_url(
    account_id: str,
    *,
    bearer_token: str | None = None,
    app_id: str | None = None,
    timeout_seconds: float = 10.0,
) -> AuthenticatedWebSocketUrl:
    """Request a modern Options API WebSocket URL under the fail-closed live lock.

    The canonical config must explicitly remain VERIFY_ONLY with live execution and
    final authorization blocked. Retries are bounded, only for transient network/5xx
    failures, and never reuse a URL returned by a previous OTP response. This endpoint
    is not called by default in TEST_ONLY; tests must mock the transport.
    """
    _assert_verify_only_lock()

    token = (
        bearer_token
        if bearer_token is not None
        else get_optional_secret("DERIV_AUTH_TOKEN")
    )
    application_id = (
        app_id
        if app_id is not None
        else get_optional_secret("DERIV_APP_ID")
    )
    auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower()

    if not account_id:
        raise DerivSessionError("ACCOUNT_ID_REQUIRED")
    if not token:
        raise DerivSessionError("DERIV_BEARER_TOKEN_MISSING")
    if auth_mode not in {"pat", "oauth"}:
        raise DerivSessionError("DERIV_AUTH_MODE_INVALID")
    if auth_mode == "pat" and not application_id:
        raise DerivSessionError("DERIV_APP_ID_MISSING")

    headers = {"Authorization": f"Bearer {token}"}
    if auth_mode == "pat":
        headers["Deriv-App-ID"] = str(application_id)

    payload = _request_otp_payload(
        account_id=account_id,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    url = ((payload.get("data") or {}).get("url") if isinstance(payload, dict) else None)
    if not isinstance(url, str) or not url.startswith("wss://"):
        raise DerivSessionError("OTP_RESPONSE_MISSING_WS_URL")
    validate_modern_options_ws_url(url)
    return AuthenticatedWebSocketUrl(account_id=account_id, url=url)
