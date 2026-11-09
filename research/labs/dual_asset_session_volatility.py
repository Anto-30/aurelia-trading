"""Dual-asset, research-only session and volatility controls.

Session timing is applied only to financial instruments. Synthetic indices are
explicitly labelled SYNTHETIC_BYPASS and are never filtered by time of day.

The volatility estimators consume one-period strategy/instrument returns and
use only observations strictly before the trade bar. The resulting multiplier
is a research sizing input, not live capital authority. The Moreira–Muir paper
uses inverse prior realized variance with a normalization step; this module's
default inverse-standard-deviation rule is an explicitly labelled adaptation,
not a replication of that published portfolio construction.
"""
from __future__ import annotations

import math
import statistics
import warnings
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Literal, Sequence
from zoneinfo import ZoneInfo

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
ORDER_SUBMISSION_PERMITTED = False

ASSET_CLASSES = {"financial", "synthetic"}
SESSIONS = {"ASIAN", "LONDON", "NY_AM", "NY_PM", "DEAD", "SYNTHETIC_BYPASS"}

TOKYO = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")


def _aware_datetime(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("SESSION_TIMESTAMP_INVALID") from exc
    if not isinstance(value, datetime):
        raise ValueError("SESSION_TIMESTAMP_INVALID")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("SESSION_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return value


def _clock_in_window(local_time: time, start: time, end: time, buffer_minutes: int = 0) -> bool:
    start_minutes = start.hour * 60 + start.minute - buffer_minutes
    end_minutes = end.hour * 60 + end.minute + buffer_minutes
    current = local_time.hour * 60 + local_time.minute
    return start_minutes <= current < end_minutes


def classify_session(timestamp: datetime | str, asset_class: str) -> str:
    """Return one exclusive session label using IANA-local wall-clock windows.

    Windows:
      ASIAN: Tokyo 09:00–16:00 (equivalent to 00:00–07:00 UTC; no Tokyo DST)
      LONDON: London 07:00–10:00 local (UTC shifts with UK DST)
      NY_AM: New York 08:30–11:00 local
      NY_PM: New York 11:00–19:00 local

    London takes precedence over the overlapping Tokyo close. NY windows are
    disjoint from the London window. The 2:33 AM and 4:15 AM anecdotal markers
    are intentionally not special cases.
    """
    normalized = str(asset_class).strip().lower()
    if normalized not in ASSET_CLASSES:
        raise ValueError("ASSET_CLASS_MUST_BE_FINANCIAL_OR_SYNTHETIC")
    if normalized == "synthetic":
        return "SYNTHETIC_BYPASS"

    stamp = _aware_datetime(timestamp)
    ny = stamp.astimezone(NEW_YORK).timetz().replace(tzinfo=None)
    london = stamp.astimezone(LONDON).timetz().replace(tzinfo=None)
    tokyo = stamp.astimezone(TOKYO).timetz().replace(tzinfo=None)

    if _clock_in_window(ny, time(8, 30), time(11, 0)):
        return "NY_AM"
    if _clock_in_window(ny, time(11, 0), time(19, 0)):
        return "NY_PM"
    if _clock_in_window(london, time(7, 0), time(10, 0)):
        return "LONDON"
    if _clock_in_window(tokyo, time(9, 0), time(16, 0)):
        return "ASIAN"
    return "DEAD"


def _extract_timestamps(frame: Any, timestamp_column: str | None) -> tuple[list[Any], Any]:
    if timestamp_column is not None:
        try:
            values = list(frame[timestamp_column])
        except (KeyError, TypeError) as exc:
            raise ValueError("SESSION_TIMESTAMP_COLUMN_MISSING") from exc
        index = getattr(frame, "index", None)
        return values, index
    index = getattr(frame, "index", None)
    if index is None:
        raise ValueError("SESSION_TIMESTAMP_COLUMN_OR_DATETIME_INDEX_REQUIRED")
    return list(index), index


def apply_session_filter(
    frame: Any,
    asset_class: str,
    *,
    timestamp_column: str | None = None,
) -> Any:
    """Return a copy annotated with session_label; never mutates the caller.

    Financial labels are based on timestamp-aware IANA timezone conversion.
    Synthetic rows receive SYNTHETIC_BYPASS and are not removed.
    """
    normalized = str(asset_class).strip().lower()
    if normalized not in ASSET_CLASSES:
        raise ValueError("ASSET_CLASS_MUST_BE_FINANCIAL_OR_SYNTHETIC")
    output = frame.copy()
    timestamps, _ = _extract_timestamps(output, timestamp_column)
    if normalized == "synthetic":
        warnings.warn(
            "Session filter bypassed for synthetic indices; no time-of-day session gating is applied.",
            UserWarning,
            stacklevel=2,
        )
        labels = ["SYNTHETIC_BYPASS"] * len(timestamps)
    else:
        labels = [classify_session(value, normalized) for value in timestamps]
    try:
        import pandas as pd
        output["session_label"] = pd.Categorical(
            labels,
            categories=sorted(SESSIONS),
            ordered=False,
        )
    except ImportError:
        output["session_label"] = labels
    return output


def is_kill_zone(
    frame: Any,
    session: str = "LONDON",
    buffer_minutes: int = 0,
    *,
    asset_class: str = "financial",
    timestamp_column: str | None = None,
):
    """Return an index-aligned boolean mask; synthetic inputs pass through.

    The buffer expands the selected session's local start/end by the requested
    number of minutes. It is a test parameter, not a hidden strategy trigger.
    """
    normalized_asset = str(asset_class).strip().lower()
    normalized_session = str(session).strip().upper()
    if normalized_asset not in ASSET_CLASSES:
        raise ValueError("ASSET_CLASS_MUST_BE_FINANCIAL_OR_SYNTHETIC")
    if normalized_session not in {"ASIAN", "LONDON", "NY_AM", "NY_PM"}:
        raise ValueError("TARGET_SESSION_INVALID")
    if isinstance(buffer_minutes, bool) or not isinstance(buffer_minutes, int) or buffer_minutes < 0:
        raise ValueError("SESSION_BUFFER_MINUTES_INVALID")
    timestamps, index = _extract_timestamps(frame, timestamp_column)
    if normalized_asset == "synthetic":
        warnings.warn(
            "Session kill-zone mask bypassed for synthetic indices; every row remains eligible.",
            UserWarning,
            stacklevel=2,
        )
        values = [True] * len(timestamps)
    else:
        windows = {
            "ASIAN": (TOKYO, time(9, 0), time(16, 0)),
            "LONDON": (LONDON, time(7, 0), time(10, 0)),
            "NY_AM": (NEW_YORK, time(8, 30), time(11, 0)),
            "NY_PM": (NEW_YORK, time(11, 0), time(19, 0)),
        }
        zone, start, end = windows[normalized_session]
        values = [
            _clock_in_window(
                _aware_datetime(value).astimezone(zone).timetz().replace(tzinfo=None),
                start,
                end,
                buffer_minutes,
            )
            for value in timestamps
        ]
    try:
        import pandas as pd
        return pd.Series(values, index=index, dtype=bool)
    except ImportError:
        return values


Estimator = Literal["rolling", "ewma"]


@dataclass(frozen=True)
class VolatilitySizingConfig:
    """Bounded sizing configuration for research simulations.

    periods_per_year must match the sampling frequency of returns. Examples:
    daily FX returns may use 252; daily synthetic-index returns may use 365;
    intraday returns need the actual number of sampled intervals per year.
    Do not apply 252 mechanically to M1/M15 returns.
    """

    periods_per_year: float
    target_vol_annual: float = 0.10
    window: int = 21
    estimator: Estimator = "rolling"
    ewma_lambda: float = 0.94
    min_multiplier: float = 0.10
    max_multiplier: float = 3.0
    max_risk_pct: float = 0.02

    def __post_init__(self) -> None:
        numeric = (
            self.periods_per_year,
            self.target_vol_annual,
            self.ewma_lambda,
            self.min_multiplier,
            self.max_multiplier,
            self.max_risk_pct,
        )
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)) for x in numeric):
            raise ValueError("VOLATILITY_CONFIG_NUMERIC_INVALID")
        if self.periods_per_year <= 0 or self.target_vol_annual <= 0:
            raise ValueError("VOLATILITY_TARGET_OR_FREQUENCY_INVALID")
        if type(self.window) is not int or self.window < 2:
            raise ValueError("VOLATILITY_WINDOW_MUST_BE_AT_LEAST_2")
        if self.estimator not in {"rolling", "ewma"}:
            raise ValueError("VOLATILITY_ESTIMATOR_INVALID")
        if not 0 < self.ewma_lambda < 1:
            raise ValueError("EWMA_LAMBDA_MUST_BE_IN_(0,1)")
        # These are hard policy bounds, not freely tunable hyperparameters.
        # A caller may tighten the range but cannot force a minimum above base
        # risk or permit a multiplier above 3.0x.
        if not 0.10 <= self.min_multiplier <= 1.0:
            raise ValueError("VOLATILITY_MIN_MULTIPLIER_OUTSIDE_HARD_BOUNDS")
        if not 1.0 <= self.max_multiplier <= 3.0:
            raise ValueError("VOLATILITY_MAX_MULTIPLIER_OUTSIDE_HARD_BOUNDS")
        if self.min_multiplier > self.max_multiplier:
            raise ValueError("VOLATILITY_MULTIPLIER_BOUNDS_INVALID")
        if not 0 < self.max_risk_pct <= 0.02:
            raise ValueError("VOLATILITY_RISK_CAP_MUST_BE_IN_(0,0.02]")


