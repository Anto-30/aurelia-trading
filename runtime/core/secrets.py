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
    """Fail fast unless this is an explicitly sealed non-production soak."""
    if os.getenv("AURELIA_NON_PRODUCTION_SOAK", "").strip().lower() == "true":
        sealed_flags = {
            "FINAL_EXECUTION_AUTHORIZATION": os.getenv(
                "FINAL_EXECUTION_AUTHORIZATION", ""
            ).strip().lower() == "false",
            "LIVE_EXECUTION": os.getenv("LIVE_EXECUTION", "").strip().upper() == "BLOCKED",
            "AURELIA_VERIFY_DERIV_PUBLIC": os.getenv(
                "AURELIA_VERIFY_DERIV_PUBLIC", ""
            ).strip().lower() == "false",
            "AURELIA_VERIFY_DERIV_AUTH": os.getenv(
                "AURELIA_VERIFY_DERIV_AUTH", ""
            ).strip().lower() == "false",
            "AURELIA_CONTINUOUS_RUNTIME": os.getenv(
                "AURELIA_CONTINUOUS_RUNTIME", ""
            ).strip().lower() == "false",
        }
        if all(sealed_flags.values()):
            return
        failed = [name for name, valid in sealed_flags.items() if not valid]
        raise SecretsError(
            "NON_PRODUCTION_SOAK_NOT_SEALED: " + ",".join(failed)
        )

    required = ["DERIV_AUTH_TOKEN", "DERIV_APP_ID"]
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise SecretsError(
            f"STARTUP_SECRET_VALIDATION_FAILED: missing={missing}"
        )
