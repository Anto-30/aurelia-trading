"""Compatibility import for research code; enforcement lives in runtime/security."""

from runtime.security.deriv_auth_gate import (
    ACCOUNT_CREDENTIAL_ENV_NAMES,
    DEFAULT_PUBLIC_APP_ID,
    PUBLIC_RESEARCH_ACTIONS,
    PUBLIC_RESEARCH_WS_URL,
    AuthModeMismatchError,
    DerivAuthenticationGate,
    DerivPublicClient,
    SecurityError,
)

__all__ = [
    "ACCOUNT_CREDENTIAL_ENV_NAMES",
    "DEFAULT_PUBLIC_APP_ID",
    "PUBLIC_RESEARCH_ACTIONS",
    "PUBLIC_RESEARCH_WS_URL",
    "AuthModeMismatchError",
    "DerivAuthenticationGate",
    "DerivPublicClient",
    "SecurityError",
]