@dataclass(frozen=True)
class VolatilitySizePoint:
    bar_index: int
    estimator: str
    realized_vol_annualized: float | None
    raw_multiplier: float | None
    bounded_multiplier: float | None
    effective_multiplier: float | None
    effective_risk_pct: float | None
    ready: bool
    reason: str

    def audit_record(self, *, trade_id: str, asset_class: str, timestamp_utc: str) -> dict[str, Any]:
        return {
            "event_type": "RESEARCH_VOLATILITY_SIZE_APPLIED",
            "trade_id": trade_id,
            "asset_class": asset_class,
            "timestamp_utc": timestamp_utc,
            "estimator": self.estimator,
            "realized_vol_annualized": self.realized_vol_annualized,
            "raw_multiplier": self.raw_multiplier,
            "bounded_multiplier": self.bounded_multiplier,
            "effective_multiplier": self.effective_multiplier,
            "effective_risk_pct": self.effective_risk_pct,
            "ready": self.ready,
            "reason": self.reason,
            "research_only": True,
            "capital_authority_granted": False,
            "order_submission_permitted": False,
        }


class VolatilitySizer:
    """Lagged rolling/EWMA inverse-volatility sizing, strictly research-only."""

    def __init__(self, config: VolatilitySizingConfig):
        self.config = config

    @staticmethod
    def _validate_returns(returns: Sequence[float]) -> list[float]:
        values: list[float] = []
        for value in returns:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("RETURN_VALUE_INVALID")
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError("RETURN_VALUE_NONFINITE")
            values.append(numeric)
        return values

    def _rolling_volatility(self, history: Sequence[float]) -> float:
        return statistics.stdev(history) * math.sqrt(self.config.periods_per_year)

    def _ewma_volatility(self, history: Sequence[float]) -> float:
        decay = self.config.ewma_lambda
        # Zero-mean EWMA variance forecast; only completed prior returns enter.
        weights = [(1.0 - decay) * decay ** age for age in range(len(history))]
        denominator = sum(weights)
        variance = sum(weight * history[-1 - age] ** 2 for age, weight in enumerate(weights)) / denominator
        return math.sqrt(max(0.0, variance) * self.config.periods_per_year)

    def build_schedule(
        self,
        returns: Sequence[float],
        *,
        base_risk_pct: float = 0.01,
    ) -> tuple[VolatilitySizePoint, ...]:
        """Build one sizing point per bar; point i uses returns strictly before i.

        A warm-up, zero-volatility, or invalid forecast point is not replaced
        with a base-risk fallback. The caller must skip the trade at that index.
        """
        if isinstance(base_risk_pct, bool) or not isinstance(base_risk_pct, (int, float)):
            raise ValueError("BASE_RISK_PCT_INVALID")
        base_risk = float(base_risk_pct)
        if not math.isfinite(base_risk) or not 0 < base_risk <= self.config.max_risk_pct:
            raise ValueError("BASE_RISK_PCT_OUTSIDE_LAYER6_CAP")
        values = self._validate_returns(returns)
        points: list[VolatilitySizePoint] = []
        for index in range(len(values)):
            history = values[:index]
            if len(history) < self.config.window:
                points.append(VolatilitySizePoint(
                    index, self.config.estimator, None, None, None, None, None,
                    False, "VOLATILITY_WARMUP_INCOMPLETE",
                ))
                continue
            relevant = history[-self.config.window:] if self.config.estimator == "rolling" else history
            annualized = (
                self._rolling_volatility(relevant)
                if self.config.estimator == "rolling"
                else self._ewma_volatility(relevant)
            )
            if not math.isfinite(annualized) or annualized <= 0:
                points.append(VolatilitySizePoint(
                    index, self.config.estimator, annualized if math.isfinite(annualized) else None,
                    None, None, None, None, False, "REALIZED_VOLATILITY_ZERO_OR_INVALID",
                ))
                continue
            raw = self.config.target_vol_annual / annualized
            bounded = min(self.config.max_multiplier, max(self.config.min_multiplier, raw))
            requested_risk = base_risk * bounded
            permitted_risk = min(requested_risk, self.config.max_risk_pct)
            effective = permitted_risk / base_risk
            points.append(VolatilitySizePoint(
                index, self.config.estimator, annualized, raw, bounded, effective,
                permitted_risk, True,
                "SIZE_BOUNDED_BY_LAYER6_CAP" if permitted_risk < requested_risk else "SIZE_MULTIPLIER_READY",
            ))
        return tuple(points)

    def point_for_trade(
        self,
        schedule: Sequence[VolatilitySizePoint],
        *,
        bar_index: int,
    ) -> VolatilitySizePoint:
        if isinstance(bar_index, bool) or not isinstance(bar_index, int) or not 0 <= bar_index < len(schedule):
            raise IndexError("VOLATILITY_BAR_INDEX_INVALID")
        point = schedule[bar_index]
        if point.bar_index != bar_index:
            raise ValueError("VOLATILITY_SCHEDULE_INDEX_MISMATCH")
        return point


