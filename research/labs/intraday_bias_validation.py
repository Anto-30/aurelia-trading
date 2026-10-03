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
    min_positive_oos_expectancy: float = 0.0

def chronological_split(observations: Sequence[ForwardObservation], *, is_end_utc: str):
    cutoff = datetime.fromisoformat(is_end_utc.replace("Z", "+00:00"))
    ordered = sorted(observations, key=lambda x: x.entry_timestamp_utc)
    is_rows = [x for x in ordered if datetime.fromisoformat(x.entry_timestamp_utc.replace("Z", "+00:00")) < cutoff]
    oos_rows = [x for x in ordered if datetime.fromisoformat(x.entry_timestamp_utc.replace("Z", "+00:00")) >= cutoff]
    return is_rows, oos_rows

def validate_level1(*, observations: Sequence[ForwardObservation],
                    is_observations: Sequence[ForwardObservation],
                    oos_observations: Sequence[ForwardObservation],
                    adjusted_q_value: float | None,
                    config: ValidationConfig = ValidationConfig()) -> str:
    if len(observations) < config.min_total_observations:
        return "INSUFFICIENT_SAMPLE"
    if len(is_observations) < config.min_is_observations or len(oos_observations) < config.min_oos_observations:
        return "INSUFFICIENT_SAMPLE"
    if adjusted_q_value is None or adjusted_q_value > config.max_q_value:
        return "IN_SAMPLE_ONLY"
    is_stats = calculate_statistics([x.raw_return for x in is_observations])
    oos_stats = calculate_statistics([x.raw_return for x in oos_observations])
    if is_stats.expectancy is None or is_stats.expectancy <= 0:
        return "IN_SAMPLE_ONLY"
    if oos_stats.expectancy is None or oos_stats.expectancy <= config.min_positive_oos_expectancy:
        return "OOS_FAILED"
    if oos_stats.max_drawdown is not None and oos_stats.max_drawdown > config.max_oos_drawdown:
        return "UNSTABLE"
    return "ROBUST_BULLISH_PRIOR"

def classify_directional(*, is_observations: Sequence[ForwardObservation],
                         oos_observations: Sequence[ForwardObservation],
                         adjusted_q_value: float | None,
                         config: ValidationConfig = ValidationConfig()) -> str:
    base = validate_level1(observations=list(is_observations)+list(oos_observations),
                           is_observations=is_observations, oos_observations=oos_observations,
                           adjusted_q_value=adjusted_q_value, config=config)
    if base != "ROBUST_BULLISH_PRIOR":
        return base
    if calculate_statistics([x.raw_return for x in oos_observations]).expectancy < 0:
        return "ROBUST_BEARISH_PRIOR"
    return base
