from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit
from typing import Any

from runtime.security.deriv_auth_gate import (
    AuthModeMismatchError,
    DerivAuthenticationGate,
    SecurityError,
)
from runtime.adapters.deriv_session import (
    AuthenticatedWebSocketUrl,
    DerivSessionError,
    derive_ws_environment,
    validate_modern_options_ws_url,
)


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
    return derive_ws_environment_from_adapter(url)


def derive_ws_environment_from_adapter(url: str) -> str:
    try:
        return derive_ws_environment(url)
    except DerivSessionError as exc:
        raise DerivSessionManagerError(str(exc)) from exc


class DerivSessionManager:
    """Account session bootstrap that fails closed without read-only scope."""

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
        configured_currency = (
            expected_currency
            if expected_currency is not None
            else os.getenv("DERIV_EXPECTED_CURRENCY", "")
        )
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

    def list_accounts(
        self,
        *,
        bearer_token: str | None = None,
        app_id: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            DerivAuthenticationGate(plane="account").get_client()
        except (AuthModeMismatchError, SecurityError) as exc:
            raise DerivSessionManagerError(str(exc)) from exc
        raise DerivSessionManagerError("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")

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
            targeted_row = (
                environment == self.expected_environment
                and (not self.expected_loginid or loginid == self.expected_loginid)
            )
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
        try:
            DerivAuthenticationGate(plane="account").get_client()
        except (AuthModeMismatchError, SecurityError) as exc:
            raise DerivSessionManagerError(str(exc)) from exc
        raise DerivSessionManagerError("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")
