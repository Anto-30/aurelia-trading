"""Deterministic intraday setup detectors. Research-only; never routes orders."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite, log, sqrt
from statistics import fmean, median
from typing import Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    # These are an explicit local-market session configuration, not inferred
    # from a session label or from the visible historical data.
    session_timezone: str | None = None
    session_open_time: str | None = None  # local HH:MM in session_timezone
    opening_range_minutes: int | None = None
    bar_duration_seconds: int | None = None
    opening_range_bars: int | None = None  # optional consistency assertion only
    tick_size: float | None = None
    breakout_buffer_ticks: float = 1.0
    minimum_range_ticks: float = 2.0
    atr_lookback_bars: int = 14
    maximum_range_atr_multiple: float = 4.0
    target_multiple_r: float = 2.0
    allowed_regimes: tuple[str, ...] = ("TRENDING_LOW_VOL",)
    version: str = "orb-v2-session-explicit"

    def __post_init__(self) -> None:
        if self.atr_lookback_bars < 2 or (
            self.opening_range_bars is not None and self.opening_range_bars < 2
        ):
            raise ValueError("ORB_LOOKBACK_INVALID")
        if self.tick_size is not None and (not isfinite(self.tick_size) or self.tick_size <= 0):
            raise ValueError("ORB_TICK_SIZE_INVALID")
        if self.breakout_buffer_ticks < 0 or self.minimum_range_ticks <= 0:
            raise ValueError("ORB_RANGE_THRESHOLDS_INVALID")
        if self.maximum_range_atr_multiple <= 0 or self.target_multiple_r <= 0:
            raise ValueError("ORB_RISK_MULTIPLIER_INVALID")
        if self.session_timezone is not None:
            try:
                ZoneInfo(self.session_timezone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError("ORB_SESSION_TIMEZONE_INVALID") from exc
        if self.session_open_time is not None:
            try:
                hour_text, minute_text = self.session_open_time.split(":")
                hour, minute = int(hour_text), int(minute_text)
            except (ValueError, AttributeError) as exc:
                raise ValueError("ORB_SESSION_OPEN_TIME_INVALID") from exc
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("ORB_SESSION_OPEN_TIME_INVALID")
        if self.opening_range_minutes is not None:
            if isinstance(self.opening_range_minutes, bool) or self.opening_range_minutes <= 0:
                raise ValueError("ORB_OPENING_RANGE_DURATION_INVALID")
        if self.bar_duration_seconds is not None:
            if isinstance(self.bar_duration_seconds, bool) or self.bar_duration_seconds <= 0:
                raise ValueError("ORB_BAR_DURATION_INVALID")
        if self.opening_range_minutes is not None and self.bar_duration_seconds is not None:
            duration_seconds = self.opening_range_minutes * 60
            if duration_seconds % self.bar_duration_seconds != 0:
                raise ValueError("ORB_RANGE_NOT_DIVISIBLE_BY_BAR_DURATION")
            derived_bars = duration_seconds // self.bar_duration_seconds
            if derived_bars < 2:
                raise ValueError("ORB_OPENING_RANGE_REQUIRES_AT_LEAST_TWO_BARS")
            if self.opening_range_bars is not None and self.opening_range_bars != derived_bars:
                raise ValueError("ORB_OPENING_RANGE_BAR_COUNT_MISMATCH")


def _true_range(current: StrategyBar, previous_close: float) -> float:
    return max(current.high - current.low, abs(current.high - previous_close), abs(current.low - previous_close))


def evaluate_opening_range_breakout(
    bars: Sequence[StrategyBar], *, config: ORBConfig,
    regime_config: RegimeConfig = RegimeConfig(),
) -> StrategyCandidate | None:
    """First close-confirmed breakout after an explicit local session window.

    The first bar in each session must align to the configured local open.
    Opening-range duration is derived from minutes and bar duration, and every
    bar inside that window must be contiguous. A label alone is not session data.
    """
    _validate_bars(bars)
    if config.tick_size is None:
        raise ValueError("ORB_TICK_SIZE_REQUIRED")
    required = (
        config.session_timezone, config.session_open_time,
        config.opening_range_minutes, config.bar_duration_seconds,
    )
    if any(value is None for value in required):
        raise ValueError("ORB_SESSION_CONFIGURATION_REQUIRED")
    opening_range_seconds = int(config.opening_range_minutes) * 60
    bar_seconds = int(config.bar_duration_seconds)
    if opening_range_seconds % bar_seconds != 0:
        raise ValueError("ORB_RANGE_NOT_DIVISIBLE_BY_BAR_DURATION")
    opening_bar_count = opening_range_seconds // bar_seconds
    if opening_bar_count < 2:
        raise ValueError("ORB_OPENING_RANGE_REQUIRES_AT_LEAST_TWO_BARS")

    i = len(bars) - 1
    if not bars or not bars[i].session_id:
        return None
    current, start = bars[i], _session_start(bars)
    session = bars[start:i + 1]
    if len(session) <= opening_bar_count:
        return None

    zone = ZoneInfo(str(config.session_timezone))
    first_local = _utc(session[0].timestamp_utc).astimezone(zone)
    if first_local.strftime("%H:%M") != config.session_open_time or first_local.second != 0 or first_local.microsecond != 0:
        return None

    opening = session[:opening_bar_count]
    for previous, current_bar in zip(opening, opening[1:]):
        elapsed = (_utc(current_bar.timestamp_utc) - _utc(previous.timestamp_utc)).total_seconds()
        if elapsed != bar_seconds:
            raise ValueError("ORB_OPENING_RANGE_BAR_INTERVAL_MISMATCH")

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
    regime = classify_regime(bars[:i], config=regime_config)
    if regime is None or regime.state not in config.allowed_regimes:
        return None
    prev = bars[i - 1].close
    up, down = upper + config.breakout_buffer_ticks * config.tick_size, lower - config.breakout_buffer_ticks * config.tick_size
    if prev <= up and current.close > up:
        side, stop, target = "LONG", lower, up + config.target_multiple_r * (up - lower)
        evidence = ("SESSION_TIMEZONE_VERIFIED", "SESSION_OPEN_CONFIRMED", "OPENING_RANGE_DURATION_VERIFIED", "CLOSE_CONFIRMED_ABOVE_RANGE", "RANGE_QUALITY_PASSED")
    elif prev >= down and current.close < down:
        side, stop, target = "SHORT", upper, down - config.target_multiple_r * (upper - down)
        evidence = ("SESSION_TIMEZONE_VERIFIED", "SESSION_OPEN_CONFIRMED", "OPENING_RANGE_DURATION_VERIFIED", "CLOSE_CONFIRMED_BELOW_RANGE", "RANGE_QUALITY_PASSED")
    else:
        return None
    return StrategyCandidate(
        "OPENING_RANGE_BREAKOUT", config.version, side, current.timestamp_utc,
        "NEXT_BAR_OPEN_AFTER_SIGNAL", stop, target, "R_MULTIPLE_FROM_TRIGGER",
        regime.state, evidence,
    )
