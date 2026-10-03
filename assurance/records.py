"""Typed, execution-neutral records for evidence, replay and near-miss analysis."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    decision_time_utc: str
    strategy_version: str
    model_version: Optional[str]
    probability: Optional[float]
    knowledge_snapshot: Optional[str]
    config_hash: str
    market_data_hash: str
    action: str
    authorization: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NearMissRecord:
    near_miss_id: str
    occurred_at_utc: str
    category: str
    trigger: str
    control_that_intervened: str
    expected_outcome: str
    observed_outcome: str
    correlation_id: str
    invariant_status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    hypothesis_id: str
    strategy_version: str
    dataset_hashes: tuple[str, ...]
    code_commit: str
    config_hash: str
    random_seeds: tuple[int, ...]
    search_space: str
    trial_count: int
    oos_reservation: str
    result: str
    limitations: str
