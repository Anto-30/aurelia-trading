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

@dataclass(frozen=True)
class DerivRateLimitProfile:
    """Documented Deriv API request budgets; treat as versioned, changeable inputs."""

    ws_trading_per_minute: int = 360
    ws_trading_per_hour: int = 14400
    ws_account_per_minute: int = 100
    ws_account_per_hour: int = 2000
    ws_portfolio_per_minute: int = 30
    ws_portfolio_per_hour: int = 1500
    ws_other_per_minute: int = 220
    ws_other_per_hour: int = 14400
    ws_ping_per_second: int = 10
    rest_ip_per_minute: int = 300
    rest_ip_per_10_minutes: int = 1000
    rest_account_per_minute: int = 80
    documentation_url: str = "https://developers.deriv.com/docs/limits/"
    documented_at_utc: str = "2026-10-10"

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if name.endswith(("_per_minute", "_per_hour", "_per_second", "_per_10_minutes")):
                if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    raise ValueError("RATE_LIMITS_MUST_BE_POSITIVE_INTEGERS")


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    budget: str
    reason: str | None = None
    retry_after_seconds: float = 0.0


class ApiRateLimitSimulator:
    """Deterministic sliding-window rate-limit simulator for Layer 9.

    The simulator accepts monotonic timestamps supplied by the test harness and
    never sleeps or sends network requests. Rejected attempts are not charged to
    a simulated budget; callers must model backoff after RATE_LIMITED decisions.
    """

    _TRADING = frozenset({"proposal", "proposal_open_contract", "buy", "sell"})
    _ACCOUNT = frozenset({"balance", "statement"})
    _PORTFOLIO = frozenset({"portfolio", "profit_table"})

    def __init__(self, profile: DerivRateLimitProfile | None = None) -> None:
        self.profile = profile or DerivRateLimitProfile()
        self._events: dict[tuple[str, str], list[float]] = {}
        self._last_timestamp: float | None = None

    @staticmethod
    def _prune(events: list[float], now: float, window: float) -> list[float]:
        return [stamp for stamp in events if 0 <= now - stamp < window]

    @staticmethod
    def classify_websocket_request(request_type: str) -> str:
        name = str(request_type).strip().lower()
        if name in ApiRateLimitSimulator._TRADING:
            return "trading"
        if name in ApiRateLimitSimulator._ACCOUNT:
            return "account"
        if name in ApiRateLimitSimulator._PORTFOLIO:
            return "portfolio"
        if name == "ping":
            return "ping"
        return "other"

    def _check_time(self, timestamp_seconds: float) -> None:
        if not isfinite(float(timestamp_seconds)) or timestamp_seconds < 0:
            raise ValueError("RATE_LIMIT_TIMESTAMP_INVALID")
        if self._last_timestamp is not None and timestamp_seconds < self._last_timestamp:
            raise ValueError("RATE_LIMIT_TIMESTAMP_MUST_BE_MONOTONIC")
        self._last_timestamp = timestamp_seconds

    def simulate_request(
        self,
        *,
        protocol: str,
        request_type: str,
        timestamp_seconds: float,
        account_key: str = "default-account",
        ip_key: str = "default-ip",
        connection_key: str = "default-connection",
    ) -> RateLimitDecision:
        """Simulate one WS/REST request and return allow/block plus retry delay."""
        self._check_time(timestamp_seconds)
        protocol = protocol.strip().lower()
        if protocol in {"ws", "websocket"}:
            return self._simulate_websocket(
                request_type, timestamp_seconds, connection_key
            )
        if protocol == "rest":
            return self._simulate_rest(
                timestamp_seconds, account_key=account_key, ip_key=ip_key
            )
        raise ValueError("RATE_LIMIT_PROTOCOL_MUST_BE_WEBSOCKET_OR_REST")

    def _simulate_websocket(
        self, request_type: str, now: float, connection_key: str
    ) -> RateLimitDecision:
        group = self.classify_websocket_request(request_type)
        if group == "ping":
            key = ("ws_ping", connection_key)
            events = self._prune(self._events.get(key, []), now, 1.0)
            limit = self.profile.ws_ping_per_second
            if len(events) >= limit:
                retry = max(0.0, min(events) + 1.0 - now)
                self._events[key] = events
                return RateLimitDecision(False, "ws_ping", "RATE_LIMITED", retry)
            events.append(now)
            self._events[key] = events
            return RateLimitDecision(True, "ws_ping")

        values = {
            "trading": (self.profile.ws_trading_per_minute, self.profile.ws_trading_per_hour),
            "account": (self.profile.ws_account_per_minute, self.profile.ws_account_per_hour),
            "portfolio": (self.profile.ws_portfolio_per_minute, self.profile.ws_portfolio_per_hour),
            "other": (self.profile.ws_other_per_minute, self.profile.ws_other_per_hour),
        }
        minute_limit, hour_limit = values[group]
        key = ("ws", group)
        events = self._prune(self._events.get(key, []), now, 3600.0)
        recent_minute = [stamp for stamp in events if now - stamp < 60.0]
        waits: list[float] = []
        if len(recent_minute) >= minute_limit:
            waits.append(max(0.0, min(recent_minute) + 60.0 - now))
        if len(events) >= hour_limit:
            waits.append(max(0.0, min(events) + 3600.0 - now))
        if waits:
            self._events[key] = events
            return RateLimitDecision(False, f"ws_{group}", "RATE_LIMITED", max(waits))
        events.append(now)
        self._events[key] = events
        return RateLimitDecision(True, f"ws_{group}")

    def _simulate_rest(
        self, now: float, *, account_key: str, ip_key: str
    ) -> RateLimitDecision:
        ip_id, account_id = ("rest_ip", ip_key), ("rest_account", account_key)
        ip_events = self._prune(self._events.get(ip_id, []), now, 600.0)
        account_events = self._prune(self._events.get(account_id, []), now, 60.0)
        ip_minute = [stamp for stamp in ip_events if now - stamp < 60.0]
        waits: list[float] = []
        if len(ip_minute) >= self.profile.rest_ip_per_minute:
            waits.append(max(0.0, min(ip_minute) + 60.0 - now))
        if len(ip_events) >= self.profile.rest_ip_per_10_minutes:
            waits.append(max(0.0, min(ip_events) + 600.0 - now))
        if len(account_events) >= self.profile.rest_account_per_minute:
            waits.append(max(0.0, min(account_events) + 60.0 - now))
        if waits:
            self._events[ip_id] = ip_events
            self._events[account_id] = account_events
            return RateLimitDecision(False, "rest", "RATE_LIMITED", max(waits))
        ip_events.append(now)
        account_events.append(now)
        self._events[ip_id], self._events[account_id] = ip_events, account_events
        return RateLimitDecision(True, "rest")