@dataclass(frozen=True)
class EntryControlDecision:
    allowed: bool
    asset_class: str
    session_label: str
    volatility_point: VolatilitySizePoint | None
    reason: str
    research_only: bool = True
    capital_authority: bool = False
    order_submission_permitted: bool = False


def evaluate_research_entry_controls(
    *,
    signal_timestamp: datetime | str,
    asset_class: str,
    volatility_point: VolatilitySizePoint,
    required_session: str = "LONDON",
) -> EntryControlDecision:
    """Apply conditional session policy plus lagged bounded sizing to a candidate.

    Financial entries must meet the requested validated session hypothesis.
    Synthetic entries bypass all time-of-day filtering. Both asset classes may
    use observed-return volatility scaling, with the same hard risk ceiling.
    """
    normalized = str(asset_class).strip().lower()
    if normalized not in ASSET_CLASSES:
        raise ValueError("ASSET_CLASS_MUST_BE_FINANCIAL_OR_SYNTHETIC")
    if not isinstance(volatility_point, VolatilitySizePoint):
        raise ValueError("VOLATILITY_SIZE_POINT_REQUIRED")
    if not volatility_point.ready or volatility_point.effective_risk_pct is None:
        return EntryControlDecision(
            False, normalized,
            "SYNTHETIC_BYPASS" if normalized == "synthetic" else classify_session(signal_timestamp, normalized),
            volatility_point, "VOLATILITY_SIZER_NOT_READY",
        )
    if normalized == "synthetic":
        return EntryControlDecision(True, normalized, "SYNTHETIC_BYPASS", volatility_point, "SESSION_FILTER_BYPASSED")
    label = classify_session(signal_timestamp, normalized)
    target = str(required_session).strip().upper()
    if target not in {"ASIAN", "LONDON", "NY_AM", "NY_PM"}:
        raise ValueError("TARGET_SESSION_INVALID")
    if label != target:
        return EntryControlDecision(False, normalized, label, volatility_point, "OUTSIDE_REQUIRED_FINANCIAL_SESSION")
    return EntryControlDecision(True, normalized, label, volatility_point, "SESSION_AND_VOLATILITY_CONTROLS_PASS")


