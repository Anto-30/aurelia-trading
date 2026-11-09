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
from typing import Any, Iterable, Literal, Sequence
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
        if not 0 < self.min_multiplier <= self.max_multiplier:
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
