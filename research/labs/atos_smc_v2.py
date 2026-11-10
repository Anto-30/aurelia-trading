"""ATOS v2.0 deterministic SMC research engine.

Research-only. This module has no broker adapter, order-routing interface, account
credentials, or capital authority. It models two independent strategies:

1. Supply/Demand + directional swing break (the user's CHoCH proxy).
2. Prior Asian/London liquidity sweep + displacement/BOS + new FVG CE entry.

OHLC timestamps are candle OPEN times in UTC. Signals are available only after
the signal candle closes. Pending limits can fill only on later candles. If one
OHLC candle touches both stop and target, the simulator books the stop first.
That is a conservative deterministic convention; OHLC cannot reveal the true
intrabar path.

A custom event-driven simulator is used instead of vectorbt's signal abstraction:
pending limits, setup invalidation, OCO exits, daily mark-to-market drawdown and
stop-first collision handling are path-dependent. pandas/numpy are used for
data preparation, resampling, fractals, ATR and metric calculations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from math import isfinite, sqrt
from typing import Any, Iterable, Literal, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
ORDER_SUBMISSION_PERMITTED = False
LIVE_EXECUTION = "BLOCKED"
FINAL_EXECUTION_AUTHORIZATION = False

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
OHLC = ("open", "high", "low", "close")


class ResearchDataError(ValueError):
    """Raised when the data cannot support a defensible historical simulation."""


@dataclass(frozen=True)
class TimeWindow:
    """Signal/entry window measured on the CLOSE time of each one-minute bar.

    A 1m bar stamped 08:49:00 NY closes at 08:50:00 and is eligible. A bar
    stamped 08:50:00 closes at 08:51:00 and is not eligible. Existing positions
    may be managed after the cutoff; unfilled entry orders are cancelled.
    """

    timezone: str = "America/New_York"
    start: str = "00:00"
    cutoff: str = "08:50"

    def __post_init__(self) -> None:
        try:
            ZoneInfo(self.timezone)
            start = _parse_clock(self.start)
            cutoff = _parse_clock(self.cutoff)
        except (ValueError, TypeError) as exc:
            raise ValueError("TIME_WINDOW_CONFIGURATION_INVALID") from exc
        if start > cutoff:
            raise ValueError("TIME_WINDOW_START_AFTER_CUTOFF")

    def mask(self, index_open_utc: pd.DatetimeIndex, bar_minutes: int = 1) -> np.ndarray:
        tz = ZoneInfo(self.timezone)
        close_times = (index_open_utc + pd.Timedelta(minutes=bar_minutes)).tz_convert(tz)
        start, cutoff = _parse_clock(self.start), _parse_clock(self.cutoff)
        return np.asarray([
            start <= stamp.timetz().replace(tzinfo=None) <= cutoff
            for stamp in close_times
        ], dtype=bool)

    def open_mask(self, index_open_utc: pd.DatetimeIndex) -> np.ndarray:
        """True for bar opens inside the window; used only for pending-order fills."""
        local = index_open_utc.tz_convert(self.timezone)
        start, cutoff = _parse_clock(self.start), _parse_clock(self.cutoff)
        return np.asarray([
            start <= stamp.timetz().replace(tzinfo=None) <= cutoff
            for stamp in local
        ], dtype=bool)

    def is_cutoff_open(self, open_time_utc: pd.Timestamp) -> bool:
        local = open_time_utc.tz_convert(self.timezone)
        return local.timetz().replace(tzinfo=None) == _parse_clock(self.cutoff)

    def close_time(self, open_time: pd.Timestamp, bar_minutes: int = 1) -> pd.Timestamp:
        return (open_time + pd.Timedelta(minutes=bar_minutes)).tz_convert(self.timezone)


def _parse_clock(value: str) -> time:
    parts = str(value).split(":")
    if len(parts) != 2:
        raise ValueError("CLOCK_MUST_BE_HH_MM")
    hour, minute = (int(part) for part in parts)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("CLOCK_OUT_OF_RANGE")
    return time(hour, minute)


def validate_ohlc(frame: pd.DataFrame, *, expected_minutes: int = 1) -> pd.DataFrame:
    """Validate, normalize and return UTC-indexed OHLC without filling gaps."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ResearchDataError("OHLC_DATA_EMPTY")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ResearchDataError("OHLC_INDEX_MUST_BE_TIMEZONE_AWARE")
    out = frame.copy()
    out.columns = [str(column).strip().lower() for column in out.columns]
    missing = [column for column in OHLC if column not in out.columns]
    if missing:
        raise ResearchDataError("OHLC_REQUIRED_COLUMNS_MISSING:" + ",".join(missing))
    out.index = out.index.tz_convert("UTC")
    out.index.name = "timestamp_utc"
    if out.index.has_duplicates:
        raise ResearchDataError("OHLC_DUPLICATE_TIMESTAMPS")
    if not out.index.is_monotonic_increasing:
        raise ResearchDataError("OHLC_TIMESTAMPS_NOT_STRICTLY_INCREASING")
    for column in OHLC:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    values = out.loc[:, OHLC].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ResearchDataError("OHLC_PRICES_NOT_FINITE_POSITIVE")
    if (out["high"] < out[["open", "close", "low"]].max(axis=1)).any():
        raise ResearchDataError("OHLC_HIGH_INCONSISTENT")
    if (out["low"] > out[["open", "close", "high"]].min(axis=1)).any():
        raise ResearchDataError("OHLC_LOW_INCONSISTENT")
    if "volume" in out.columns:
        out["volume"] = pd.to_numeric(out["volume"], errors="coerce")
        if out["volume"].notna().any() and (
            (~np.isfinite(out["volume"].dropna())).any()
            or (out["volume"].dropna() < 0).any()
        ):
            raise ResearchDataError("OHLC_VOLUME_INVALID")
    if expected_minutes > 0 and len(out) > 1:
        delta = out.index.to_series().diff().dropna()
        if (delta < pd.Timedelta(minutes=expected_minutes)).any():
            raise ResearchDataError("OHLC_TIME_STEP_INVALID")
    return out


def data_quality_report(
    frame: pd.DataFrame,
    *,
    start_utc: datetime | pd.Timestamp | None = None,
    end_utc: datetime | pd.Timestamp | None = None,
    expected_minutes: int = 1,
) -> dict[str, Any]:
    """Report coverage and gaps; never forward-fill or silently repair candles."""
    data = validate_ohlc(frame, expected_minutes=expected_minutes)
    start = pd.Timestamp(start_utc).tz_convert("UTC") if start_utc is not None else data.index[0]
    end = pd.Timestamp(end_utc).tz_convert("UTC") if end_utc is not None else (
        data.index[-1] + pd.Timedelta(minutes=expected_minutes)
    )
    if end <= start:
        raise ResearchDataError("QUALITY_WINDOW_INVALID")
    expected = pd.date_range(
        start=start.ceil(f"{expected_minutes}min"),
        end=(end - pd.Timedelta(minutes=expected_minutes)).floor(f"{expected_minutes}min"),
        freq=f"{expected_minutes}min",
        tz="UTC",
    )
    present = data.index[(data.index >= start) & (data.index < end)]
    missing = expected.difference(present)
    gaps = data.index.to_series().diff().dropna()
    return {
        "rows": int(len(data)),
        "start_utc": data.index[0].isoformat(),
        "end_utc_exclusive": (data.index[-1] + pd.Timedelta(minutes=expected_minutes)).isoformat(),
        "requested_start_utc": start.isoformat(),
        "requested_end_utc": end.isoformat(),
        "expected_bars": int(len(expected)),
        "present_bars_in_window": int(len(present)),
        "missing_bars": int(len(missing)),
        "coverage_pct": float(100.0 * len(present) / len(expected)) if len(expected) else None,
        "max_gap_minutes": float(gaps.max().total_seconds() / 60.0) if len(gaps) else 0.0,
        "gaps_gt_one_bar": int((gaps > pd.Timedelta(minutes=expected_minutes)).sum()),
        "forward_filled": False,
        "duplicates": 0,
        "quality_status": "PASS" if len(missing) == 0 else "GAPS_PRESENT",
    }


