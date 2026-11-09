from __future__ import annotations

from collections.abc import Mapping
import os


# These names are forbidden in the public research process. Presence is
# sufficient to reject the process; values are never read.
ACCOUNT_CREDENTIAL_ENV_NAMES = (
    "DERIV_AUTH_TOKEN",
    "DERIV_PAT",
    "DERIV_OAUTH_ACCESS_TOKEN",
    "DERIV_OAUTH_REFRESH_TOKEN",
    "DERIV_REFRESH_TOKEN",
    "DERIV_APP_ID",
    "DERIV_EXPECTED_LOGINID",
    "DERIV_AUTHORIZED_ACCOUNT_ID",
    "DERIV_EXPECTED_CURRENCY",
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
        # The required account-list and authenticated OTP endpoints require
        # trade scope. No documented read-only account scope is available.
        # Do not inspect or consume any token, PAT, refresh token, or account
        # metadata before failing closed.
        raise SecurityError("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")