def _profit_factor(trades: Sequence[float]) -> tuple[float | None, str]:
    gains = sum(value for value in trades if value > 0)
    losses = -sum(value for value in trades if value < 0)
    if losses == 0:
        return None, "NO_LOSSES_OBSERVED" if gains > 0 else "NO_NONZERO_RETURNS"
    return gains / losses, "DEFINED"


def _moving_block_bootstrap_mean_ci(
    daily_trades: Sequence[Sequence[float]],
    *,
    replications: int,
    block_days: int,
    seed: int,
) -> tuple[float, float, float]:
    """Bootstrap expectancy per trade by resampling contiguous day blocks."""
    import random

    day_count = len(daily_trades)
    if (
        isinstance(block_days, bool)
        or not isinstance(block_days, int)
        or day_count < 2
        or block_days < 1
        or block_days > day_count
    ):
        raise ValueError("SESSION_BOOTSTRAP_DAY_BLOCK_INVALID")
    rng = random.Random(seed)

    def expectancy(day_indexes: Sequence[int]) -> float | None:
        sample = [
            float(value)
            for day_index in day_indexes
            for value in daily_trades[day_index]
        ]
        return statistics.fmean(sample) if sample else None

    observed = expectancy(tuple(range(day_count)))
    if observed is None:
        raise ValueError("SESSION_BOOTSTRAP_HAS_NO_TRADES")
    bootstrapped: list[float] = []
    blocks_needed = math.ceil(day_count / block_days)
    for _ in range(replications):
        indexes: list[int] = []
        for _block in range(blocks_needed):
            start = rng.randrange(day_count)
            indexes.extend((start + offset) % day_count for offset in range(block_days))
        result = expectancy(indexes[:day_count])
        if result is not None and math.isfinite(result):
            bootstrapped.append(result)
    minimum_valid = math.ceil(replications * 0.95)
    if len(bootstrapped) < minimum_valid:
        raise ValueError("SESSION_BOOTSTRAP_VALID_REPLICATIONS_INSUFFICIENT")
    bootstrapped.sort()
    lower_index = max(0, math.floor(0.025 * (len(bootstrapped) - 1)))
    upper_index = min(len(bootstrapped) - 1, math.ceil(0.975 * (len(bootstrapped) - 1)))
    return observed, bootstrapped[lower_index], bootstrapped[upper_index]