def resample_15m(frame_1m: pd.DataFrame) -> pd.DataFrame:
    """Create complete 15m candles from 1m candle-open timestamps only."""
    data = validate_ohlc(frame_1m, expected_minutes=1)
    agg = data.loc[:, OHLC].resample("15min", label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
    })
    counts = data["close"].resample("15min", label="left", closed="left").count()
    return agg.loc[counts[counts == 15].index].dropna(subset=list(OHLC))


@dataclass(frozen=True)
class SwingConfig:
    left: int = 2
    right: int = 2

    def __post_init__(self) -> None:
        if self.left < 1 or self.right < 1:
            raise ValueError("FRACTAL_LEFT_RIGHT_MUST_BE_POSITIVE")


def _swing_context(
    frame: pd.DataFrame,
    *,
    config: SwingConfig = SwingConfig(),
    bar_minutes: int = 1,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    """Return only pivots confirmed by the current bar; no centred-window leak."""
    data = validate_ohlc(frame, expected_minutes=bar_minutes)
    highs = data["high"].to_numpy(dtype=float)
    lows = data["low"].to_numpy(dtype=float)
    n = len(data)
    high_events: dict[int, list[dict[str, Any]]] = {}
    low_events: dict[int, list[dict[str, Any]]] = {}
    all_highs: list[dict[str, Any]] = []
    all_lows: list[dict[str, Any]] = []

    for pivot in range(config.left, n - config.right):
        confirm = pivot + config.right
        left_high = highs[pivot - config.left:pivot]
        right_high = highs[pivot + 1:pivot + config.right + 1]
        left_low = lows[pivot - config.left:pivot]
        right_low = lows[pivot + 1:pivot + config.right + 1]

        # Tie policy: a flat extreme belongs to the earliest bar in the plateau.
        if highs[pivot] > np.max(left_high) and highs[pivot] >= np.max(right_high):
            event = {
                "pivot_index": pivot,
                "confirmed_index": confirm,
                "timestamp_utc": data.index[pivot],
                "available_at_utc": data.index[confirm] + pd.Timedelta(minutes=bar_minutes),
                "price": float(highs[pivot]),
                "kind": "HIGH",
            }
            high_events.setdefault(confirm, []).append(event)
            all_highs.append(event)
        if lows[pivot] < np.min(left_low) and lows[pivot] <= np.min(right_low):
            event = {
                "pivot_index": pivot,
                "confirmed_index": confirm,
                "timestamp_utc": data.index[pivot],
                "available_at_utc": data.index[confirm] + pd.Timedelta(minutes=bar_minutes),
                "price": float(lows[pivot]),
                "kind": "LOW",
            }
            low_events.setdefault(confirm, []).append(event)
            all_lows.append(event)

    rows: list[dict[str, Any]] = []
    confirmed_highs: list[dict[str, Any]] = []
    confirmed_lows: list[dict[str, Any]] = []
    for i in range(n):
        confirmed_highs.extend(high_events.get(i, []))
        confirmed_lows.extend(low_events.get(i, []))
        hi = [event["price"] for event in confirmed_highs[-2:]]
        lo = [event["price"] for event in confirmed_lows[-2:]]
        bias = "RANGE"
        if len(hi) == 2 and len(lo) == 2:
            if hi[-1] > hi[-2] and lo[-1] > lo[-2]:
                bias = "UP"
            elif hi[-1] < hi[-2] and lo[-1] < lo[-2]:
                bias = "DOWN"
        rows.append({
            "last_high": hi[-1] if hi else np.nan,
            "previous_high": hi[-2] if len(hi) == 2 else np.nan,
            "last_low": lo[-1] if lo else np.nan,
            "previous_low": lo[-2] if len(lo) == 2 else np.nan,
            "bias": bias,
        })
    state = pd.DataFrame(rows, index=data.index)
    return state, all_highs, all_lows


def _mtf_bias(
    frame_1m: pd.DataFrame,
    *,
    swing_config: SwingConfig,
) -> tuple[pd.Series, list[dict[str, Any]], list[dict[str, Any]]]:
    """Map the latest *closed and confirmed* 15m structure to each 1m close."""
    higher = resample_15m(frame_1m)
    if higher.empty:
        return pd.Series("UNKNOWN", index=frame_1m.index, dtype="object"), [], []
    state, highs, lows = _swing_context(
        higher, config=swing_config, bar_minutes=15
    )
    available = higher.index + pd.Timedelta(minutes=15)
    right = pd.DataFrame({
        "available_at": available,
        "bias": state["bias"].to_numpy(),
    }).sort_values("available_at")
    left = pd.DataFrame({
        "signal_at": frame_1m.index + pd.Timedelta(minutes=1),
        "_row": np.arange(len(frame_1m)),
    }).sort_values("signal_at")
    merged = pd.merge_asof(
        left, right, left_on="signal_at", right_on="available_at", direction="backward"
    ).sort_values("_row")
    bias = pd.Series(
        merged["bias"].fillna("UNKNOWN").to_numpy(),
        index=frame_1m.index,
        dtype="object",
    )
    return bias, highs, lows


def _atr_before_bar(frame: pd.DataFrame, period: int) -> pd.Series:
    previous_close = frame["close"].shift(1)
    tr = pd.concat([
        frame["high"] - frame["low"],
        (frame["high"] - previous_close).abs(),
        (frame["low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    # The threshold used on bar i is known before bar i starts.
    return tr.rolling(period, min_periods=period).mean().shift(1)


def _known_pivots(
    events: Iterable[dict[str, Any]],
    *,
    signal_time: pd.Timestamp,
    side: Literal["HIGH", "LOW"],
) -> list[float]:
    return [
        float(event["price"])
        for event in events
        if event["kind"] == side and event["available_at_utc"] <= signal_time
    ]


def _nearest_liquidity_target(
    entry: float,
    direction: Literal["LONG", "SHORT"],
    high_events: Sequence[dict[str, Any]],
    low_events: Sequence[dict[str, Any]],
    signal_time: pd.Timestamp,
    *,
    current_price: float | None = None,
) -> tuple[float | None, str | None]:
    # Target must still be ahead of the signal close, not merely ahead of entry.
    reference = entry if current_price is None else float(current_price)
    if direction == "LONG":
        levels = _known_pivots(high_events, signal_time=signal_time, side="HIGH")
        candidates = [level for level in levels if level > max(entry, reference)]
        return (min(candidates), "NEAREST_CONFIRMED_SWING_HIGH") if candidates else (None, None)
    levels = _known_pivots(low_events, signal_time=signal_time, side="LOW")
    candidates = [level for level in levels if level < min(entry, reference)]
    return (max(candidates), "NEAREST_CONFIRMED_SWING_LOW") if candidates else (None, None)


@dataclass(frozen=True)
class Strategy1Config:
    swing: SwingConfig = SwingConfig()
    atr_period: int = 14
    origin_lookback: int = 10
    minimum_rr: float = 3.0
    order_ttl_bars: int = 30
    atr_stop_multiple: float = 1.0
    time_window: TimeWindow = TimeWindow()

    def __post_init__(self) -> None:
        if self.atr_period < 2 or self.origin_lookback < 1 or self.order_ttl_bars < 1:
            raise ValueError("STRATEGY1_LOOKBACK_INVALID")
        if self.minimum_rr < 3.0 or self.atr_stop_multiple <= 0:
            raise ValueError("STRATEGY1_RR_OR_STOP_INVALID")


@dataclass(frozen=True)
class Strategy2Config:
    swing: SwingConfig = SwingConfig()
    atr_period: int = 14
    displacement_atr_multiple: float = 1.5
    equal_level_tolerance_ticks: float = 2.0
    minimum_sweep_ticks: float = 1.0
    stop_buffer_ticks: float = 1.0
    max_displacement_wait_bars: int = 10
    order_ttl_bars: int = 30
    asia_start: str = "19:00"
    asia_end: str = "00:00"
    london_start: str = "02:00"
    london_end: str = "05:00"
    time_window: TimeWindow = TimeWindow()

    def __post_init__(self) -> None:
        if self.atr_period < 2 or self.max_displacement_wait_bars < 1 or self.order_ttl_bars < 1:
            raise ValueError("STRATEGY2_LOOKBACK_INVALID")
        if self.displacement_atr_multiple <= 0 or self.equal_level_tolerance_ticks < 0:
            raise ValueError("STRATEGY2_THRESHOLD_INVALID")
        if self.minimum_sweep_ticks <= 0 or self.stop_buffer_ticks < 0:
            raise ValueError("STRATEGY2_TICK_BUFFER_INVALID")
        for value in (self.asia_start, self.asia_end, self.london_start, self.london_end):
            _parse_clock(value)


@dataclass(frozen=True)
class Setup:
    strategy_id: str
    direction: Literal["LONG", "SHORT"]
    signal_index: int
    signal_time_utc: str
    entry: float
    stop: float
    target: float
    invalidation_price: float
    zone_low: float
    zone_high: float
    order_ttl_bars: int
    minimum_rr: float
    evidence: tuple[str, ...]
    liquidity_reference: str
    origin_time_utc: str | None = None
    sweep_time_utc: str | None = None

    def __post_init__(self) -> None:
        if self.direction not in ("LONG", "SHORT"):
            raise ValueError("SETUP_DIRECTION_INVALID")
        prices = (self.entry, self.stop, self.target, self.invalidation_price, self.zone_low, self.zone_high)
        if not all(isfinite(float(x)) and float(x) > 0 for x in prices):
            raise ValueError("SETUP_PRICES_INVALID")
        if self.zone_low > self.zone_high or self.order_ttl_bars < 1:
            raise ValueError("SETUP_ZONE_OR_TTL_INVALID")
        if self.direction == "LONG" and not (self.stop < self.entry < self.target):
            raise ValueError("LONG_SETUP_LEVEL_ORDER_INVALID")
        if self.direction == "SHORT" and not (self.target < self.entry < self.stop):
            raise ValueError("SHORT_SETUP_LEVEL_ORDER_INVALID")

    @property
    def planned_rr(self) -> float:
        risk = abs(self.entry - self.stop)
        reward = abs(self.target - self.entry)
        return reward / risk if risk > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["planned_rr"] = self.planned_rr
        return result


def strategy1_supply_demand_choch(
    frame_1m: pd.DataFrame,
    *,
    tick_size: float,
    config: Strategy1Config = Strategy1Config(),
) -> list[Setup]:
    """S&D origin candle + directional close through last confirmed swing.

    Long: 1m structure HH/HL, 15m bias UP, close breaks last confirmed swing high;
    nearest prior bearish candle is the demand origin. Short is the inverse.
    "CHoCH" is implemented exactly as the requested directional swing-close proxy.
    It is closer to a close-confirmed structure break than every textbook CHoCH
    taxonomy; the operational definition is intentionally explicit.
    """
    if not isfinite(float(tick_size)) or tick_size <= 0:
        raise ValueError("INSTRUMENT_TICK_SIZE_REQUIRED")
    data = validate_ohlc(frame_1m)
    if len(data) < max(config.atr_period + 3, config.swing.left + config.swing.right + 5):
        return []
    state, high_events, low_events = _swing_context(data, config=config.swing)
    bias15, high15, low15 = _mtf_bias(data, swing_config=config.swing)
    atr = _atr_before_bar(data, config.atr_period).to_numpy(dtype=float)
    active = config.time_window.mask(data.index)
    highs_all = high_events + high15
    lows_all = low_events + low15
    setups: list[Setup] = []
    opens = data["open"].to_numpy(dtype=float)
    highs = data["high"].to_numpy(dtype=float)
    lows = data["low"].to_numpy(dtype=float)
    closes = data["close"].to_numpy(dtype=float)

    for i in range(1, len(data)):
        if not active[i] or not isfinite(atr[i]) or atr[i] <= 0:
            continue
        direction: Literal["LONG", "SHORT"] | None = None
        pivot = np.nan
        local_bias = state["bias"].iloc[i]
        if local_bias == "UP" and bias15.iloc[i] == "UP":
            pivot = float(state["last_high"].iloc[i])
            if isfinite(pivot) and closes[i] > pivot and closes[i - 1] <= pivot:
                direction = "LONG"
        elif local_bias == "DOWN" and bias15.iloc[i] == "DOWN":
            pivot = float(state["last_low"].iloc[i])
            if isfinite(pivot) and closes[i] < pivot and closes[i - 1] >= pivot:
                direction = "SHORT"
        if direction is None:
            continue

        first = max(0, i - config.origin_lookback)
        origin_candidates = range(i - 1, first - 1, -1)
        origin = next((
            k for k in origin_candidates
            if (closes[k] < opens[k] if direction == "LONG" else closes[k] > opens[k])
        ), None)
        if origin is None:
            continue

        proximal = float(opens[origin])
        if direction == "LONG":
            distal = float(lows[origin])
            # Any later return to the proximal line means the zone was mitigated.
            if (lows[origin + 1:i + 1] <= proximal).any():
                continue
            stop = distal - config.atr_stop_multiple * atr[i]
            entry = proximal
        else:
            distal = float(highs[origin])
            if (highs[origin + 1:i + 1] >= proximal).any():
                continue
            stop = distal + config.atr_stop_multiple * atr[i]
            entry = proximal
        signal_time = data.index[i] + pd.Timedelta(minutes=1)
        target, target_source = _nearest_liquidity_target(
            entry, direction, highs_all, lows_all, signal_time,
            current_price=closes[i],
        )
        if target is None or target_source is None:
            continue
        risk = entry - stop if direction == "LONG" else stop - entry
        reward = target - entry if direction == "LONG" else entry - target
        rr = reward / risk if risk > 0 else 0.0
        if risk <= tick_size * 0.25 or reward <= 0 or rr < config.minimum_rr:
            continue
        setups.append(Setup(
            strategy_id="ATOS_S1_SUPPLY_DEMAND_CHOCH",
            direction=direction,
            signal_index=i,
            signal_time_utc=signal_time.isoformat(),
            entry=entry,
            stop=stop,
            target=float(target),
            invalidation_price=distal,
            zone_low=float(lows[origin]),
            zone_high=float(highs[origin]),
            order_ttl_bars=config.order_ttl_bars,
            minimum_rr=config.minimum_rr,
            evidence=(
                "1M_CONFIRMED_FRACTAL_TREND",
                "15M_CLOSED_BIAS_ALIGNED",
                "BODY_CLOSE_BEYOND_LAST_CONFIRMED_SWING",
                "ORIGIN_CANDLE_ZONE_UNMITIGATED",
                "ATR_STOP_BEYOND_DISTAL",
                "NEXT_CONFIRMED_LIQUIDITY_TARGET",
                "MINIMUM_3R_PASSED",
            ),
            liquidity_reference=target_source,
            origin_time_utc=data.index[origin].isoformat(),
        ))
    return setups


@dataclass(frozen=True)
class LiquidityPool:
    pool_id: str
    session_date: str
    session_name: str
    kind: str
    side: Literal["HIGH", "LOW"]
    level: float
    lower: float | None = None
    upper: float | None = None
    source_time_utc: str | None = None


def _clustered_levels(values: Sequence[tuple[int, float]], tolerance: float) -> list[float]:
    ordered = sorted(values, key=lambda item: item[1])
    clusters: list[list[float]] = []
    for _, price in ordered:
        # Every member must remain within the full two-tick band from the
        # cluster's first price; chained near-neighbours cannot widen the band.
        if not clusters or price - clusters[-1][0] > tolerance:
            clusters.append([price])
        else:
            clusters[-1].append(price)
    return [float(np.median(cluster)) for cluster in clusters if len(cluster) >= 2]


def _session_fvg_pools(
    session: pd.DataFrame,
    *,
    session_date: str,
    session_name: str,
) -> list[LiquidityPool]:
    pools: list[LiquidityPool] = []
    hi = session["high"].to_numpy(dtype=float)
    lo = session["low"].to_numpy(dtype=float)
    for i in range(2, len(session)):
        lower: float | None = None
        upper: float | None = None
        kind: str | None = None
        side: Literal["HIGH", "LOW"] | None = None
        if lo[i] > hi[i - 2]:
            lower, upper, kind, side = float(hi[i - 2]), float(lo[i]), "BULLISH_FVG", "LOW"
        elif hi[i] < lo[i - 2]:
            lower, upper, kind, side = float(hi[i]), float(lo[i - 2]), "BEARISH_FVG", "HIGH"
        if lower is None or upper is None or kind is None or side is None:
            continue
        later = session.iloc[i + 1:]
        mitigated = (
            (later["low"] <= upper) & (later["high"] >= lower)
        ).any() if not later.empty else False
        if not mitigated:
            pools.append(LiquidityPool(
                pool_id=f"{session_name}:{kind}:{session.index[i].isoformat()}",
                session_date=session_date,
                session_name=session_name,
                kind=kind,
                side=side,
                level=lower if side == "LOW" else upper,
                lower=lower,
                upper=upper,
                source_time_utc=session.index[i].isoformat(),
            ))
    return pools


def build_prior_session_liquidity(
    frame_1m: pd.DataFrame,
    *,
    tick_size: float,
    config: Strategy2Config = Strategy2Config(),
) -> dict[str, list[LiquidityPool]]:
    """Build prior completed Asia/London pools keyed by their NY session date.

    Conventions are configurable: Asia 19:00 previous NY date to 00:00 current
    date; London 02:00–05:00 on the prior NY date. Both windows are complete
    before any signal on the current date, so current-session future data is not used.
    """
    if not isfinite(float(tick_size)) or tick_size <= 0:
        raise ValueError("INSTRUMENT_TICK_SIZE_REQUIRED")
    data = validate_ohlc(frame_1m)
    local_index = data.index.tz_convert(config.time_window.timezone)
    days = sorted(set(local_index.date))
    tolerance = config.equal_level_tolerance_ticks * tick_size
    result: dict[str, list[LiquidityPool]] = {}

    for current_day in days:
        prior_day = current_day - timedelta(days=1)
        windows = (
            ("ASIA", datetime.combine(prior_day, _parse_clock(config.asia_start), tzinfo=ZoneInfo(config.time_window.timezone)),
             datetime.combine(current_day, _parse_clock(config.asia_end), tzinfo=ZoneInfo(config.time_window.timezone))),
            # The previous completed London session is on the prior NY date.
            # Never use the current day's still-forming London range for earlier
            # 1-minute signals; that would introduce future-session look-ahead.
            ("LONDON", datetime.combine(prior_day, _parse_clock(config.london_start), tzinfo=ZoneInfo(config.time_window.timezone)),
             datetime.combine(prior_day, _parse_clock(config.london_end), tzinfo=ZoneInfo(config.time_window.timezone))),
        )
        pools: list[LiquidityPool] = []
        for session_name, start_local, end_local in windows:
            start_utc = pd.Timestamp(start_local).tz_convert("UTC")
            end_utc = pd.Timestamp(end_local).tz_convert("UTC")
            session = data.loc[(data.index >= start_utc) & (data.index < end_utc)]
            if session.empty:
                continue
            session_key = current_day.isoformat()
            pools.extend([
                LiquidityPool(
                    pool_id=f"{session_name}:SESSION_HIGH:{session.index[0].isoformat()}",
                    session_date=session_key,
                    session_name=session_name,
                    kind="SESSION_HIGH",
                    side="HIGH",
                    level=float(session["high"].max()),
                    source_time_utc=session.index[int(np.argmax(session["high"].to_numpy()))].isoformat(),
                ),
                LiquidityPool(
                    pool_id=f"{session_name}:SESSION_LOW:{session.index[0].isoformat()}",
                    session_date=session_key,
                    session_name=session_name,
                    kind="SESSION_LOW",
                    side="LOW",
                    level=float(session["low"].min()),
                    source_time_utc=session.index[int(np.argmin(session["low"].to_numpy()))].isoformat(),
                ),
            ])
            state, high_events, low_events = _swing_context(session, config=config.swing)
            del state
            eqh = _clustered_levels(
                [(event["pivot_index"], event["price"]) for event in high_events], tolerance
            )
            eql = _clustered_levels(
                [(event["pivot_index"], event["price"]) for event in low_events], tolerance
            )
            for level_index, level in enumerate(eqh):
                pools.append(LiquidityPool(
                    pool_id=f"{session_name}:EQH:{level_index}",
                    session_date=session_key, session_name=session_name,
                    kind="EQUAL_HIGHS", side="HIGH", level=level,
                ))
            for level_index, level in enumerate(eql):
                pools.append(LiquidityPool(
                    pool_id=f"{session_name}:EQL:{level_index}",
                    session_date=session_key, session_name=session_name,
                    kind="EQUAL_LOWS", side="LOW", level=level,
                ))
            pools.extend(_session_fvg_pools(
                session, session_date=session_key, session_name=session_name
            ))
        result[current_day.isoformat()] = pools
    return result


def _unmitigated_fvg_pools(
    pools: Sequence[LiquidityPool],
    data: pd.DataFrame,
    current_index: int,
) -> list[LiquidityPool]:
    """Keep prior-session FVG pools only until the first later bar trades into them."""
    eligible: list[LiquidityPool] = []
    current_time = data.index[current_index]
    for pool in pools:
        if pool.lower is None or pool.upper is None or pool.source_time_utc is None:
            eligible.append(pool)
            continue
        formed_at = pd.Timestamp(pool.source_time_utc)
        later = data.loc[(data.index > formed_at) & (data.index < current_time)]
        mitigated = (
            (later["low"] <= pool.upper) & (later["high"] >= pool.lower)
        ).any() if not later.empty else False
        if not mitigated:
            eligible.append(pool)
    return eligible


def _detect_sweep(
    bar: pd.Series,
    pools: Sequence[LiquidityPool],
    *,
    tick_size: float,
    minimum_sweep_ticks: float,
) -> dict[str, Any] | None:
    threshold = tick_size * minimum_sweep_ticks
    candidates: list[dict[str, Any]] = []
    for pool in pools:
        if pool.kind in ("SESSION_HIGH", "EQUAL_HIGHS"):
            boundary = pool.level
            pierced = float(bar["high"]) > boundary + threshold
            reclaimed = float(bar["open"]) < boundary and float(bar["close"]) < boundary
            if pierced and reclaimed:
                candidates.append({
                    "direction": "SHORT", "boundary": boundary,
                    "wick": float(bar["high"]), "pool": pool,
                })
        elif pool.kind in ("SESSION_LOW", "EQUAL_LOWS"):
            boundary = pool.level
            pierced = float(bar["low"]) < boundary - threshold
            reclaimed = float(bar["open"]) > boundary and float(bar["close"]) > boundary
            if pierced and reclaimed:
                candidates.append({
                    "direction": "LONG", "boundary": boundary,
                    "wick": float(bar["low"]), "pool": pool,
                })
        elif pool.kind == "BULLISH_FVG" and pool.lower is not None and pool.upper is not None:
            boundary = pool.lower
            pierced = float(bar["low"]) < boundary - threshold
            reclaimed = (
                float(bar["open"]) > boundary
                and boundary < float(bar["close"]) <= pool.upper
            )
            if pierced and reclaimed:
                candidates.append({
                    "direction": "LONG", "boundary": boundary,
                    "wick": float(bar["low"]), "pool": pool,
                })
        elif pool.kind == "BEARISH_FVG" and pool.lower is not None and pool.upper is not None:
            boundary = pool.upper
            pierced = float(bar["high"]) > boundary + threshold
            reclaimed = (
                float(bar["open"]) < boundary
                and pool.lower <= float(bar["close"]) < boundary
            )
            if pierced and reclaimed:
                candidates.append({
                    "direction": "SHORT", "boundary": boundary,
                    "wick": float(bar["high"]), "pool": pool,
                })
    directions = {candidate["direction"] for candidate in candidates}
    if len(directions) != 1 or not candidates:
        return None
    # Select the pool nearest to the wick's penetration; ties are deterministic.
    candidates.sort(key=lambda item: (
        abs(item["wick"] - item["boundary"]),
        item["pool"].pool_id,
    ))
    return candidates[0]


def _opposing_pool_target(
    pools: Sequence[LiquidityPool],
    direction: Literal["LONG", "SHORT"],
    entry: float,
    *,
    current_price: float | None = None,
) -> tuple[float | None, str | None]:
    reference = entry if current_price is None else float(current_price)
    if direction == "LONG":
        candidates = [
            pool for pool in pools
            if pool.side == "HIGH" and pool.level > max(entry, reference)
            and pool.kind in ("SESSION_HIGH", "EQUAL_HIGHS")
        ]
        if not candidates:
            return None, None
        chosen = min(candidates, key=lambda pool: (pool.level, pool.pool_id))
    else:
        candidates = [
            pool for pool in pools
            if pool.side == "LOW" and pool.level < min(entry, reference)
            and pool.kind in ("SESSION_LOW", "EQUAL_LOWS")
        ]
        if not candidates:
            return None, None
        chosen = max(candidates, key=lambda pool: (pool.level, pool.pool_id))
    return float(chosen.level), chosen.kind


def strategy2_fvg_sweep_displacement(
    frame_1m: pd.DataFrame,
    *,
    tick_size: float,
    config: Strategy2Config = Strategy2Config(),
) -> list[Setup]:
    """Sweep -> later displacement (>1.5x prior ATR) + BOS -> new FVG CE.

    A close through the swept level/FVG boundary invalidates that sweep. A valid
    FVG order is entered at its 50% CE; the stop sits beyond the original sweep
    wick and the target is the nearest opposing session liquidity pool.
    """
    if not isfinite(float(tick_size)) or tick_size <= 0:
        raise ValueError("INSTRUMENT_TICK_SIZE_REQUIRED")
    data = validate_ohlc(frame_1m)
    minimum_rows = max(config.atr_period + 4, config.swing.left + config.swing.right + 5)
    if len(data) < minimum_rows:
        return []
    state, _, _ = _swing_context(data, config=config.swing)
    bias15, _, _ = _mtf_bias(data, swing_config=config.swing)
    atr = _atr_before_bar(data, config.atr_period).to_numpy(dtype=float)
    active = config.time_window.mask(data.index)
    pools_by_day = build_prior_session_liquidity(data, tick_size=tick_size, config=config)
    local_close_dates = [
        stamp.date().isoformat()
        for stamp in (data.index + pd.Timedelta(minutes=1)).tz_convert(config.time_window.timezone)
    ]
    opens = data["open"].to_numpy(dtype=float)
    highs = data["high"].to_numpy(dtype=float)
    lows = data["low"].to_numpy(dtype=float)
    closes = data["close"].to_numpy(dtype=float)
    pending_sweeps: list[dict[str, Any]] = []
    setups: list[Setup] = []

    for i in range(len(data)):
        if not active[i]:
            # Once the entry window closes, no incomplete sweep can mature later.
            pending_sweeps.clear()
            continue
        pools = _unmitigated_fvg_pools(
            pools_by_day.get(local_close_dates[i], []), data, i
        )
        # Evaluate older sweeps before registering a sweep on the current candle.
        for sweep in list(reversed(pending_sweeps)):
            age = i - int(sweep["index"])
            if age < 1:
                continue
            if age > config.max_displacement_wait_bars:
                pending_sweeps.remove(sweep)
                continue
            boundary = float(sweep["boundary"])
            if sweep["direction"] == "LONG":
                invalidated = (closes[sweep["index"] + 1:i + 1] <= boundary).any()
            else:
                invalidated = (closes[sweep["index"] + 1:i + 1] >= boundary).any()
            if invalidated:
                pending_sweeps.remove(sweep)
                continue
            if not isfinite(atr[i]) or atr[i] <= 0:
                continue
            body = abs(closes[i] - opens[i])
            if body <= config.displacement_atr_multiple * atr[i]:
                continue
            direction = sweep["direction"]
            if direction == "LONG":
                broken_level = float(state["last_high"].iloc[i])
                bos = isfinite(broken_level) and closes[i] > broken_level and closes[i - 1] <= broken_level
                fvg = i >= 2 and lows[i] > highs[i - 2]
                if not bos or not fvg or bias15.iloc[i] != "UP":
                    # Once displacement occurs, a missing BOS/FVG/bias alignment
                    # invalidates this sweep rather than allowing stale drift setups.
                    pending_sweeps.remove(sweep)
                    continue
                zone_low, zone_high = float(highs[i - 2]), float(lows[i])
                entry = (zone_low + zone_high) / 2.0
                stop = float(sweep["wick"]) - config.stop_buffer_ticks * tick_size
                target, target_source = _opposing_pool_target(pools, "LONG", entry, current_price=closes[i])
                invalidation = zone_low
            else:
                broken_level = float(state["last_low"].iloc[i])
                bos = isfinite(broken_level) and closes[i] < broken_level and closes[i - 1] >= broken_level
                fvg = i >= 2 and highs[i] < lows[i - 2]
                if not bos or not fvg or bias15.iloc[i] != "DOWN":
                    pending_sweeps.remove(sweep)
                    continue
                zone_low, zone_high = float(highs[i]), float(lows[i - 2])
                entry = (zone_low + zone_high) / 2.0
                stop = float(sweep["wick"]) + config.stop_buffer_ticks * tick_size
                target, target_source = _opposing_pool_target(pools, "SHORT", entry, current_price=closes[i])
                invalidation = zone_high
            if target is None or target_source is None:
                pending_sweeps.remove(sweep)
                continue
            risk = entry - stop if direction == "LONG" else stop - entry
            reward = target - entry if direction == "LONG" else entry - target
            if risk <= tick_size * 0.25 or reward <= 0:
                pending_sweeps.remove(sweep)
                continue
            signal_time = data.index[i] + pd.Timedelta(minutes=1)
            setups.append(Setup(
                strategy_id="ATOS_S2_FVG_SWEEP_DISPLACEMENT",
                direction=direction,
                signal_index=i,
                signal_time_utc=signal_time.isoformat(),
                entry=entry,
                stop=stop,
                target=float(target),
                invalidation_price=invalidation,
                zone_low=zone_low,
                zone_high=zone_high,
                order_ttl_bars=config.order_ttl_bars,
                minimum_rr=0.0,
                evidence=(
                    "PRIOR_ASIA_OR_LONDON_LIQUIDITY_POOL",
                    "WICK_SWEEP_AND_CLOSE_RECLAIM",
                    "NO_INVERSION_CLOSE",
                    "SUBSEQUENT_DISPLACEMENT_GT_1_5X_PRIOR_ATR14",
                    "CLOSE_CONFIRMED_BREAK_OF_STRUCTURE",
                    "NEW_THREE_CANDLE_FVG",
                    "CE_50_PERCENT_LIMIT",
                    "STOP_BEYOND_SWEEP_WICK",
                    "OPPOSING_SESSION_LIQUIDITY_TARGET",
                    "15M_CLOSED_BIAS_ALIGNED",
                ),
                liquidity_reference=target_source,
                sweep_time_utc=data.index[int(sweep["index"])].isoformat(),
            ))
            pending_sweeps.remove(sweep)
            # One signal per displacement bar.
            break

        found = _detect_sweep(
            data.iloc[i], pools, tick_size=tick_size,
            minimum_sweep_ticks=config.minimum_sweep_ticks,
        )
        if found is not None:
            found["index"] = i
            pending_sweeps.append(found)
            pending_sweeps = pending_sweeps[-8:]
    return setups


@dataclass(frozen=True)
class SupplyDemandCHoCHStrategy:
    """Independent Strategy 1 detector; it only emits research Setup records."""

    config: Strategy1Config = Strategy1Config()

    def generate_setups(self, frame_1m: pd.DataFrame, *, tick_size: float) -> list[Setup]:
        return strategy1_supply_demand_choch(
            frame_1m, tick_size=tick_size, config=self.config
        )


@dataclass(frozen=True)
class FvgSweepDisplacementStrategy:
    """Independent Strategy 2 detector; it only emits research Setup records."""

    config: Strategy2Config = Strategy2Config()

    def generate_setups(self, frame_1m: pd.DataFrame, *, tick_size: float) -> list[Setup]:
        return strategy2_fvg_sweep_displacement(
            frame_1m, tick_size=tick_size, config=self.config
        )


@dataclass(frozen=True)
class BacktestConfig:
    starting_equity: float = 10_000.0
    risk_fraction: float = 0.01
    daily_drawdown_limit: float = 0.03
    tick_size: float = 0.01
    point_value: float = 1.0
    spread_ticks_round_trip: float = 0.0
    slippage_ticks_round_trip: float = 0.0
    commission_cash_per_unit_round_trip: float = 0.0
    costs_verified: bool = False
    point_value_verified: bool = False
    max_one_position: bool = True
    time_window: TimeWindow = TimeWindow()

    def __post_init__(self) -> None:
        positive = (self.starting_equity, self.risk_fraction, self.daily_drawdown_limit,
                    self.tick_size, self.point_value)
        if not all(isfinite(float(value)) and float(value) > 0 for value in positive):
            raise ValueError("BACKTEST_RISK_CONFIGURATION_INVALID")
        if self.risk_fraction > 0.02:
            raise ValueError("BACKTEST_RISK_FRACTION_ABOVE_2_PERCENT")
        if self.daily_drawdown_limit > 0.03:
            raise ValueError("BACKTEST_DAILY_DRAWDOWN_ABOVE_3_PERCENT")
        costs = (
            self.spread_ticks_round_trip,
            self.slippage_ticks_round_trip,
            self.commission_cash_per_unit_round_trip,
        )
        if not all(isfinite(float(value)) and float(value) >= 0 for value in costs):
            raise ValueError("BACKTEST_COST_INPUT_INVALID")

    @property
    def round_trip_cost_per_unit(self) -> float:
        price_cost = (
            self.spread_ticks_round_trip + self.slippage_ticks_round_trip
        ) * self.tick_size * self.point_value
        return price_cost + self.commission_cash_per_unit_round_trip


@dataclass
class _PendingOrder:
    setup: Setup
    submitted_index: int
    expires_index: int


@dataclass
class _OpenPosition:
    setup: Setup
    entry_index: int
    entry_price: float
    quantity: float
    planned_risk_cash: float
    cost_per_unit: float


def _exit_price(
    direction: str,
    bar: pd.Series,
    stop: float,
    target: float,
    *,
    allow_target: bool = True,
) -> tuple[float | None, str | None]:
    """Conservative OHLC execution: stop wins if both barriers trade."""
    open_price = float(bar["open"])
    high = float(bar["high"])
    low = float(bar["low"])
    if direction == "LONG":
        stop_hit, target_hit = low <= stop, high >= target
        if stop_hit:
            return (min(open_price, stop), "STOP")
        if target_hit and allow_target:
            return (max(open_price, target), "TARGET")
    else:
        stop_hit, target_hit = high >= stop, low <= target
        if stop_hit:
            return (max(open_price, stop), "STOP")
        if target_hit and allow_target:
            return (min(open_price, target), "TARGET")
    return None, None


def simulate(
    frame_1m: pd.DataFrame,
    setups: Sequence[Setup],
    *,
    config: BacktestConfig,
    strategy_id: str,
) -> dict[str, Any]:
    """Sequential OHLC simulator with 1% sizing, 3% daily circuit breaker."""
    data = validate_ohlc(frame_1m)
    if not setups:
        setup_by_index: dict[int, list[Setup]] = {}
    else:
        setup_by_index = {}
        for setup in setups:
            if setup.signal_index < 0 or setup.signal_index >= len(data):
                raise ValueError("SETUP_INDEX_OUT_OF_RANGE")
            if setup.signal_time_utc != (data.index[setup.signal_index] + pd.Timedelta(minutes=1)).isoformat():
                raise ValueError("SETUP_SIGNAL_TIME_DOES_NOT_MATCH_BAR_CLOSE")
            setup_by_index.setdefault(setup.signal_index, []).append(setup)
        for rows in setup_by_index.values():
            rows.sort(key=lambda item: (item.signal_time_utc, item.strategy_id, item.direction))

    balance = float(config.starting_equity)
    high_water = balance
    max_drawdown = 0.0
    day_key: str | None = None
    day_start_equity = balance
    daily_halted = False
    pending: _PendingOrder | None = None
    position: _OpenPosition | None = None
    trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    rejections: dict[str, int] = {
        "DAILY_DRAWDOWN_HALT": 0,
        "ORDER_EXPIRED": 0,
        "ZONE_INVALIDATED_BEFORE_FILL": 0,
        "NO_FILL_BEFORE_CUTOFF": 0,
        "INVALID_RISK_DISTANCE": 0,
        "END_OF_DATA_PENDING": 0,
    }
    active = config.time_window.mask(data.index)
    active_entry = config.time_window.open_mask(data.index)
    local_close = (data.index + pd.Timedelta(minutes=1)).tz_convert(config.time_window.timezone)
    cost_per_unit = config.round_trip_cost_per_unit

    def mark_to_market(close: float) -> float:
        if position is None:
            return balance
        sign = 1.0 if position.setup.direction == "LONG" else -1.0
        gross = sign * (close - position.entry_price) * position.quantity * config.point_value
        estimated_cost = position.cost_per_unit * position.quantity
        return balance + gross - estimated_cost

    def close_position(index: int, price: float, reason: str) -> None:
        nonlocal balance, position
        assert position is not None
        sign = 1.0 if position.setup.direction == "LONG" else -1.0
        gross = sign * (price - position.entry_price) * position.quantity * config.point_value
        total_cost = position.cost_per_unit * position.quantity
        net = gross - total_cost
        balance += net
        r_multiple = net / position.planned_risk_cash if position.planned_risk_cash > 0 else 0.0
        trades.append({
            "strategy_id": position.setup.strategy_id,
            "direction": position.setup.direction,
            "signal_time_utc": position.setup.signal_time_utc,
            "entry_time_utc": data.index[position.entry_index].isoformat(),
            "exit_time_utc": data.index[index].isoformat(),
            "entry_price": position.entry_price,
            "exit_price": float(price),
            "stop_price": position.setup.stop,
            "target_price": position.setup.target,
            "quantity_normalized": position.quantity,
            "planned_risk_cash": position.planned_risk_cash,
            "gross_pnl_cash": gross,
            "estimated_round_trip_cost_cash": total_cost,
            "net_pnl_cash": net,
            "r_multiple_net": r_multiple,
            "exit_reason": reason,
            "planned_rr": position.setup.planned_rr,
            "evidence": list(position.setup.evidence),
        })
        position = None

    for i in range(len(data)):
        row = data.iloc[i]
        session_date = local_close[i].date().isoformat()
        current_mark = mark_to_market(float(row["close"]))
        if session_date != day_key:
            day_key = session_date
            # Mark the daily baseline at the first bar open, so movement during
            # that first minute is counted in the new NY trading day.
            day_start_equity = mark_to_market(float(row["open"]))
            daily_halted = False

        # Manage open position before looking for fresh entries.
        if position is not None:
            exit_price, reason = _exit_price(
                position.setup.direction, row, position.setup.stop, position.setup.target
            )
            if exit_price is not None:
                close_position(i, exit_price, str(reason))
                current_mark = balance
            else:
                current_mark = mark_to_market(float(row["close"]))

        # A pending entry is only eligible on a later candle and within the NY window.
        if pending is not None and position is None:
            setup = pending.setup
            if i > pending.expires_index:
                pending = None
                rejections["ORDER_EXPIRED"] += 1
            elif not active_entry[i]:
                pending = None
                rejections["NO_FILL_BEFORE_CUTOFF"] += 1
            else:
                long_side = setup.direction == "LONG"
                invalid_open = (
                    float(row["open"]) <= setup.invalidation_price if long_side
                    else float(row["open"]) >= setup.invalidation_price
                )
                invalid_close = (
                    float(row["close"]) <= setup.invalidation_price if long_side
                    else float(row["close"]) >= setup.invalidation_price
                )
                if invalid_open or invalid_close:
                    pending = None
                    rejections["ZONE_INVALIDATED_BEFORE_FILL"] += 1
                else:
                    fill: float | None = None
                    gap_fill = (
                        float(row["open"]) <= setup.entry if long_side
                        else float(row["open"]) >= setup.entry
                    )
                    cutoff_open = config.time_window.is_cutoff_open(data.index[i])
                    if long_side:
                        if gap_fill:
                            fill = float(row["open"])
                        elif not cutoff_open and float(row["low"]) <= setup.entry:
                            fill = setup.entry
                    else:
                        if gap_fill:
                            fill = float(row["open"])
                        elif not cutoff_open and float(row["high"]) >= setup.entry:
                            fill = setup.entry
                    if cutoff_open and not gap_fill:
                        pending = None
                        rejections["NO_FILL_BEFORE_CUTOFF"] += 1
                    if fill is not None:
                        stop_distance = abs(fill - setup.stop)
                        risk_per_unit = stop_distance * config.point_value + cost_per_unit
                        risk_cash = balance * config.risk_fraction
                        if stop_distance <= config.tick_size * 0.25 or risk_per_unit <= 0:
                            rejections["INVALID_RISK_DISTANCE"] += 1
                            pending = None
                        else:
                            quantity = risk_cash / risk_per_unit
                            position = _OpenPosition(
                                setup=setup,
                                entry_index=i,
                                entry_price=fill,
                                quantity=quantity,
                                planned_risk_cash=risk_cash,
                                cost_per_unit=cost_per_unit,
                            )
                            pending = None
                            # If entry and stop/target occur in this same OHLC bar,
                            # stop-first is deliberately conservative.
                            # Intrabar entry time is unknown from OHLC. On the
                            # fill candle only a stop may be assumed; a target-only
                            # touch is ignored until a later complete candle.
                            exit_price, reason = _exit_price(
                                setup.direction, row, setup.stop, setup.target,
                                allow_target=False,
                            )
                            if exit_price is not None:
                                close_position(i, exit_price, str(reason))
                                current_mark = balance
                            else:
                                current_mark = mark_to_market(float(row["close"]))

        # Daily circuit breaker uses current marked equity (realized + unrealized).
        daily_drawdown = max(0.0, (day_start_equity - current_mark) / day_start_equity) if day_start_equity > 0 else 1.0
        if daily_drawdown >= config.daily_drawdown_limit:
            if not daily_halted:
                rejections["DAILY_DRAWDOWN_HALT"] += 1
            daily_halted = True
            if pending is not None:
                pending = None

        high_water = max(high_water, current_mark)
        drawdown = (high_water - current_mark) / high_water if high_water > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        equity_rows.append({
            "timestamp_utc": data.index[i],
            "equity_marked": current_mark,
            "balance_realized": balance,
            "daily_drawdown_pct": daily_drawdown,
            "daily_halted": daily_halted,
            "drawdown_from_peak_pct": drawdown,
        })

        # The signal becomes actionable only after this candle closes; it is
        # therefore queued for the next bar, never filled on its signal bar.
        if (
            pending is None and position is None and not daily_halted
            and active[i]
        ):
            candidates = setup_by_index.get(i, [])
            if candidates:
                pending = _PendingOrder(
                    setup=candidates[0],
                    submitted_index=i + 1,
                    expires_index=min(len(data) - 1, i + candidates[0].order_ttl_bars),
                )

    if pending is not None:
        rejections["END_OF_DATA_PENDING"] += 1
    if position is not None:
        close_position(len(data) - 1, float(data["close"].iloc[-1]), "END_OF_DATA_MARK_TO_MARK")
        equity_rows[-1]["equity_marked"] = balance
        equity_rows[-1]["balance_realized"] = balance

    equity = pd.DataFrame(equity_rows).set_index("timestamp_utc")
    trade_frame = pd.DataFrame(trades)
    metrics = calculate_metrics(
        trade_frame,
        equity,
        initial_equity=config.starting_equity,
        timezone=config.time_window.timezone,
    )
    return {
        "schema": "atos.smc.backtest.v1",
        "strategy_id": strategy_id,
        "research_only": True,
        "capital_authority": False,
        "order_submission_permitted": False,
        "live_execution": "BLOCKED",
        "final_execution_authorization": False,
        "metrics": metrics,
        "trade_count": int(len(trade_frame)),
        "trades": trades,
        "rejections": rejections,
        "equity_curve": [
            {**row, "timestamp_utc": pd.Timestamp(timestamp).isoformat()}
            for timestamp, row in equity.to_dict(orient="index").items()
        ],
        "assumptions": {
            **asdict(config),
            "round_trip_cost_per_unit_cash": config.round_trip_cost_per_unit,
            "cost_status": (
                "USER_ASSERTED_VERIFIED_NOT_INDEPENDENTLY_CHECKED"
                if config.costs_verified else "UNVERIFIED_ASSUMPTION"
            ),
            "point_value_status": (
                "USER_ASSERTED_VERIFIED_NOT_INDEPENDENTLY_CHECKED"
                if config.point_value_verified else "NORMALIZED_OR_UNVERIFIED"
            ),
            "max_positions": 1,
            "intrabar_collision_policy": "STOP_FIRST",
            "entry_execution": "NEXT_BAR_LIMIT",
            "unfilled_orders_cancelled_after_ny_cutoff": True,
            "daily_drawdown_uses_marked_equity": True,
        },
    }


def calculate_metrics(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    *,
    initial_equity: float,
    timezone: str = "America/New_York",
) -> dict[str, Any]:
    """Institutional-style trade and equity statistics; no raw win-rate headline."""
    if trades.empty:
        expectancy = profit_factor = sharpe = None
        r_distribution = {"count": 0, "p05": None, "p25": None, "p50": None,
                          "p75": None, "p95": None, "mean": None, "std": None}
        total_net = 0.0
    else:
        pnl = trades["net_pnl_cash"].to_numpy(dtype=float)
        r_values = trades["r_multiple_net"].to_numpy(dtype=float)
        positive = float(pnl[pnl > 0].sum())
        negative = float(abs(pnl[pnl < 0].sum()))
        expectancy = float(np.mean(r_values))
        profit_factor = (positive / negative) if negative > 0 else (None if positive == 0 else None)
        r_distribution = {
            "count": int(len(r_values)),
            "p05": float(np.quantile(r_values, 0.05)),
            "p25": float(np.quantile(r_values, 0.25)),
            "p50": float(np.quantile(r_values, 0.50)),
            "p75": float(np.quantile(r_values, 0.75)),
            "p95": float(np.quantile(r_values, 0.95)),
            "mean": float(np.mean(r_values)),
            "std": float(np.std(r_values, ddof=1)) if len(r_values) > 1 else 0.0,
        }
        total_net = float(pnl.sum())

    if equity.empty:
        max_dd = 0.0
        final_equity = float(initial_equity)
        daily_returns = pd.Series(dtype=float)
    else:
        curve = equity["equity_marked"].astype(float)
        peaks = curve.cummax().clip(lower=initial_equity)
        max_dd = float(((peaks - curve) / peaks).max())
        final_equity = float(curve.iloc[-1])
        local = curve.copy()
        local.index = local.index.tz_convert(timezone)
        daily_equity = local.groupby(local.index.date).last()
        daily_returns = daily_equity.pct_change().dropna()
    if len(daily_returns) > 1 and float(daily_returns.std(ddof=1)) > 0:
        # 365 sessions because synthetic indices are continuously quoted; this
        # annualization is a convention, not evidence of 365 independent days.
        sharpe = float(daily_returns.mean() / daily_returns.std(ddof=1) * sqrt(365.0))
    else:
        sharpe = None
    return {
        "expectancy_r_per_trade": expectancy,
        "profit_factor": profit_factor,
        "maximum_drawdown_pct": max_dd * 100.0,
        "sharpe_daily_annualized_sqrt365": sharpe,
        "r_multiple_distribution": r_distribution,
        "net_pnl_cash_modelled": total_net,
        "initial_equity_modelled": float(initial_equity),
        "final_equity_modelled": final_equity,
        "daily_return_observations": int(len(daily_returns)),
    }


def run_strategy_comparison(
    frame_1m: pd.DataFrame,
    *,
    tick_size: float,
    backtest: BacktestConfig,
    strategy1: Strategy1Config = Strategy1Config(),
    strategy2: Strategy2Config = Strategy2Config(),
) -> dict[str, Any]:
    """Run the two models separately on the same validated 1m input."""
    data = validate_ohlc(frame_1m)
    q = data_quality_report(data)
    s1 = SupplyDemandCHoCHStrategy(strategy1).generate_setups(data, tick_size=tick_size)
    s2 = FvgSweepDisplacementStrategy(strategy2).generate_setups(data, tick_size=tick_size)
    result1 = simulate(
        data, s1, config=backtest, strategy_id="ATOS_S1_SUPPLY_DEMAND_CHOCH"
    )
    result2 = simulate(
        data, s2, config=backtest, strategy_id="ATOS_S2_FVG_SWEEP_DISPLACEMENT"
    )
    return {
        "schema": "atos.smc.comparison.v1",
        "research_only": True,
        "capital_authority": False,
        "order_submission_permitted": False,
        "live_execution": "BLOCKED",
        "symbol": str(data.attrs.get("symbol", "UNSPECIFIED")),
        "timeframe": "1m",
        "higher_timeframe": "15m",
        "time_window": asdict(backtest.time_window),
        "data_quality": q,
        "strategy_1": result1,
        "strategy_2": result2,
        "selection_policy": (
            "NO_AUTOMATIC_WINNER; compare expectancy, profit factor, drawdown, "
            "Sharpe, sample size, cost verification and out-of-sample stability"
        ),
    }
