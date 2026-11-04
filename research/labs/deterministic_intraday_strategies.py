"""Deterministic intraday setup detectors. Research-only; never routes orders."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as wall_time, timedelta, timezone
from math import isfinite, log, sqrt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from statistics import fmean, median
from typing import Sequence

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False

STRATEGY_MANIFEST = (
    {"strategy_id": "MSNR_LIQUIDITY_SWEEP", "version": "1.0.0",
     "qualification_status": "RESEARCH_ONLY_UNQUALIFIED",
     "data_requirements": ("closed_ohlc_bars", "instrument_tick_size")},
    {"strategy_id": "VWAP_PULLBACK_RECLAIM", "version": "1.0.0",
     "qualification_status": "RESEARCH_ONLY_UNQUALIFIED",
     "data_requirements": ("closed_ohlc_bars", "verified_session_volume", "session_id")},
    {"strategy_id": "OPENING_RANGE_BREAKOUT", "version": "1.0.0",
     "qualification_status": "RESEARCH_ONLY_UNQUALIFIED",
     "data_requirements": ("closed_ohlc_bars", "session_id", "instrument_tick_size")},
)


def _utc(value: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("BAR_TIMESTAMP_INVALID") from exc
    if stamp.tzinfo is None:
        raise ValueError("BAR_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return stamp.astimezone(timezone.utc)


@dataclass(frozen=True)
class StrategyBar:
    timestamp_utc: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        _utc(self.timestamp_utc)
        prices = (self.open, self.high, self.low, self.close)
        if not all(isfinite(float(x)) and float(x) > 0 for x in prices):
            raise ValueError("BAR_PRICES_MUST_BE_FINITE_AND_POSITIVE")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("BAR_HIGH_INCONSISTENT")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("BAR_LOW_INCONSISTENT")
        if self.volume is not None and (
            not isfinite(float(self.volume)) or float(self.volume) < 0
        ):
            raise ValueError("BAR_VOLUME_INVALID")


def _validate_bars(bars: Sequence[StrategyBar]) -> None:
    previous = None
    for bar in bars:
        if not isinstance(bar, StrategyBar):
            raise ValueError("STRATEGY_BAR_TYPE_INVALID")
        stamp = _utc(bar.timestamp_utc)
        if previous is not None and stamp <= previous:
            raise ValueError("BAR_TIMESTAMPS_MUST_BE_STRICTLY_INCREASING")
        previous = stamp


@dataclass(frozen=True)
class RegimeConfig:
    lookback_bars: int = 20
    trend_efficiency_min: float = 0.35
    high_volatility_pct: float = 0.75
    version: str = "regime-v1"

    def __post_init__(self) -> None:
        if self.lookback_bars < 2:
            raise ValueError("REGIME_LOOKBACK_MUST_BE_AT_LEAST_2")
        if not 0 <= self.trend_efficiency_min <= 1:
            raise ValueError("REGIME_EFFICIENCY_THRESHOLD_INVALID")
        if not isfinite(self.high_volatility_pct) or self.high_volatility_pct <= 0:
            raise ValueError("REGIME_VOLATILITY_THRESHOLD_INVALID")


@dataclass(frozen=True)
class RegimeSnapshot:
    state: str
    directional_efficiency: float
    realized_volatility_pct: float
    lookback_bars: int
    version: str


def classify_regime(
    bars: Sequence[StrategyBar], *, config: RegimeConfig = RegimeConfig()
) -> RegimeSnapshot | None:
    """Classify the supplied closed-bar prefix; insufficient history returns None."""
    _validate_bars(bars)
    n = config.lookback_bars
    if len(bars) < n + 1:
        return None
    closes = [float(b.close) for b in bars[-n - 1:]]
    returns = [log(closes[j] / closes[j - 1]) for j in range(1, len(closes))]
    path = sum(abs(closes[j] - closes[j - 1]) for j in range(1, len(closes)))
    efficiency = abs(closes[-1] - closes[0]) / path if path else 0.0
    avg = fmean(returns)
    vol = sqrt(sum((r - avg) ** 2 for r in returns) / max(1, len(returns) - 1)) * 100.0
    direction = "TRENDING" if efficiency >= config.trend_efficiency_min else "RANGING"
    volatility = "HIGH_VOL" if vol >= config.high_volatility_pct else "LOW_VOL"
    return RegimeSnapshot(f"{direction}_{volatility}", efficiency, vol, n, config.version)


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_id: str
    version: str
    direction: str
    signal_timestamp_utc: str
    entry_timing: str
    stop_reference_price: float
    target_reference_price: float | None
    target_mode: str
    regime: str
    evidence_codes: tuple[str, ...]
    capital_authority: bool = False
    order_submission_permitted: bool = False

    def as_payload(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id, "version": self.version,
            "direction": self.direction, "signal_timestamp_utc": self.signal_timestamp_utc,
            "entry_timing": self.entry_timing, "stop_reference_price": self.stop_reference_price,
            "target_reference_price": self.target_reference_price, "target_mode": self.target_mode,
            "regime": self.regime, "evidence_codes": list(self.evidence_codes),
            "research_only": True, "capital_authority": False,
            "order_submission_permitted": False,
        }


@dataclass(frozen=True)
class MSNRConfig:
    lookback_bars: int = 20
    tick_size: float | None = None
    min_sweep_ticks: float = 1.0
    stop_buffer_ticks: float = 1.0
    max_reclaim_bars: int = 3
    require_volume_pop: bool = False
    volume_pop_multiplier: float = 1.5
    allowed_regimes: tuple[str, ...] = ("TRENDING_LOW_VOL", "RANGING_LOW_VOL")
    version: str = "msnr-v1"

    def __post_init__(self) -> None:
        if self.lookback_bars < 3 or self.max_reclaim_bars < 1:
            raise ValueError("MSNR_LOOKBACK_OR_RECLAIM_INVALID")
        if self.tick_size is not None and (not isfinite(self.tick_size) or self.tick_size <= 0):
            raise ValueError("MSNR_TICK_SIZE_INVALID")
        if self.min_sweep_ticks <= 0 or self.stop_buffer_ticks < 0:
            raise ValueError("MSNR_TICK_PARAMETERS_INVALID")
        if self.require_volume_pop and self.volume_pop_multiplier <= 0:
            raise ValueError("MSNR_VOLUME_MULTIPLIER_INVALID")


def detect_msnr_liquidity_sweep(
    bars: Sequence[StrategyBar], *, config: MSNRConfig,
    regime_config: RegimeConfig = RegimeConfig(),
    volume_source_verified: bool = False,
) -> StrategyCandidate | None:
    """Sweep -> close back inside reference range -> local structure break.

    Delta/DOM/footprint divergence is not inferred from OHLC. Optional volume-pop
    gating requires caller-verified volume provenance.
    """
    _validate_bars(bars)
    if config.tick_size is None:
        raise ValueError("MSNR_TICK_SIZE_REQUIRED")
    i = len(bars) - 1
    regime = classify_regime(bars, config=regime_config)
    if regime is None or regime.state not in config.allowed_regimes:
        return None
    first = max(config.lookback_bars, i - config.max_reclaim_bars + 1)
    for sweep_i in range(i, first - 1, -1):
        prior = bars[sweep_i - config.lookback_bars:sweep_i]
        sweep = bars[sweep_i]
        ref_low, ref_high = min(b.low for b in prior), max(b.high for b in prior)
        swept_low = sweep.low <= ref_low - config.min_sweep_ticks * config.tick_size
        swept_high = sweep.high >= ref_high + config.min_sweep_ticks * config.tick_size
        if swept_low == swept_high:
            continue  # neither boundary swept, or ambiguous two-sided sweep
        if config.require_volume_pop:
            volumes = [b.volume for b in prior]
            if not volume_source_verified or any(v is None or v <= 0 for v in volumes):
                continue
            if sweep.volume is None or sweep.volume <= median(volumes) * config.volume_pop_multiplier:
                continue
        side = "LONG" if swept_low else "SHORT"
        confirmations = []
        for k in range(sweep_i, i + 1):
            current, previous = bars[k], bars[k - 1]
            if side == "LONG":
                valid = current.close > ref_low and current.close > previous.high
            else:
                valid = current.close < ref_high and current.close < previous.low
            if valid:
                confirmations.append(k)
                break
        if not confirmations or confirmations[0] != i:
            continue
        if side == "LONG":
            target = ref_high
            if target <= bars[i].close:
                continue
            stop = sweep.low - config.stop_buffer_ticks * config.tick_size
            evidence = ("LIQUIDITY_LOW_SWEPT", "RANGE_RECLAIMED", "STRUCTURE_BREAK_CONFIRMED")
        else:
            target = ref_low
            if target >= bars[i].close:
                continue
            stop = sweep.high + config.stop_buffer_ticks * config.tick_size
            evidence = ("LIQUIDITY_HIGH_SWEPT", "RANGE_RECLAIMED", "STRUCTURE_BREAK_CONFIRMED")
        evidence += ("VERIFIED_VOLUME_POP",) if config.require_volume_pop else ("ORDERFLOW_CONFIRMATION_UNAVAILABLE",)
        return StrategyCandidate(
            "MSNR_LIQUIDITY_SWEEP", config.version, side, bars[i].timestamp_utc,
            "NEXT_BAR_OPEN_AFTER_SIGNAL", stop, target, "OPPOSING_REFERENCE_RANGE_EDGE",
            regime.state, evidence,
        )
    return None



@dataclass(frozen=True)
class CycleMarkerConfig:
    """Explicit optional 0.618 marker policy; disabled for 24/7 synthetics by default."""

    enabled: bool = False
    base_marker_time: str = "08:49:55"
    timezone_name: str = "America/New_York"
    normalization: str | None = None
    est_offset_minutes: int | None = None
    entry_window_seconds: int = 45
    hard_cutoff_seconds: int = 90
    dst_transition_policy: str | None = None

    def __post_init__(self) -> None:
        if self.entry_window_seconds < 0 or self.hard_cutoff_seconds < self.entry_window_seconds:
            raise ValueError("CYCLE_MARKER_WINDOW_INVALID")
        try:
            hour, minute, second = (int(part) for part in self.base_marker_time.split(":"))
            wall_time(hour, minute, second)
        except (TypeError, ValueError):
            raise ValueError("CYCLE_MARKER_TIME_INVALID") from None
        if self.normalization not in {None, "clock_fixed", "solar_fixed"}:
            raise ValueError("CYCLE_NORMALIZATION_INVALID")
        if self.dst_transition_policy not in {
            None, "apply_local_timezone", "skip_transition_days"
        }:
            raise ValueError("CYCLE_DST_TRANSITION_POLICY_INVALID")
        if self.est_offset_minutes is not None and (
            isinstance(self.est_offset_minutes, bool)
            or not isinstance(self.est_offset_minutes, int)
            or not -180 <= self.est_offset_minutes <= 180
        ):
            raise ValueError("CYCLE_EST_OFFSET_INVALID")


@dataclass(frozen=True)
class MSNRConfirmationConfig:
    """Proposed MSNR-1..5 thresholds; research-only until separately qualified."""

    timeframe: str
    lookback_bars: int
    tick_size: float
    atr_period: int = 14
    min_sweep_atr: float = 1.0
    rejection_close_fraction: float = 0.60
    stop_buffer_ticks: float = 0.0
    require_volume_confirmation: bool = False
    volume_sma_period: int = 20
    volume_multiplier: float = 1.5
    require_htf_alignment: bool = False
    htf_ema_period: int = 50
    htf_slope_lookback: int = 5
    temporal_required: bool = False
    allowed_regimes: tuple[str, ...] = ("TRENDING_LOW_VOL", "RANGING_LOW_VOL")
    version: str = "msnr-confirmation-hypothesis-v1"

    def __post_init__(self) -> None:
        if self.timeframe not in {"1m", "15m"}:
            raise ValueError("MSNR_TIMEFRAME_INVALID")
        lower, upper = (20, 50) if self.timeframe == "1m" else (10, 20)
        if not lower <= self.lookback_bars <= upper:
            raise ValueError("MSNR_LOOKBACK_OUT_OF_POLICY_RANGE")
        if (
            isinstance(self.tick_size, bool)
            or not isinstance(self.tick_size, (int, float))
            or not isfinite(float(self.tick_size))
            or self.tick_size <= 0
        ):
            raise ValueError("MSNR_TICK_SIZE_INVALID")
        if isinstance(self.atr_period, bool) or self.atr_period < 2:
            raise ValueError("MSNR_ATR_PERIOD_INVALID")
        if not isfinite(self.min_sweep_atr) or self.min_sweep_atr <= 0:
            raise ValueError("MSNR_MIN_SWEEP_ATR_INVALID")
        if not 0.5 <= self.rejection_close_fraction <= 1.0:
            raise ValueError("MSNR_REJECTION_FRACTION_INVALID")
        if not isfinite(self.stop_buffer_ticks) or self.stop_buffer_ticks < 0:
            raise ValueError("MSNR_STOP_BUFFER_INVALID")
        if isinstance(self.volume_sma_period, bool) or self.volume_sma_period < 2:
            raise ValueError("MSNR_VOLUME_PERIOD_INVALID")
        if not isfinite(self.volume_multiplier) or self.volume_multiplier <= 0:
            raise ValueError("MSNR_VOLUME_MULTIPLIER_INVALID")
        if self.htf_ema_period < 2 or self.htf_slope_lookback < 1:
            raise ValueError("MSNR_HTF_PERIOD_INVALID")
        if not self.allowed_regimes:
            raise ValueError("MSNR_ALLOWED_REGIMES_EMPTY")


@dataclass(frozen=True)
class MSNRConfirmationVerdict:
    signal_valid: bool
    reason: str
    direction: str | None = None
    signal_timestamp_utc: str | None = None
    stop_reference_price: float | None = None
    target_reference_price: float | None = None
    atr: float | None = None
    rejection_close_fraction: float | None = None
    regime: str | None = None
    evidence_codes: tuple[str, ...] = ()
    capital_authority: bool = False
    order_submission_permitted: bool = False


def _msnr_reject(
    reason: str,
    *,
    direction: str | None = None,
    signal_timestamp_utc: str | None = None,
    atr: float | None = None,
    rejection_close_fraction: float | None = None,
    regime: str | None = None,
    evidence_codes: Sequence[str] = (),
) -> MSNRConfirmationVerdict:
    return MSNRConfirmationVerdict(
        False, reason, direction, signal_timestamp_utc, None, None,
        atr, rejection_close_fraction, regime, tuple(evidence_codes), False, False,
    )


def _is_dst_transition_day(day: date, zone: ZoneInfo) -> bool:
    def midday(value: date):
        return datetime.combine(value, wall_time(12, 0), tzinfo=zone).utcoffset()
    return (
        midday(day - timedelta(days=1)) != midday(day)
        or midday(day) != midday(day + timedelta(days=1))
    )


def _cycle_marker_check(
    signal_time: datetime,
    config: CycleMarkerConfig | None,
) -> tuple[bool, str, str | None]:
    if config is None or not config.enabled:
        return True, "TEMPORAL_FILTER_DISABLED", None
    if config.normalization is None:
        return False, "CYCLE_DST_NORMALIZATION_UNSPECIFIED", None
    if config.dst_transition_policy is None:
        return False, "CYCLE_DST_TRANSITION_POLICY_UNSPECIFIED", None
    if config.normalization == "solar_fixed" and config.est_offset_minutes is None:
        return False, "CYCLE_EST_OFFSET_UNSPECIFIED", None
    if not isinstance(signal_time, datetime) or signal_time.tzinfo is None:
        return False, "SIGNAL_TIME_MUST_BE_TIMEZONE_AWARE", None
    try:
        zone = ZoneInfo(config.timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return False, "CYCLE_TIMEZONE_INVALID", None

    local_signal = signal_time.astimezone(zone)
    transition_day = _is_dst_transition_day(local_signal.date(), zone)
    if transition_day and config.dst_transition_policy == "skip_transition_days":
        return False, "TEMPORAL_DST_TRANSITION_DAY_SKIPPED", None

    try:
        hour, minute, second = (int(part) for part in config.base_marker_time.split(":"))
        marker_clock = wall_time(hour, minute, second)
    except (TypeError, ValueError):
        return False, "CYCLE_MARKER_TIME_INVALID", None

    shift_minutes = 0
    if config.normalization == "solar_fixed":
        offset = local_signal.utcoffset()
        if offset is None:
            return False, "CYCLE_LOCAL_UTC_OFFSET_UNKNOWN", None
        if offset.total_seconds() == -5 * 3600:
            shift_minutes = int(config.est_offset_minutes or 0)
        elif offset.total_seconds() != -4 * 3600:
            return False, "CYCLE_SOLAR_OFFSET_UNSUPPORTED", None

    marker_local = datetime.combine(local_signal.date(), marker_clock, tzinfo=zone)
    marker_local += timedelta(minutes=shift_minutes)
    marker_utc = marker_local.astimezone(timezone.utc)
    signal_utc = signal_time.astimezone(timezone.utc)
    delta_seconds = (signal_utc - marker_utc).total_seconds()

    if abs(delta_seconds) <= config.entry_window_seconds:
        return True, "CYCLE_MARKER_WINDOW_CONFIRMED", marker_utc.isoformat()
    if delta_seconds > config.hard_cutoff_seconds:
        return False, "TEMPORAL_HARD_CUTOFF_EXCEEDED", marker_utc.isoformat()
    if delta_seconds < -config.entry_window_seconds:
        return False, "TEMPORAL_BEFORE_ENTRY_WINDOW", marker_utc.isoformat()
    return False, "TEMPORAL_OUTSIDE_ENTRY_WINDOW", marker_utc.isoformat()


def _ema_values(values: Sequence[float], period: int) -> list[float]:
    alpha = 2.0 / (period + 1.0)
    result = [float(values[0])]
    for value in values[1:]:
        result.append(alpha * float(value) + (1.0 - alpha) * result[-1])
    return result


def evaluate_msnr_entry_confirmation(
    bars: Sequence[StrategyBar],
    *,
    config: MSNRConfirmationConfig,
    regime_config: RegimeConfig = RegimeConfig(),
    higher_timeframe_bars: Sequence[StrategyBar] | None = None,
    volume_source_verified: bool = False,
    signal_time: datetime | None = None,
    cycle_config: CycleMarkerConfig | None = None,
) -> MSNRConfirmationVerdict:
    """Evaluate Layer-9 MSNR rules on closed bars only; never grants capital authority.

    For Deriv synthetic indices, true traded volume is not present in the public
    ticks_history payload. Volume confirmation therefore remains off by default
    and, when requested, requires independently verified volume provenance.
    """

    try:
        _validate_bars(bars)
    except ValueError as exc:
        return _msnr_reject(str(exc))
    if not bars:
        return _msnr_reject("MSNR_BARS_EMPTY")

    current = bars[-1]
    current_stamp = _utc(current.timestamp_utc)
    observed_signal_time = signal_time
    if observed_signal_time is None:
        try:
            observed_signal_time = datetime.fromisoformat(
                current.timestamp_utc.replace("Z", "+00:00")
            )
        except (TypeError, ValueError):
            return _msnr_reject("SIGNAL_TIME_INVALID")
    if not isinstance(observed_signal_time, datetime) or observed_signal_time.tzinfo is None:
        return _msnr_reject("SIGNAL_TIME_MUST_BE_TIMEZONE_AWARE")
    if observed_signal_time.astimezone(timezone.utc) < current_stamp:
        return _msnr_reject("SIGNAL_TIME_PRECEDES_SIGNAL_BAR")
    signal_stamp = observed_signal_time.astimezone(timezone.utc).isoformat()

    required_history = max(
        config.lookback_bars + 1,
        config.atr_period + 1,
        config.volume_sma_period + 1 if config.require_volume_confirmation else 0,
    )
    if len(bars) < required_history:
        return _msnr_reject(
            "MSNR_INSUFFICIENT_HISTORY",
            signal_timestamp_utc=signal_stamp,
        )

    index = len(bars) - 1
    prior = bars[index - config.lookback_bars:index]
    reference_low = min(bar.low for bar in prior)
    reference_high = max(bar.high for bar in prior)

    true_ranges = [
        _true_range(bars[k], bars[k - 1].close)
        for k in range(index - config.atr_period, index)
    ]
    atr = fmean(true_ranges)
    if not isfinite(atr) or atr <= 0:
        return _msnr_reject(
            "MSNR_ATR_INVALID", signal_timestamp_utc=signal_stamp
        )

    sweep_distance = config.min_sweep_atr * atr
    swept_low = current.low <= reference_low - sweep_distance
    swept_high = current.high >= reference_high + sweep_distance
    if swept_low and swept_high:
        return _msnr_reject(
            "AMBIGUOUS_BIDIRECTIONAL_SWEEP",
            signal_timestamp_utc=signal_stamp,
            atr=atr,
        )
    if not swept_low and not swept_high:
        return _msnr_reject(
            "NO_ATR_SIZED_LIQUIDITY_SWEEP",
            signal_timestamp_utc=signal_stamp,
            atr=atr,
        )

    direction = "LONG" if swept_low else "SHORT"
    candle_range = current.high - current.low
    if candle_range <= 0:
        return _msnr_reject(
            "REJECTION_CANDLE_ZERO_RANGE",
            direction=direction,
            signal_timestamp_utc=signal_stamp,
            atr=atr,
        )
    inward_fraction = (
        (current.close - current.low) / candle_range
        if direction == "LONG"
        else (current.high - current.close) / candle_range
    )
    close_inside = (
        reference_low < current.close <= reference_high
        if direction == "LONG"
        else reference_low <= current.close < reference_high
    )
    if not close_inside:
        return _msnr_reject(
            "REJECTION_CLOSE_NOT_BACK_INSIDE_RANGE",
            direction=direction,
            signal_timestamp_utc=signal_stamp,
            atr=atr,
            rejection_close_fraction=inward_fraction,
        )
    if inward_fraction < config.rejection_close_fraction:
        return _msnr_reject(
            "REJECTION_BODY_FRACTION_NOT_MET",
            direction=direction,
            signal_timestamp_utc=signal_stamp,
            atr=atr,
            rejection_close_fraction=inward_fraction,
        )

    regime = classify_regime(bars[:-1], config=regime_config)
    if regime is None:
        return _msnr_reject(
            "VOLATILITY_REGIME_HISTORY_INSUFFICIENT",
            direction=direction,
            signal_timestamp_utc=signal_stamp,
            atr=atr,
            rejection_close_fraction=inward_fraction,
        )
    if regime.state not in config.allowed_regimes:
        return _msnr_reject(
            "VOLATILITY_REGIME_NOT_ALLOWED",
            direction=direction,
            signal_timestamp_utc=signal_stamp,
            atr=atr,
            rejection_close_fraction=inward_fraction,
            regime=regime.state,
        )

    evidence = [
        "PRIOR_SWING_REFERENCE_DEFINED",
        "ATR_SWEEP_CONFIRMED",
        "REJECTION_CLOSE_INWARD_CONFIRMED",
        "PRIOR_RANGE_RECLAIM_CONFIRMED",
        "VOLATILITY_REGIME_PASSED",
    ]

    if config.require_volume_confirmation:
        if not volume_source_verified:
            return _msnr_reject(
                "VOLUME_SOURCE_UNVERIFIED",
                direction=direction,
                signal_timestamp_utc=signal_stamp,
                atr=atr,
                rejection_close_fraction=inward_fraction,
                regime=regime.state,
                evidence_codes=evidence,
            )
        volumes = [bar.volume for bar in prior[-config.volume_sma_period:]]
        if current.volume is None or any(value is None for value in volumes):
            return _msnr_reject(
                "VERIFIED_VOLUME_DATA_MISSING",
                direction=direction,
                signal_timestamp_utc=signal_stamp,
                atr=atr,
                rejection_close_fraction=inward_fraction,
                regime=regime.state,
                evidence_codes=evidence,
            )
        volume_baseline = fmean(float(value) for value in volumes)
        if volume_baseline <= 0 or float(current.volume) < config.volume_multiplier * volume_baseline:
            return _msnr_reject(
                "VOLUME_POP_NOT_CONFIRMED",
                direction=direction,
                signal_timestamp_utc=signal_stamp,
                atr=atr,
                rejection_close_fraction=inward_fraction,
                regime=regime.state,
                evidence_codes=evidence,
            )
        evidence.append("VERIFIED_VOLUME_SMA_POP")
    else:
        evidence.append("VOLUME_FILTER_NOT_APPLICABLE_PUBLIC_TICKS_HAVE_NO_TRADE_VOLUME")

    if config.require_htf_alignment:
        if higher_timeframe_bars is None or len(higher_timeframe_bars) < (
            config.htf_ema_period + config.htf_slope_lookback
        ):
            return _msnr_reject(
                "HTF_DATA_UNAVAILABLE",
                direction=direction,
                signal_timestamp_utc=signal_stamp,
                atr=atr,
                rejection_close_fraction=inward_fraction,
                regime=regime.state,
                evidence_codes=evidence,
            )
        try:
            _validate_bars(higher_timeframe_bars)
        except ValueError as exc:
            return _msnr_reject(
                str(exc),
                direction=direction,
                signal_timestamp_utc=signal_stamp,
                atr=atr,
                rejection_close_fraction=inward_fraction,
                regime=regime.state,
                evidence_codes=evidence,
            )
        if _utc(higher_timeframe_bars[-1].timestamp_utc) >= current_stamp:
            return _msnr_reject(
                "HTF_DATA_NOT_CLOSED_BEFORE_SIGNAL",
                direction=direction,
                signal_timestamp_utc=signal_stamp,
                atr=atr,
                rejection_close_fraction=inward_fraction,
                regime=regime.state,
                evidence_codes=evidence,
            )
        ema_values = _ema_values(
            [bar.close for bar in higher_timeframe_bars],
            config.htf_ema_period,
        )
        slope = ema_values[-1] - ema_values[-1 - config.htf_slope_lookback]
        aligned = slope > 0 if direction == "LONG" else slope < 0
        if not aligned:
            return _msnr_reject(
                "HTF_STRUCTURE_OPPOSED" if slope != 0 else "HTF_STRUCTURE_FLAT",
                direction=direction,
                signal_timestamp_utc=signal_stamp,
                atr=atr,
                rejection_close_fraction=inward_fraction,
                regime=regime.state,
                evidence_codes=evidence,
            )
        evidence.append("HTF_EMA50_SLOPE_ALIGNED")

    if config.temporal_required:
        temporal_pass, temporal_reason, marker_utc = _cycle_marker_check(
            observed_signal_time, cycle_config
        )
        if not temporal_pass:
            return _msnr_reject(
                temporal_reason,
                direction=direction,
                signal_timestamp_utc=signal_stamp,
                atr=atr,
                rejection_close_fraction=inward_fraction,
                regime=regime.state,
                evidence_codes=evidence,
            )
        evidence.append("CYCLE_MARKER_WINDOW_CONFIRMED")
    elif cycle_config is not None and cycle_config.enabled:
        temporal_pass, temporal_reason, marker_utc = _cycle_marker_check(
            observed_signal_time, cycle_config
        )
        if not temporal_pass:
            return _msnr_reject(
                temporal_reason,
                direction=direction,
                signal_timestamp_utc=signal_stamp,
                atr=atr,
                rejection_close_fraction=inward_fraction,
                regime=regime.state,
                evidence_codes=evidence,
            )
        evidence.append("CYCLE_MARKER_WINDOW_CONFIRMED")

    stop = (
        current.low - config.stop_buffer_ticks * config.tick_size
        if direction == "LONG"
        else current.high + config.stop_buffer_ticks * config.tick_size
    )
    target = reference_high if direction == "LONG" else reference_low
    if (direction == "LONG" and target <= current.close) or (
        direction == "SHORT" and target >= current.close
    ):
        return _msnr_reject(
            "STRUCTURAL_TARGET_NOT_REWARDING",
            direction=direction,
            signal_timestamp_utc=signal_stamp,
            atr=atr,
            rejection_close_fraction=inward_fraction,
            regime=regime.state,
            evidence_codes=evidence,
        )
    evidence.append("STRUCTURAL_TARGET_REFERENCE_DEFINED")
    return MSNRConfirmationVerdict(
        signal_valid=True,
        reason="PASSED",
        direction=direction,
        signal_timestamp_utc=signal_stamp,
        stop_reference_price=stop,
        target_reference_price=target,
        atr=atr,
        rejection_close_fraction=inward_fraction,
        regime=regime.state,
        evidence_codes=tuple(evidence),
        capital_authority=False,
        order_submission_permitted=False,
    )

@dataclass(frozen=True)
class VWAPPullbackConfig:
    trend_lookback_bars: int = 10
    pullback_tolerance_bps: float = 5.0
    volume_contraction_bars: int = 2
    tick_size: float | None = None
    stop_buffer_ticks: float = 1.0
    allowed_regimes: tuple[str, ...] = ("TRENDING_LOW_VOL",)
    version: str = "vwap-pullback-v1"

    def __post_init__(self) -> None:
        if self.trend_lookback_bars < 2 or self.volume_contraction_bars < 2:
            raise ValueError("VWAP_LOOKBACK_INVALID")
        if self.pullback_tolerance_bps < 0 or self.stop_buffer_ticks < 0:
            raise ValueError("VWAP_TOLERANCE_INVALID")
        if self.tick_size is not None and (not isfinite(self.tick_size) or self.tick_size <= 0):
            raise ValueError("VWAP_TICK_SIZE_INVALID")


def _session_start(bars: Sequence[StrategyBar]) -> int:
    session = bars[-1].session_id
    if not session:
        return len(bars)
    start = len(bars) - 1
    while start > 0 and bars[start - 1].session_id == session:
        start -= 1
    return start


def evaluate_vwap_pullback(
    bars: Sequence[StrategyBar], *, config: VWAPPullbackConfig,
    regime_config: RegimeConfig = RegimeConfig(),
    volume_source_verified: bool = False,
) -> StrategyCandidate | None:
    """VWAP touch/reclaim with verified session volume and a down-candle proxy.

    The proxy is not bid/ask delta or proof of institutional selling. Unverified
    or absent volume fails closed rather than manufacturing VWAP evidence.
    """
    _validate_bars(bars)
    if config.tick_size is None:
        raise ValueError("VWAP_TICK_SIZE_REQUIRED")
    if not volume_source_verified or not bars or not bars[-1].session_id:
        return None
    i, current = len(bars) - 1, bars[-1]
    start = _session_start(bars)
    if i - start < max(config.trend_lookback_bars, config.volume_contraction_bars):
        return None
    session = bars[start:i + 1]
    if any(b.session_id != current.session_id or b.volume is None or b.volume <= 0 for b in session):
        return None
    regime = classify_regime(bars[:-1], config=regime_config)
    if regime is None or regime.state not in config.allowed_regimes:
        return None
    volume_sum = sum(float(b.volume) for b in session)
    vwap = sum(((b.high + b.low + b.close) / 3.0) * float(b.volume) for b in session) / volume_sum
    if current.close <= bars[i - config.trend_lookback_bars].close:
        return None
    if not (current.low <= vwap * (1.0 + config.pullback_tolerance_bps / 10000.0)
            and current.close > vwap and current.close > current.open):
        return None
    pullback = bars[i - config.volume_contraction_bars:i]
    if any(b.session_id != current.session_id or b.volume is None or b.close >= b.open for b in pullback):
        return None
    vols = [float(b.volume) for b in pullback]
    if any(vols[k] <= vols[k + 1] for k in range(len(vols) - 1)):
        return None
    target = max(b.high for b in bars[i - config.trend_lookback_bars:i])
    if target <= current.close:
        return None
    stop = min(b.low for b in pullback + [current]) - config.stop_buffer_ticks * config.tick_size
    return StrategyCandidate(
        "VWAP_PULLBACK_RECLAIM", config.version, "LONG", current.timestamp_utc,
        "NEXT_BAR_OPEN_AFTER_SIGNAL", stop, target, "PRE_PULLBACK_SWING_HIGH",
        regime.state, ("SESSION_VWAP_TOUCH", "VWAP_CLOSE_RECLAIM", "UPTREND_CONFIRMED",
                       "DOWN_CANDLE_VOLUME_CONTRACTION_PROXY"),
    )


@dataclass(frozen=True)
class ORBConfig:
    opening_range_bars: int = 5
    tick_size: float | None = None
    breakout_buffer_ticks: float = 1.0
    minimum_range_ticks: float = 2.0
    atr_lookback_bars: int = 14
    maximum_range_atr_multiple: float = 4.0
    target_multiple_r: float = 2.0
    allowed_regimes: tuple[str, ...] = ("TRENDING_LOW_VOL",)
    version: str = "orb-v1"

    def __post_init__(self) -> None:
        if self.opening_range_bars < 2 or self.atr_lookback_bars < 2:
            raise ValueError("ORB_LOOKBACK_INVALID")
        if self.tick_size is not None and (not isfinite(self.tick_size) or self.tick_size <= 0):
            raise ValueError("ORB_TICK_SIZE_INVALID")
        if self.breakout_buffer_ticks < 0 or self.minimum_range_ticks <= 0:
            raise ValueError("ORB_RANGE_THRESHOLDS_INVALID")
        if self.maximum_range_atr_multiple <= 0 or self.target_multiple_r <= 0:
            raise ValueError("ORB_RISK_MULTIPLIER_INVALID")


def _true_range(current: StrategyBar, previous_close: float) -> float:
    return max(current.high - current.low, abs(current.high - previous_close), abs(current.low - previous_close))


def evaluate_opening_range_breakout(
    bars: Sequence[StrategyBar], *, config: ORBConfig,
    regime_config: RegimeConfig = RegimeConfig(),
) -> StrategyCandidate | None:
    """First close-confirmed breakout after N session bars; target re-anchors on fill."""
    _validate_bars(bars)
    if config.tick_size is None:
        raise ValueError("ORB_TICK_SIZE_REQUIRED")
    i = len(bars) - 1
    if not bars or not bars[i].session_id:
        return None
    current, start = bars[i], _session_start(bars)
    session = bars[start:i + 1]
    if len(session) <= config.opening_range_bars or i < 3:
        return None
    opening = session[:config.opening_range_bars]
    upper, lower = max(b.high for b in opening), min(b.low for b in opening)
    width = upper - lower
    if width < config.minimum_range_ticks * config.tick_size:
        return None
    atr_rows = bars[max(1, i - config.atr_lookback_bars):i]
    ranges = [_true_range(atr_rows[j], atr_rows[j - 1].close) for j in range(1, len(atr_rows))]
    if not ranges:
        return None
    atr = fmean(ranges)
    if atr <= 0 or width > config.maximum_range_atr_multiple * atr:
        return None
    # Regime is measured before the breakout candle to avoid using the breakout
    # itself to qualify the setup that it creates.
    regime = classify_regime(bars[:i], config=regime_config)
    if regime is None or regime.state not in config.allowed_regimes:
        return None
    prev = bars[i - 1].close
    up, down = upper + config.breakout_buffer_ticks * config.tick_size, lower - config.breakout_buffer_ticks * config.tick_size
    if prev <= up and current.close > up:
        side, stop, target = "LONG", lower, up + config.target_multiple_r * (up - lower)
        evidence = ("SESSION_OPENING_RANGE_DEFINED", "CLOSE_CONFIRMED_ABOVE_RANGE", "RANGE_QUALITY_PASSED")
    elif prev >= down and current.close < down:
        side, stop, target = "SHORT", upper, down - config.target_multiple_r * (upper - down)
        evidence = ("SESSION_OPENING_RANGE_DEFINED", "CLOSE_CONFIRMED_BELOW_RANGE", "RANGE_QUALITY_PASSED")
    else:
        return None
    return StrategyCandidate(
        "OPENING_RANGE_BREAKOUT", config.version, side, current.timestamp_utc,
        "NEXT_BAR_OPEN_AFTER_SIGNAL", stop, target, "R_MULTIPLE_FROM_TRIGGER",
        regime.state, evidence,
    )
