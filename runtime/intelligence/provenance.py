"""Provenance and knowledge-lifecycle primitives for intelligence-plane objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


LIFECYCLE = ("created", "tested", "active", "degraded", "expired", "revalidated")


@dataclass(frozen=True)
class Provenance:
    object_id: str
    origin: str
    observed_at_utc: str
    source_ids: tuple[str, ...]
    contributing_agents: tuple[str, ...]
    validation_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    last_validated_at_utc: str | None
    lifecycle: str

    def validate(self) -> None:
        if self.lifecycle not in LIFECYCLE:
            raise ValueError("INVALID_KNOWLEDGE_LIFECYCLE")
        if not self.origin or not self.observed_at_utc:
            raise ValueError("MISSING_KNOWLEDGE_PROVENANCE")
        if self.lifecycle in {"tested", "active", "revalidated"} and not self.validation_ids:
            raise ValueError("VALIDATED_KNOWLEDGE_REQUIRES_VALIDATION_ID")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stale(observed_at_utc: str, max_age_seconds: int, *, now: datetime | None = None) -> bool:
    observed = datetime.fromisoformat(observed_at_utc.replace("Z", "+00:00"))
    current = now or datetime.now(timezone.utc)
    return (current - observed).total_seconds() > max_age_seconds