def test_c_session_edge(
    *,
    asset_class: str,
    day_ids: Sequence[str],
    daily_trade_r: dict[str, dict[str, Sequence[float]]],
    replications: int = 2000,
    block_days: int = 5,
    minimum_trades: int = 100,
    minimum_days: int = 30,
    minimum_active_days: int = 10,
    seed: int = 369,
) -> dict[str, Any]:
    """Falsify the London-session hypothesis using chronological daily blocks.

    daily_trade_r maps session -> ISO day -> net R values for trades closed on
    that day. Include days with no trades as empty lists. The 95% rule is
    deliberately conservative: London's lower CI must exceed both the
    baseline upper CI and the Asian upper CI. This is not a claim that London
    wins; it is an empirical test result for one registered strategy/data set.
    """
    normalized = str(asset_class).strip().lower()
    if normalized == "synthetic":
        return {
            "verdict": "SKIPPED",
            "reason": "SESSION_EDGE_NOT_APPLICABLE_TO_SYNTHETIC_INDICES",
            "asset_class": normalized,
            "capital_authority": False,
            "live_execution": "BLOCKED",
        }
    if normalized != "financial":
        raise ValueError("ASSET_CLASS_MUST_BE_FINANCIAL_OR_SYNTHETIC")
    valid_days = True
    try:
        parsed_days = [datetime.fromisoformat(str(day)).date() for day in day_ids]
        valid_days = all(parsed.isoformat() == str(day) for parsed, day in zip(parsed_days, day_ids))
    except (TypeError, ValueError):
        valid_days = False
    if (
        not valid_days
        or len(day_ids) < minimum_days
        or list(day_ids) != sorted(set(day_ids))
    ):
        return {
            "verdict": "FAIL",
            "reason": "SESSION_EDGE_DAILY_SAMPLE_INSUFFICIENT_OR_UNORDERED",
            "day_count": len(day_ids),
            "capital_authority": False,
            "live_execution": "BLOCKED",
        }
    for name, value, lower in (
        ("replications", replications, 500),
        ("minimum_trades", minimum_trades, 1),
        ("minimum_days", minimum_days, 2),
        ("minimum_active_days", minimum_active_days, 1),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < lower:
            raise ValueError(f"SESSION_{name.upper()}_INVALID")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("SESSION_BOOTSTRAP_SEED_INVALID")
    if isinstance(block_days, bool) or not isinstance(block_days, int) or not 1 <= block_days <= len(day_ids):
        raise ValueError("SESSION_BOOTSTRAP_DAY_BLOCK_INVALID")

    required = ("LONDON", "NY_AM", "ASIAN", "BASELINE")
    results: dict[str, dict[str, Any]] = {}
    for session in required:
        day_map = daily_trade_r.get(session)
        if not isinstance(day_map, dict):
            return {
                "verdict": "FAIL",
                "reason": f"SESSION_EDGE_DATA_MISSING:{session}",
                "capital_authority": False,
                "live_execution": "BLOCKED",
            }
        if not isinstance(day_map, dict):
            return {
                "verdict": "FAIL",
                "reason": f"SESSION_EDGE_DATA_INVALID:{session}",
                "capital_authority": False,
                "live_execution": "BLOCKED",
            }
        daily = []
        for day in day_ids:
            values = day_map.get(day, ())
            if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
                raise ValueError(f"SESSION_EDGE_DAILY_VALUES_INVALID:{session}:{day}")
            converted = []
            for value in values:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"SESSION_EDGE_RETURN_INVALID:{session}:{day}")
                numeric = float(value)
                if not math.isfinite(numeric):
                    raise ValueError(f"SESSION_EDGE_NONFINITE_R:{session}:{day}")
                converted.append(numeric)
            daily.append(converted)
        trades = [value for day in daily for value in day]
        active_day_count = sum(bool(day) for day in daily)
        if len(trades) < minimum_trades or active_day_count < minimum_active_days:
            sample_reason = (
                "TRADE_COUNT_INSUFFICIENT"
                if len(trades) < minimum_trades
                else "ACTIVE_DAY_COUNT_INSUFFICIENT"
            )
            return {
                "verdict": "FAIL",
                "reason": f"SESSION_EDGE_{sample_reason}:{session}",
                "trade_count": len(trades),
                "active_day_count": active_day_count,
                "minimum_trades": minimum_trades,
                "minimum_active_days": minimum_active_days,
                "capital_authority": False,
                "live_execution": "BLOCKED",
            }
        observed, lower, upper = _moving_block_bootstrap_mean_ci(
            daily,
            replications=replications,
            block_days=block_days,
            seed=seed + required.index(session),
        )
        profit_factor, profit_factor_status = _profit_factor(trades)
        results[session] = {
            "trade_count": len(trades),
            "active_day_count": active_day_count,
            "expectancy_r": observed,
            "expectancy_ci95_lower": lower,
            "expectancy_ci95_upper": upper,
            "profit_factor": profit_factor,
            "profit_factor_status": profit_factor_status,
        }

    london = results["LONDON"]
    baseline = results["BASELINE"]
    asian = results["ASIAN"]
    passed = (
        london["expectancy_ci95_lower"] > baseline["expectancy_ci95_upper"]
        and london["expectancy_ci95_lower"] > asian["expectancy_ci95_upper"]
        and london["expectancy_ci95_lower"] > 0.0
    )
    return {
        "verdict": "PASS" if passed else "FAIL",
        "reason": "LONDON_95_PERCENT_CI_EXCEEDS_BASELINE_AND_ASIAN"
        if passed else "LONDON_EDGE_NOT_ESTABLISHED",
        "asset_class": normalized,
        "sessions": results,
        "london_expectancy_ci95_lower": london["expectancy_ci95_lower"],
        "non_overlapping_95_percent_ci": passed,
        "block_bootstrap": {
            "replications": replications,
            "block_days": block_days,
            "day_count": len(day_ids),
            "seed": seed,
        },
        "capital_authority": False,
        "order_submission_permitted": False,
        "live_execution": "BLOCKED",
    }


