"""Deterministic policy layer for AURELIA's Multi-LLM Brain Federation.

This module selects an approved model for an intelligence task. It never grants
capital authority and never mutates LIVE_LOCK or execution authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ModelEvidence:
    model_id: str
    task_type: str
    score: float
    sample_size: int
    reliability: float = 1.0
    calibration: float = 1.0
    evidence_quality: float = 1.0
    latency_ms: float = 0.0
    cost: float = 0.0
    available: bool = True
    stale: bool = False


@dataclass(frozen=True)
class RouteDecision:
    status: str
    agent_id: str
    task_type: str
    model_id: str | None
    challenger_ids: tuple[str, ...]
    reason: str
    high_consequence: bool
    deterministic_validation_required: bool
    capital_authority: bool = False


class ModelRouter:
    """Selects models from empirical evidence, with safe abstention."""

    def __init__(self, registry: Mapping[str, object], minimum_samples: int = 30) -> None:
        self.registry = registry
        self.minimum_samples = minimum_samples

    def route(
        self,
        *,
        agent_id: str,
        task_type: str,
        evidence: Sequence[ModelEvidence],
        high_consequence: bool = False,
        capital_relevant: bool = False,
    ) -> RouteDecision:
        agent = next((a for a in self.registry.get("agents", []) if a["agent_id"] == agent_id), None)
        if agent is None:
            return RouteDecision("ABSTAIN", agent_id, task_type, None, (), "UNKNOWN_AGENT", high_consequence, True)

        allowed = {agent["primary"], *agent.get("challengers", [])}
        candidates = [
            e for e in evidence
            if e.model_id in allowed
            and e.task_type == task_type
            and e.available
            and not e.stale
            and e.sample_size >= self.minimum_samples
            and all(isfinite(float(v)) for v in (e.score, e.reliability, e.calibration, e.evidence_quality))
        ]
        if not candidates:
            return RouteDecision("ABSTAIN", agent_id, task_type, None, tuple(agent.get("challengers", [])),
                                  "INSUFFICIENT_VERIFIED_MODEL_EVIDENCE", high_consequence, True)

        def utility(e: ModelEvidence) -> float:
            # Quality dominates. Reliability, calibration and evidence quality are
            # multiplicative guards; latency/cost are only tie-breaker pressure.
            quality = max(0.0, min(1.0, e.score))
            reliability = max(0.0, min(1.0, e.reliability))
            calibration = max(0.0, min(1.0, e.calibration))
            evidence_quality = max(0.0, min(1.0, e.evidence_quality))
            return quality * reliability * calibration * evidence_quality

        winner = max(candidates, key=lambda e: (utility(e), e.sample_size, -e.latency_ms, -e.cost))
        challengers = tuple(x for x in agent.get("challengers", []) if x != winner.model_id)

        return RouteDecision(
            "ROUTE",
            agent_id,
            task_type,
            winner.model_id,
            challengers,
            "EMPIRICAL_MODEL_EVIDENCE",
            high_consequence,
            high_consequence or capital_relevant,
            False,
        )
