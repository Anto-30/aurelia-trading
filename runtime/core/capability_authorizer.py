from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class CapabilityRequest:
    actor: str
    capability: str
    side_effect: str
    environment: str
    secret_scope: str = "NONE"


@dataclass(frozen=True)
class CapabilityDecision:
    allowed: bool
    reason: str


class CapabilityAuthorizer:
    """Deny-by-default boundary for agent/tool side effects.

    This layer never grants capital authority. Capital release remains owned by
    the deterministic capital-plane controls and LIVE_LOCK.
    """

    CAPITAL_CAPABILITIES: FrozenSet[str] = frozenset({
        "authorize_capital", "submit_order", "flip_live_lock",
    })

    def __init__(self, boundary: dict):
        self.boundary = boundary

    def authorize(self, request: CapabilityRequest) -> CapabilityDecision:
        actor_cfg = self.boundary.get("actors", {}).get(request.actor)
        if not isinstance(actor_cfg, dict):
            return CapabilityDecision(False, "ACTOR_NOT_REGISTERED")

        if request.capability in self.CAPITAL_CAPABILITIES:
            return CapabilityDecision(False, "CAPITAL_CAPABILITY_FORBIDDEN_AT_AGENT_BOUNDARY")

        allowed = set(actor_cfg.get("may", []))
        denied = set(actor_cfg.get("may_not", []))
        if request.capability in denied:
            return CapabilityDecision(False, "CAPABILITY_EXPLICITLY_DENIED")
        if request.capability not in allowed:
            return CapabilityDecision(False, "CAPABILITY_NOT_GRANTED")

        if request.environment == "real" and request.side_effect in {"CAPITAL", "ORDER_SUBMISSION"}:
            return CapabilityDecision(False, "REAL_CAPITAL_SIDE_EFFECT_REQUIRES_DETERMINISTIC_AUTHORITY")

        if request.secret_scope not in {"NONE", "PUBLIC"}:
            return CapabilityDecision(False, "SECRET_SCOPE_NOT_GRANTED")

        return CapabilityDecision(True, "CAPABILITY_GRANTED")
