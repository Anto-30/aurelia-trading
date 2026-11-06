from __future__ import annotations

from collections.abc import Mapping
import os


ACCOUNT_CREDENTIAL_ENV_NAMES = (
    "DERIV_AUTH_TOKEN",
    "DERIV_PAT",
    "DERIV_OAUTH_ACCESS_TOKEN",
    "DERIV_OAUTH_REFRESH_TOKEN",
    "DERIV_REFRESH_TOKEN",
)


class SecurityError(RuntimeError):
    """Raised when a Deriv account authentication invariant is violated."""


class AuthModeMismatchError(RuntimeError):
    """Raised when account credentials do not match the selected auth mode."""


class DerivAuthenticationGate:
    """Fail-closed account-plane gate; no authenticated account client is issued."""

    def __init__(
        self,
        plane: str = "account",
        *,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        if plane != "account":
            raise ValueError("UNKNOWN_DERIV_AUTH_PLANE")
        self.environ = os.environ if environ is None else environ

    def get_client(self):
        env = self.environ
        mode = str(env.get("ACCOUNT_DERIV_AUTH_MODE", "none")).strip().lower()
        if mode != "oauth":
            raise AuthModeMismatchError("ACCOUNT_PLANE_REQUIRES_EXPLICIT_OAUTH_MODE")

        oauth_token = str(env.get("DERIV_OAUTH_ACCESS_TOKEN", "")).strip()
        pat_token = str(env.get("DERIV_PAT", "")).strip()
        generic_token = str(env.get("DERIV_AUTH_TOKEN", "")).strip()
        refresh_token = (
            str(env.get("DERIV_OAUTH_REFRESH_TOKEN", "")).strip()
            or str(env.get("DERIV_REFRESH_TOKEN", "")).strip()
        )

        if oauth_token and pat_token and oauth_token == pat_token:
            raise SecurityError("OAUTH_TOKEN_EQUALS_PAT")
        if pat_token:
            raise SecurityError("ACCOUNT_PLANE_PAT_PRESENT")
        if generic_token:
            raise AuthModeMismatchError("GENERIC_TOKEN_FALLBACK_BLOCKED")
        if refresh_token:
            raise SecurityError("DERIV_OAUTH_REFRESH_TOKEN_UNSUPPORTED")
        # Token presence, token shape, and OAuth/PAT distinction do not prove
        # a read-only scope. Deriv's required account-list and OTP endpoints
        # currently require `trade`; no account client is issued whether the
        # OAuth token is absent or present.
        raise SecurityError("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")
