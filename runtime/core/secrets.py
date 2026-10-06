"""Centralized secrets access with validation and redaction."""
from __future__ import annotations

import os
from functools import lru_cache


class SecretsError(RuntimeError):
    """Raised when required runtime secrets are unavailable."""


@lru_cache(maxsize=1)
def get_required_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SecretsError(f"REQUIRED_SECRET_MISSING: {name}")
    return value


def get_optional_secret(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def redact(value: str, visible_chars: int = 4) -> str:
    """Redact a secret for safe logging, showing only its final N characters."""
    if len(value) <= visible_chars:
        return "***"
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]


def validate_secrets_at_startup() -> None:
    """Fail fast before runtime initialization if critical secrets are absent."""
    required = ["DERIV_AUTH_TOKEN", "DERIV_APP_ID"]
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise SecretsError(
            f"STARTUP_SECRET_VALIDATION_FAILED: missing={missing}"
        )
