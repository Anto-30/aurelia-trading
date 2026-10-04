"""Independent production controls for AURELIA.

These controls deliberately fail closed. They provide decision-time freshness,
configuration-drift, canary, circuit-breaker, and post-trade safety primitives.
They do not grant capital authority and never modify LIVE_LOCK.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any, Mapping


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def age_seconds(captured_at: datetime, *, now: datetime | None = None) -> float:
    observed = now or utc_now()
    if captured_at.tzinfo is None:
        raise ValueError("CAPTURE_TIME_MUST_BE_TIMEZONE_AWARE")
    return (observed - captured_at).total_seconds()


def fresh(captured_at: datetime, max_age_seconds: float, *, now: datetime | None = None) -> bool:
    age = age_seconds(captured_at, now=now)
    return 0 <= age <= max_age_seconds


@dataclass(frozen=True)
class DecisionTimeGate:
    market_data_fresh: bool
    probability_fresh: bool
    probability_valid: bool
    probability_drift_ok: bool
    capital_fresh: bool
    configuration_current: bool
    deployment_current: bool

    @property
    def passed(self) -> bool:
        return all((self.market_data_fresh, self.probability_fresh, self.probability_valid,
                    self.probability_drift_ok, self.capital_fresh,
                    self.configuration_current, self.deployment_current))


def sha256_payload(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configuration_matches(expected_hash: str, actual_hash: str) -> bool:
    return bool(expected_hash and actual_hash and expected_hash == actual_hash)


def deployment_matches(*, source_hash: str, runtime_source_hash: str,
                       artifact_hash: str, runtime_artifact_hash: str) -> bool:
    return bool(source_hash and runtime_source_hash and artifact_hash and runtime_artifact_hash
                and source_hash == runtime_source_hash and artifact_hash == runtime_artifact_hash)


@dataclass
class CircuitBreaker:
    max_consecutive_failures: int = 3
    max_reconciliation_failures: int = 1
    max_slippage_breaches: int = 2
    consecutive_failures: int = 0
    reconciliation_failures: int = 0
    slippage_breaches: int = 0
    tripped: bool = False
    reason: str | None = None

    def _trip(self, reason: str) -> None:
        self.tripped = True
        self.reason = reason

    def record_broker_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_consecutive_failures:
            self._trip("BROKER_FAILURE_THRESHOLD")

    def record_reconciliation_failure(self) -> None:
        self.reconciliation_failures += 1
        self._trip("RECONCILIATION_FAILURE")

    def record_slippage_breach(self) -> None:
        self.slippage_breaches += 1
        if self.slippage_breaches >= self.max_slippage_breaches:
            self._trip("SLIPPAGE_BREACH_THRESHOLD")

    def record_success(self) -> None:
        self.consecutive_failures = 0

    def permit(self) -> bool:
        return not self.tripped

    def reset(self) -> None:
        self.tripped = False
        self.reason = None
        self.consecutive_failures = 0
        self.reconciliation_failures = 0
        self.slippage_breaches = 0


@dataclass(frozen=True)
class CanaryPolicy:
    max_trades: int = 1
    max_stake: float = 1.0

    def permits(self, *, trades_completed: int, stake: float) -> bool:
        return trades_completed < self.max_trades and isfinite(stake) and 0 < stake <= self.max_stake


def post_trade_guard(*, reconciliation_healthy: bool, unexpected_balance_delta: bool,
                     slippage_breach: bool, broker_status_known: bool,
                     circuit: CircuitBreaker) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if not broker_status_known:
        reasons.append("BROKER_STATUS_UNKNOWN")
    if not reconciliation_healthy:
        circuit.record_reconciliation_failure()
        reasons.append("RECONCILIATION_FAILED")
    if unexpected_balance_delta:
        reasons.append("UNEXPECTED_BALANCE_DELTA")
    if slippage_breach:
        circuit.record_slippage_breach()
        reasons.append("SLIPPAGE_BREACH")
    if circuit.tripped:
        reasons.append(circuit.reason or "CIRCUIT_BREAKER_TRIPPED")
    return not reasons, tuple(reasons)
