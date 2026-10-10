from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Sequence

from .intraday_bias_measurement import ForwardObservation, calculate_statistics

@dataclass(frozen=True)
class CostModel:
    proportional_cost: float = 0.0
    fixed_cost_return: float = 0.0
    slippage_return: float = 0.0

    def adjusted_returns(self, observations: Sequence[ForwardObservation]) -> list[float]:
        friction = self.proportional_cost + self.fixed_cost_return + self.slippage_return
        if friction < 0:
            raise ValueError("costs cannot be negative")
        return [x.raw_return - friction for x in observations]

def cost_adjusted_statistics(observations: Sequence[ForwardObservation], model: CostModel):
    return calculate_statistics(model.adjusted_returns(observations))

@dataclass(frozen=True)
class InstrumentCostProfile:
    """Verified instrument-specific round-trip costs for return backtests.

    All cost fields are basis points of the exact denominator used by raw_return.
    Spread cost is the paid round-trip spread impact; slippage must be incremental
    to spread. Explicit 0.0 means measured/verified zero; None means UNKNOWN.
    Contract-purchase strategies must use contract-P&L returns and cost inputs
    normalized to that same basis, never underlying-price returns.
    """

    instrument_id: str
    instrument_type: str
    return_basis: str
    spread_cost_bps_round_trip: float | None
    slippage_cost_bps_round_trip: float | None
    commission_bps_round_trip: float | None
    other_fees_bps_round_trip: float | None
    source: str
    observed_at_utc: str
    verified: bool
    slippage_excludes_spread: bool
    max_age_seconds: float = 86400.0

    def validate(
        self, *, now: datetime | None = None, require_verified: bool = True
    ) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.instrument_id.strip():
            errors.append("INSTRUMENT_ID_MISSING")
        if not self.instrument_type.strip():
            errors.append("INSTRUMENT_TYPE_MISSING")
        if not self.return_basis.strip():
            errors.append("RETURN_BASIS_MISSING")
        if not self.source.strip():
            errors.append("COST_SOURCE_MISSING")
        if require_verified and not self.verified:
            errors.append("COST_PROFILE_UNVERIFIED")
        if not self.slippage_excludes_spread:
            errors.append("SLIPPAGE_MAY_DOUBLE_COUNT_SPREAD")
        for name in (
            "spread_cost_bps_round_trip",
            "slippage_cost_bps_round_trip",
            "commission_bps_round_trip",
            "other_fees_bps_round_trip",
        ):
            value = getattr(self, name)
            if value is None:
                errors.append(f"COST_INPUT_UNKNOWN:{name}")
            elif not isfinite(float(value)) or float(value) < 0:
                errors.append(f"COST_INPUT_INVALID:{name}")
        if not isfinite(float(self.max_age_seconds)) or self.max_age_seconds <= 0:
            errors.append("COST_PROFILE_MAX_AGE_INVALID")
        captured = _parse_aware_utc(self.observed_at_utc)
        if captured is None:
            errors.append("COST_PROFILE_TIMESTAMP_INVALID")
        else:
            reference = now or datetime.now(timezone.utc)
            if reference.tzinfo is None:
                errors.append("VALIDATION_TIME_MUST_BE_TIMEZONE_AWARE")
            else:
                age = (reference.astimezone(timezone.utc) - captured).total_seconds()
                if age < 0:
                    errors.append("COST_PROFILE_FROM_FUTURE")
                elif age > self.max_age_seconds:
                    errors.append("COST_PROFILE_STALE")
        return tuple(errors)

    def total_cost_bps(
        self, *, now: datetime | None = None, require_verified: bool = True
    ) -> float:
        errors = self.validate(now=now, require_verified=require_verified)
        if errors:
            raise ValueError("COST_PROFILE_INVALID:" + ",".join(errors))
        return sum(
            float(value)
            for value in (
                self.spread_cost_bps_round_trip,
                self.slippage_cost_bps_round_trip,
                self.commission_bps_round_trip,
                self.other_fees_bps_round_trip,
            )
        )


