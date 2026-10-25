from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol


class PaymentPolicyError(RuntimeError):
    """Stable, sanitized payment-policy rejection code."""

    pass


class HttpTransport(Protocol):
    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Transport interface supplied by a separately reviewed adapter."""
        ...


_ALLOWED_READ_PATHS = (
    "/payment-agents/v1/agent-statistics",
    "/payment-agents/v1/agents",
    "/payment-agents/v1/clients/me",
)


def _allowed_status_path(path: str) -> bool:
    if path in _ALLOWED_READ_PATHS:
        return True
    if path.startswith("/payment-agents/v1/agents/"):
        agent_id = path.rsplit("/", 1)[-1]
        return agent_id == "me" or (agent_id.isascii() and agent_id.isdigit() and len(agent_id) > 0)
    for prefix in (
        "/payment-agents/v1/transfer/",
        "/payment-agents/v1/withdraw/",
    ):
        if path.startswith(prefix):
            request_id = path[len(prefix):]
            # These status endpoints only; deliberately exclude verification_code and /withdraw.
            return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", request_id)) and request_id != "verification_code"
    return False


def assert_payment_request_allowed(
    *,
    method: str,
    path: str,
    capital_plane_mode: str | None,
    transport_mode: str,
) -> None:
    """Allow authenticated read-only Payment Agent REST only under explicit VERIFY_ONLY.

    TEST_ONLY must use in-process fixtures and must not access the network. This
    boundary deliberately rejects every REST write, including verification-code
    dispatch, PATCH client settings, transfer and withdrawal, even if a caller
    supplies dry_run=true.
    """
    if capital_plane_mode != "VERIFY_ONLY":
        raise PaymentPolicyError("CAPITAL_PLANE_MODE_NOT_VERIFY_ONLY")
    if transport_mode != "AUTHENTICATED_VERIFY_ONLY":
        raise PaymentPolicyError("PAYMENT_TRANSPORT_NOT_AUTHENTICATED_VERIFY_ONLY")
    if method.upper() != "GET":
        raise PaymentPolicyError("PAYMENT_WRITE_DISABLED")
    if not _allowed_status_path(path):
        raise PaymentPolicyError("PAYMENT_ENDPOINT_NOT_ALLOWLISTED")


@dataclass(frozen=True)
class GuardedPaymentAgentTransport:
    """Thin policy wrapper; caller must inject a transport explicitly.

    There is no concrete network transport in this module. Tests use recording
    fakes. A future HTTP adapter must instantiate this wrapper with values read
    from the canonical safety state, not from an LLM/tool argument.
    """

    transport: HttpTransport
    capital_plane_mode: str | None = None
    transport_mode: str = "TEST_ONLY"

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        assert_payment_request_allowed(
            method=method,
            path=path,
            capital_plane_mode=self.capital_plane_mode,
            transport_mode=self.transport_mode,
        )
        return self.transport.request(method.upper(), path, **kwargs)
