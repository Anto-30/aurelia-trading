from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from .intraday_bias_measurement import ForwardObservation, calculate_statistics


@dataclass(frozen=True)
class ValidationConfig:
    min_total_observations: int = 240
    min_is_observations: int = 120
    min_oos_observations: int = 60
    max_oos_drawdown: float = 0.50
    max_q_value: float = 0.10


def chronological_split(observations: Sequence[ForwardObservation], *, is_end_utc: str):
    cutoff = datetime.fromisoformat(is_end_utc.replace("Z", "+00:00"))
    ordered = sorted(observations, key=lambda x: x.entry_timestamp_utc)
    is_rows = [x for x in ordered if datetime.fromisoformat(x.entry_timestamp_utc.replace("Z", "+00:00")) < cutoff]
    oos_rows = [x for x in ordered if datetime.fromisoformat(x.entry_timestamp_utc.replace("Z", "+00:00")) >= cutoff]
    return is_rows, oos_rows


def _directional_max_drawdown(returns: Sequence[float]) -> float | None:
    if not returns:
        return None
    stats = calculate_statistics(returns)
    return stats.max_drawdown


def validate_level1(
    *,
    observations: Sequence[ForwardObservation],
    is_observations: Sequence[ForwardObservation],
    oos_observations: Sequence[ForwardObservation],
    adjusted_q_value: float | None,
    config: ValidationConfig = ValidationConfig(),
    cost_adjusted_oos_expectancy: float | None = None,
) -> str:
    if len(observations) < config.min_total_observations:
        return "INSUFFICIENT_SAMPLE"
    if len(is_observations) < config.min_is_observations or len(oos_observations) < config.min_oos_observations:
        return "INSUFFICIENT_SAMPLE"
    if adjusted_q_value is None or adjusted_q_value > config.max_q_value:
        return "IN_SAMPLE_ONLY"

    is_stats = calculate_statistics([x.raw_return for x in is_observations])
    oos_returns = [x.raw_return for x in oos_observations]
    oos_stats = calculate_statistics(oos_returns)
    if is_stats.expectancy is None or oos_stats.expectancy is None:
        return "NO_EVIDENCE"
    if cost_adjusted_oos_expectancy is not None and cost_adjusted_oos_expectancy <= 0:
        return "COST_ERODED"
    if is_stats.expectancy == 0 or oos_stats.expectancy == 0:
        return "OOS_FAILED"
    if is_stats.expectancy * oos_stats.expectancy <= 0:
        return "OOS_FAILED"

    direction = 1.0 if oos_stats.expectancy > 0 else -1.0
    directional_oos_returns = [direction * x for x in oos_returns]
    if _directional_max_drawdown(directional_oos_returns) is not None and _directional_max_drawdown(directional_oos_returns) > config.max_oos_drawdown:
        return "UNSTABLE"

    return "ROBUST_BULLISH_PRIOR" if direction > 0 else "ROBUST_BEARISH_PRIOR"


def classify_directional(
    *,
    is_observations: Sequence[ForwardObservation],
    oos_observations: Sequence[ForwardObservation],
    adjusted_q_value: float | None,
    config: ValidationConfig = ValidationConfig(),
) -> str:
    return validate_level1(
        observations=list(is_observations) + list(oos_observations),
        is_observations=is_observations,
        oos_observations=oos_observations,
        adjusted_q_value=adjusted_q_value,
        config=config,
    )
