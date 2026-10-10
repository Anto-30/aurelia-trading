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

    # A locked verify-only worker may run without broker credentials, but
    # only when every runtime/capital flag is explicitly sealed.
    deployment_mode = os.getenv("AURELIA_DEPLOYMENT_MODE", "").strip().upper()
    if deployment_mode == "VERIFY_ONLY":
        sealed_flags = {
            "FINAL_EXECUTION_AUTHORIZATION": os.getenv(
                "FINAL_EXECUTION_AUTHORIZATION", ""
            ).strip().lower() == "false",
            "LIVE_EXECUTION": os.getenv("LIVE_EXECUTION", "").strip().upper() == "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": os.getenv(
                "AURELIA_AUTONOMOUS_LOOP", ""
            ).strip().lower() == "false",
        }
        if not all(sealed_flags.values()):
            failed = [name for name, valid in sealed_flags.items() if not valid]
            raise SecretsError(
                "VERIFY_ONLY_RUNTIME_NOT_SEALED: " + ",".join(failed)
            )
        # Permit a credential-free locked worker to run, but if read-only broker
        # verification was requested, validate its credentials before startup.
        if os.getenv("AURELIA_VERIFY_DERIV_AUTH", "").strip().lower() != "true":
            return

    auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower() or "pat"
    token = os.getenv("DERIV_AUTH_TOKEN", "").strip() or os.getenv("DERIV_PAT", "").strip()
    loginid = os.getenv("DERIV_EXPECTED_LOGINID", "").strip() or os.getenv(
        "DERIV_AUTHORIZED_ACCOUNT_ID", ""
    ).strip()
    currency = os.getenv("DERIV_EXPECTED_CURRENCY", "").strip()
    environment = os.getenv("DERIV_ENVIRONMENT", "").strip().lower()

    missing: list[str] = []
    if not token:
        missing.append("DERIV_AUTH_TOKEN_OR_DERIV_PAT")
    if auth_mode not in {"pat", "oauth"}:
        raise SecretsError("STARTUP_AUTH_MODE_INVALID")
    if auth_mode == "pat" and not os.getenv("DERIV_APP_ID", "").strip():
        missing.append("DERIV_APP_ID")
    if not loginid:
        missing.append("DERIV_EXPECTED_LOGINID_OR_DERIV_AUTHORIZED_ACCOUNT_ID")
    if not currency:
        missing.append("DERIV_EXPECTED_CURRENCY")
    if environment not in {"real", "demo"}:
        missing.append("DERIV_ENVIRONMENT")
    if deployment_mode == "LIVE" and environment != "real":
        raise SecretsError("LIVE_RUNTIME_REQUIRES_REAL_DERIV_ENVIRONMENT")
    if missing:
        raise SecretsError(
            f"STARTUP_SECRET_VALIDATION_FAILED: missing={missing}"
        )
    # A locked VERIFY_ONLY process may authenticate and verify its account,
    # but capital authority and autonomous order execution remain sealed above.
    if deployment_mode == "VERIFY_ONLY":
        return
