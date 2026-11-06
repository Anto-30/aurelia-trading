"""Centralized secrets access with validation and redaction."""
from __future__ import annotations

import os
from collections.abc import Mapping
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


def account_credential_keys_present(
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Check forbidden account-credential key presence without reading values."""
    

    source = os.environ if environ is None else environ
    return any(name in source for name in ACCOUNT_CREDENTIAL_ENV_NAMES)


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
            

            if account_credential_keys_present():
                raise SecretsError(
                    "NON_PRODUCTION_SOAK_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED"
                )
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
        # Public research is credential-free. Account authentication is not
        # available until Deriv documents a genuine read-only permission.
        if os.getenv("AURELIA_VERIFY_DERIV_AUTH", "").strip().lower() != "true":
            

            if account_credential_keys_present():
                raise SecretsError(
                    "VERIFY_ONLY_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED"
                )
            return

    from runtime.security.deriv_auth_gate import (
        AuthModeMismatchError,
        DerivAuthenticationGate,
        SecurityError,
    )

    try:
        DerivAuthenticationGate(plane="account").get_client()
    except (AuthModeMismatchError, SecurityError) as exc:
        raise SecretsError(str(exc)) from exc
    raise SecretsError("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")