def select_volatility_estimator_from_dsr(
    *,
    rolling_dsr: float | None,
    ewma_dsr: float | None,
    rolling_trade_count: int,
    ewma_trade_count: int,
    configurations_tested: int,
    minimum_trades: int = 100,
    relative_improvement_required: float = 0.02,
) -> dict[str, Any]:
    """Choose only from externally calculated DSR values; never calculate a fake DSR.

    The current repository does not expose a canonical Deflated Sharpe Ratio
    calculator. Callers must pass values from the registered research metric
    implementation with the full configuration/trial count. Incomplete inputs
    return NOT_RUN rather than selecting an estimator.
    """
    values = (rolling_dsr, ewma_dsr)
    if any(value is None for value in values):
        return {"status": "NOT_RUN", "reason": "CANONICAL_DSR_VALUES_UNAVAILABLE", "selected_estimator": None}
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0
        for value in values
    ):
        raise ValueError("DSR_VALUE_INVALID")
    if configurations_tested < 2:
        raise ValueError("DSR_CONFIGURATION_COUNT_MUST_INCLUDE_BOTH_ESTIMATORS")
    if min(rolling_trade_count, ewma_trade_count) < minimum_trades:
        return {"status": "NOT_RUN", "reason": "ESTIMATOR_TRADE_COUNT_INSUFFICIENT", "selected_estimator": None}
    rolling, ewma = float(rolling_dsr), float(ewma_dsr)
    improvement = (ewma - rolling) / max(abs(rolling), 1e-12)
    selected = "ewma" if improvement > relative_improvement_required else "rolling"
    return {
        "status": "RESEARCH_SELECTION_ONLY",
        "selected_estimator": selected,
        "rolling_dsr": rolling,
        "ewma_dsr": ewma,
        "ewma_relative_dsr_improvement": improvement,
        "relative_improvement_required": relative_improvement_required,
        "configurations_tested": configurations_tested,
        "rolling_trade_count": rolling_trade_count,
        "ewma_trade_count": ewma_trade_count,
        "capital_authority": False,
        "live_execution": "BLOCKED",
    }


