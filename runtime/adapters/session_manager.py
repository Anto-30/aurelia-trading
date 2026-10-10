from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from runtime.core.secrets import get_optional_secret

from runtime.adapters.deriv_session import (
    AuthenticatedWebSocketUrl,
    DerivSessionError,
    get_authenticated_ws_url,
    validate_modern_options_ws_url,
)

OTP_ENDPOINT = "https://api.derivws.com/trading/v1/options/accounts/{account_id}/otp"
MODERN_OPTIONS_WS_HOST = "api.derivws.com"
MODERN_OPTIONS_WS_PREFIX = "/trading/v1/options/ws/"
ACCOUNTS_ENDPOINT = "https://api.derivws.com/trading/v1/options/accounts"


class DerivSessionManagerError(RuntimeError):
    pass


@dataclass(frozen=True)
class DerivAccountBinding:
    loginid: str
    account_type: str
    currency: str
    environment: str


@dataclass(frozen=True)
class DerivSessionBootstrap:
    binding: DerivAccountBinding
    websocket: AuthenticatedWebSocketUrl

    @property
    def safe_websocket_url(self) -> str:
        return redact_ws_url(self.websocket.url)


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
    """Extract and validate the Deriv environment from an authenticated WS URL.
    
    Args:
        url: WebSocket URL from OTP response
    
    Returns:
        Environment name ('real' or 'demo')
    
    Raises:
        DerivSessionError: If URL is invalid or environment is unknown
    """
    if not isinstance(url, str) or not url:
        raise DerivSessionError("DERIV_WS_URL_MISSING")
    validate_modern_options_ws_url(url)
    path = urlsplit(url).path.lower().rstrip("/")
    return path.rsplit("/", 1)[-1]


class DerivSessionManager:
    """Authentication/session bootstrap only; no capital authorization or order submission."""

    def __init__(
        self,
        *,
        expected_loginid: str | None = None,
        expected_environment: str = "real",
        expected_currency: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.expected_loginid = (
            expected_loginid
            if expected_loginid is not None
            else os.getenv("DERIV_EXPECTED_LOGINID", "")
        )
        self.expected_environment = expected_environment.lower()
        configured_currency = expected_currency if expected_currency is not None else os.getenv("DERIV_EXPECTED_CURRENCY", "")
        self.expected_currency = str(configured_currency).strip().upper()
        self.timeout_seconds = timeout_seconds

    def validate_binding(self, *, loginid: str, environment: str) -> bool:
        env = environment.lower()
        if env != self.expected_environment:
            raise ValueError("ACCOUNT_ENVIRONMENT_MISMATCH")
        if env == "real" and not self.expected_loginid:
            raise ValueError("REAL_ACCOUNT_BINDING_REQUIRED")
        if self.expected_loginid and loginid != self.expected_loginid:
            raise ValueError("ACCOUNT_LOGINID_MISMATCH")
        return True

    def _request_json(
        self,
        *,
        method: str,
        url: str,
        bearer_token: str,
        app_id: str | None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {bearer_token}"}
        if app_id:
            headers["Deriv-App-ID"] = app_id
        request = Request(url, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DerivSessionManagerError("DERIV_ACCOUNT_REQUEST_FAILED") from exc
        if not isinstance(payload, dict):
            raise DerivSessionManagerError("DERIV_ACCOUNT_RESPONSE_INVALID")
        return payload

    def list_accounts(
        self,
        *,
        bearer_token: str | None = None,
        app_id: str | None = None,
    ) -> list[dict[str, Any]]:
        token = bearer_token if bearer_token is not None else (get_optional_secret("DERIV_AUTH_TOKEN") or get_optional_secret("DERIV_PAT"))
        application_id = app_id if app_id is not None else get_optional_secret("DERIV_APP_ID")
        if not token:
            raise DerivSessionManagerError("DERIV_BEARER_TOKEN_MISSING")
        payload = self._request_json(
            method="GET",
            url=ACCOUNTS_ENDPOINT,
            bearer_token=token,
            app_id=application_id,
        )
        data = payload.get("data")
        if isinstance(data, list):
            return [dict(item) for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            return [dict(data)]
        raise DerivSessionManagerError("DERIV_ACCOUNT_LIST_MISSING")

    def select_account(self, accounts: list[dict[str, Any]]) -> DerivAccountBinding:
        if not self.expected_currency:
            raise DerivSessionManagerError("EXPECTED_CURRENCY_REQUIRED")
        candidates: list[DerivAccountBinding] = []
        for row in accounts:
            loginid = str(
                row.get("account_id")
                or row.get("loginid")
                or row.get("login_id")
                or ""
            )
            if not loginid:
                continue
            account_type = str(row.get("account_type") or "").lower()
            currency = str(row.get("currency") or "").strip().upper()
            environment = "real" if account_type == "real" else "demo"
            if row.get("environment"):
                environment = str(row["environment"]).lower()
            if environment == "virtual":
                environment = "demo"
            targeted_row = environment == self.expected_environment and (not self.expected_loginid or loginid == self.expected_loginid)
            if targeted_row and not currency:
                raise DerivSessionManagerError("ACCOUNT_CURRENCY_UNVERIFIED")
            if not currency:
                continue
            candidates.append(
                DerivAccountBinding(
                    loginid=loginid,
                    account_type=account_type or environment,
                    currency=currency,
                    environment=environment,
                )
            )

        matches = [
            item
            for item in candidates
            if item.environment == self.expected_environment
            and item.currency == self.expected_currency
            and (
                not self.expected_loginid
                or item.loginid == self.expected_loginid
            )
        ]
        if not matches:
            raise DerivSessionManagerError("NO_EXACT_DERIV_ACCOUNT_MATCH")
        if self.expected_environment == "real" and len(matches) != 1:
            raise DerivSessionManagerError(
                "MULTIPLE_REAL_ACCOUNTS_REQUIRE_EXPLICIT_BINDING"
            )
        selected = matches[0]
        self.validate_binding(
            loginid=selected.loginid,
            environment=selected.environment,
        )
        return selected

    def bootstrap(
        self,
        *,
        bearer_token: str | None = None,
        app_id: str | None = None,
    ) -> DerivSessionBootstrap:
        token = bearer_token if bearer_token is not None else os.getenv("DERIV_AUTH_TOKEN", "")
        application_id = app_id if app_id is not None else os.getenv("DERIV_APP_ID", "")
        accounts = self.list_accounts(
            bearer_token=token,
            app_id=application_id,
        )
        binding = self.select_account(accounts)
        try:
            websocket = get_authenticated_ws_url(
                binding.loginid,
                bearer_token=token,
                app_id=application_id,
                timeout_seconds=self.timeout_seconds,
            )
        except DerivSessionError as exc:
            raise DerivSessionManagerError(str(exc)) from exc

        actual_environment = derive_ws_environment(websocket.url)
        self.validate_binding(
            loginid=binding.loginid,
            environment=actual_environment,
        )
        if actual_environment != self.expected_environment:
            raise DerivSessionManagerError("OTP_WS_ENVIRONMENT_MISMATCH")
        return DerivSessionBootstrap(
            binding=binding,
            websocket=websocket,
        )