@dataclass(frozen=True)
class LatencyProfile:
    """Latency quantiles plus separately measured slippage sensitivity.

    Sensitivity is an explicit model input in basis points per 100 ms; latency
    quantiles alone do not prove how much a delayed fill will cost. Qualification
    requires timestamped observations, a sensitivity source and >=100 samples.
    """

    p50_ms: float
    p95_ms: float
    p99_ms: float
    sample_count: int
    source: str
    sensitivity_source: str
    slippage_cost_bps_per_100ms: float | None
    observed_at_utc: str
    max_age_seconds: float = 86400.0
    minimum_samples: int = 100

    def validate(self, *, now: datetime | None = None) -> tuple[str, ...]:
        errors: list[str] = []
        quantiles = (self.p50_ms, self.p95_ms, self.p99_ms)
        if not all(isfinite(float(x)) and float(x) >= 0 for x in quantiles):
            errors.append("LATENCY_QUANTILE_INVALID")
        elif not self.p50_ms <= self.p95_ms <= self.p99_ms:
            errors.append("LATENCY_QUANTILES_NOT_MONOTONIC")
        if isinstance(self.sample_count, bool) or self.sample_count < self.minimum_samples:
            errors.append("LATENCY_SAMPLE_COUNT_INSUFFICIENT")
        if not self.source.strip():
            errors.append("LATENCY_SOURCE_MISSING")
        if not self.sensitivity_source.strip():
            errors.append("LATENCY_SENSITIVITY_SOURCE_MISSING")
        sensitivity = self.slippage_cost_bps_per_100ms
        if sensitivity is None:
            errors.append("LATENCY_COST_SENSITIVITY_UNKNOWN")
        elif not isfinite(float(sensitivity)) or float(sensitivity) < 0:
            errors.append("LATENCY_COST_SENSITIVITY_INVALID")
        if not isfinite(float(self.max_age_seconds)) or self.max_age_seconds <= 0:
            errors.append("LATENCY_PROFILE_MAX_AGE_INVALID")
        captured = _parse_aware_utc(self.observed_at_utc)
        if captured is None:
            errors.append("LATENCY_PROFILE_TIMESTAMP_INVALID")
        else:
            reference = now or datetime.now(timezone.utc)
            if reference.tzinfo is None:
                errors.append("VALIDATION_TIME_MUST_BE_TIMEZONE_AWARE")
            else:
                age = (reference.astimezone(timezone.utc) - captured).total_seconds()
                if age < 0:
                    errors.append("LATENCY_PROFILE_FROM_FUTURE")
                elif age > self.max_age_seconds:
                    errors.append("LATENCY_PROFILE_STALE")
        return tuple(errors)

    def scenario_delay_ms(self, scenario: str) -> float:
        quantiles = {"p50": self.p50_ms, "p95": self.p95_ms, "p99": self.p99_ms}
        try:
            return float(quantiles[scenario.strip().lower()])
        except KeyError as exc:
            raise ValueError("LATENCY_SCENARIO_MUST_BE_P50_P95_OR_P99") from exc

    def cost_bps_for_scenario(
        self, scenario: str, *, now: datetime | None = None
    ) -> float:
        errors = self.validate(now=now)
        if errors:
            raise ValueError("LATENCY_PROFILE_INVALID:" + ",".join(errors))
        return (
            self.scenario_delay_ms(scenario)
            / 100.0
            * float(self.slippage_cost_bps_per_100ms)
        )


def _parse_aware_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def instrument_cost_adjusted_returns(
    observations: Sequence[ForwardObservation],
    *,
    cost_profile: InstrumentCostProfile,
    latency_profile: LatencyProfile,
    observation_return_basis: str,
    latency_scenario: str = "p95",
    now: datetime | None = None,
    require_verified_costs: bool = True,
) -> list[float]:
    """Deduct verified round-trip costs and selected latency stress from returns."""
    if not observation_return_basis.strip():
        raise ValueError("OBSERVATION_RETURN_BASIS_REQUIRED")
    if observation_return_basis != cost_profile.return_basis:
        raise ValueError("RETURN_BASIS_MISMATCH")
    base_cost_bps = cost_profile.total_cost_bps(
        now=now, require_verified=require_verified_costs
    )
    latency_cost_bps = latency_profile.cost_bps_for_scenario(
        latency_scenario, now=now
    )
    total_friction = (base_cost_bps + latency_cost_bps) / 10000.0
    return [float(row.raw_return) - total_friction for row in observations]


def instrument_cost_adjusted_statistics(
    observations: Sequence[ForwardObservation],
    *,
    cost_profile: InstrumentCostProfile,
    latency_profile: LatencyProfile,
    observation_return_basis: str,
    latency_scenario: str = "p95",
    now: datetime | None = None,
    require_verified_costs: bool = True,
):
    adjusted = instrument_cost_adjusted_returns(
        observations,
        cost_profile=cost_profile,
        latency_profile=latency_profile,
        observation_return_basis=observation_return_basis,
        latency_scenario=latency_scenario,
        now=now,
        require_verified_costs=require_verified_costs,
    )
    return calculate_statistics(adjusted)