@dataclass(frozen=True)
class ResearchCandidateSizing:
    candidate: Any
    decision: EntryControlDecision
    effective_risk_pct: float | None
    effective_multiplier: float | None

    def audit_record(self, *, candidate_id: str) -> dict[str, Any]:
        point = self.decision.volatility_point
        return {
            "event_type": "RESEARCH_CANDIDATE_SIZING_DECISION",
            "candidate_id": candidate_id,
            "allowed": self.decision.allowed,
            "asset_class": self.decision.asset_class,
            "session_label": self.decision.session_label,
            "reason": self.decision.reason,
            "effective_risk_pct": self.effective_risk_pct,
            "effective_multiplier": self.effective_multiplier,
            "volatility_estimator": point.estimator if point else None,
            "realized_vol_annualized": point.realized_vol_annualized if point else None,
            "capital_authority_granted": False,
            "order_submission_permitted": False,
            "live_execution": "BLOCKED",
        }


def prepare_candidate_for_research_simulation(
    candidate: Any,
    *,
    signal_timestamp: datetime | str,
    asset_class: str,
    volatility_schedule: Sequence[VolatilitySizePoint],
    entry_bar_index: int,
    required_session: str = "LONDON",
) -> ResearchCandidateSizing:
    """Attach conditional session/volatility gates to an existing MSNR candidate.

    This is a research pre-simulation adapter, not an execution engine. It
    consumes the repository's existing candidate object rather than creating a
    duplicate MSNR detector or CapitalPlaneExecutor. The trade's entry-bar
    sizing point must already be lagged by VolatilitySizer.build_schedule().
    """
    if candidate is None:
        raise ValueError("RESEARCH_CANDIDATE_REQUIRED")
    if getattr(candidate, "capital_authority", False) is not False:
        raise ValueError("RESEARCH_CANDIDATE_CAPITAL_AUTHORITY_FORBIDDEN")
    if getattr(candidate, "order_submission_permitted", False) is not False:
        raise ValueError("RESEARCH_CANDIDATE_ORDER_SUBMISSION_FORBIDDEN")
    research_only = getattr(candidate, "research_only", None)
    if research_only is not True:
        payload_builder = getattr(candidate, "as_payload", None)
        payload = payload_builder() if callable(payload_builder) else None
        research_only = payload.get("research_only") if isinstance(payload, dict) else None
    if research_only is not True:
        raise ValueError("CANDIDATE_MUST_DECLARE_RESEARCH_ONLY")
    if isinstance(entry_bar_index, bool) or not isinstance(entry_bar_index, int):
        raise ValueError("ENTRY_BAR_INDEX_INVALID")
    if not 0 <= entry_bar_index < len(volatility_schedule):
        raise IndexError("ENTRY_BAR_INDEX_OUT_OF_RANGE")
    candidate_timestamp = (
        getattr(candidate, "signal_close_timestamp_utc", None)
        or getattr(candidate, "signal_timestamp_utc", None)
    )
    if not isinstance(candidate_timestamp, str) or not candidate_timestamp.strip():
        raise ValueError("CANDIDATE_SIGNAL_TIMESTAMP_REQUIRED")
    supplied_stamp = _aware_datetime(signal_timestamp)
    candidate_stamp = _aware_datetime(candidate_timestamp)
    if supplied_stamp.astimezone(ZoneInfo("UTC")) != candidate_stamp.astimezone(ZoneInfo("UTC")):
        raise ValueError("CANDIDATE_SIGNAL_TIMESTAMP_MISMATCH")
    point = volatility_schedule[entry_bar_index]
    controls = evaluate_research_entry_controls(
        signal_timestamp=candidate_timestamp,
        asset_class=asset_class,
        volatility_point=point,
        required_session=required_session,
    )
    return ResearchCandidateSizing(
        candidate=candidate,
        decision=controls,
        effective_risk_pct=point.effective_risk_pct if controls.allowed else None,
        effective_multiplier=point.effective_multiplier if controls.allowed else None,
    )
