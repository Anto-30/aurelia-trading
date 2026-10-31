from __future__ import annotations
import asyncio
import hashlib
import json
import math
import random
from bisect import bisect_left
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from statistics import fmean
from typing import Any, Awaitable, Callable, Literal, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
ORDER_SUBMISSION_PERMITTED = False
ENGINE_VERSION = 'layer9-structure-369-v1.0.0'
Direction = Literal['LONG', 'SHORT']
SwingType = Literal['high', 'low']
MissingPolicy = Literal['drop', 'forward_fill']

def _utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        stamp = value
    else:
        try:
            stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (TypeError, ValueError) as exc:
            raise ValueError('TIMESTAMP_INVALID') from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('TIMESTAMP_MUST_BE_TIMEZONE_AWARE')
    return stamp.astimezone(timezone.utc)

def _utc_text(value: str | datetime) -> str:
    return _utc(value).isoformat().replace('+00:00', 'Z')

def _finite_positive(value: float, code: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(code)
    return result

def _finite_nonnegative(value: float, code: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(code)
    return result

@dataclass(frozen=True, slots=True)
class OHLCBar:
    timestamp_utc: str
    open: float
    high: float
    low: float
    close: float
    synthetic: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, 'timestamp_utc', _utc_text(self.timestamp_utc))
        values = tuple((float(x) for x in (self.open, self.high, self.low, self.close)))
        if not all((math.isfinite(x) and x > 0 for x in values)):
            raise ValueError('BAR_PRICES_MUST_BE_FINITE_AND_POSITIVE')
        o, h, l, c = values
        if h < max(o, l, c):
            raise ValueError('BAR_HIGH_INCONSISTENT')
        if l > min(o, h, c):
            raise ValueError('BAR_LOW_INCONSISTENT')
        object.__setattr__(self, 'open', o)
        object.__setattr__(self, 'high', h)
        object.__setattr__(self, 'low', l)
        object.__setattr__(self, 'close', c)

    @property
    def timestamp(self) -> datetime:
        return _utc(self.timestamp_utc)

@dataclass(frozen=True, slots=True)
class StructureConfig:
    pivot_left: int = 2
    pivot_right: int = 2
    atr_lookback: int = 10
    displacement_factor: float = 1.5
    timeframe_seconds: int = 60

    def __post_init__(self) -> None:
        if self.pivot_left < 1 or self.pivot_right < 1:
            raise ValueError('PIVOT_WIDTH_MUST_BE_POSITIVE')
        if self.atr_lookback < 2:
            raise ValueError('ATR_LOOKBACK_TOO_SHORT')
        if not math.isfinite(self.displacement_factor) or self.displacement_factor <= 0:
            raise ValueError('DISPLACEMENT_FACTOR_INVALID')
        if self.timeframe_seconds not in (60, 900):
            raise ValueError('TIMEFRAME_MUST_BE_M1_OR_M15')

@dataclass(frozen=True, slots=True)
class SwingPoint:
    index: int
    confirmed_at_index: int
    price: float
    swing_type: SwingType

@dataclass(frozen=True, slots=True)
class ProtectedSwing:
    swing_index: int
    confirmed_at_index: int
    protected_at_index: int
    price: float
    swing_type: SwingType
    break_direction: Direction
    broken_level_price: float
    displacement_ratio: float

@dataclass(frozen=True, slots=True)
class StructureBreak:
    break_index: int
    break_timestamp_utc: str
    direction: Direction
    broken_swing_index: int
    broken_level_price: float
    protected_swing: ProtectedSwing
    body_size: float
    prior_atr: float
    displacement_ratio: float

def _validate_bars(bars: Sequence[OHLCBar]) -> None:
    previous: datetime | None = None
    for bar in bars:
        if not isinstance(bar, OHLCBar):
            raise ValueError('OHLC_BAR_TYPE_INVALID')
        stamp = bar.timestamp
        if previous is not None and stamp <= previous:
            raise ValueError('BAR_TIMESTAMPS_MUST_BE_STRICTLY_INCREASING')
        previous = stamp

def _contiguous(bars: Sequence[OHLCBar], start: int, end: int, interval: int) -> bool:
    if start < 0 or end >= len(bars) or start > end:
        return False
    if any((bars[i].synthetic for i in range(start, end + 1))):
        return False
    return all(((bars[i].timestamp - bars[i - 1].timestamp).total_seconds() == interval for i in range(start + 1, end + 1)))

def _true_range(bars: Sequence[OHLCBar], index: int) -> float:
    bar = bars[index]
    if index == 0:
        return bar.high - bar.low
    previous_close = bars[index - 1].close
    return max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close))

def calculate_atr(bars: Sequence[OHLCBar], index: int, period: int=10, timeframe_seconds: int=60) -> float | None:
    if period < 2:
        raise ValueError('ATR_LOOKBACK_TOO_SHORT')
    start = index - period
    end = index - 1
    if start < 0:
        return None
    continuity_start = start - 1 if start > 0 else start
    if not _contiguous(bars, continuity_start, end, timeframe_seconds):
        return None
    return fmean((_true_range(bars, i) for i in range(start, index)))

def _pivot_at(bars: Sequence[OHLCBar], pivot_index: int, left: int, right: int, swing_type: SwingType, interval: int) -> bool:
    start, end = (pivot_index - left, pivot_index + right)
    if not _contiguous(bars, start, end, interval):
        return False
    candidate = bars[pivot_index].high if swing_type == 'high' else bars[pivot_index].low
    values = [bars[i].high if swing_type == 'high' else bars[i].low for i in range(start, end + 1) if i != pivot_index]
    return candidate > max(values) if swing_type == 'high' else candidate < min(values)

def detect_protected_swings(bars: Sequence[OHLCBar], *, config: StructureConfig=StructureConfig()) -> list[StructureBreak]:
    _validate_bars(bars)
    highs: list[SwingPoint] = []
    lows: list[SwingPoint] = []
    consumed_highs: set[int] = set()
    consumed_lows: set[int] = set()
    events: list[StructureBreak] = []
    interval = config.timeframe_seconds
    for i, bar in enumerate(bars):
        if i and ((bar.timestamp - bars[i - 1].timestamp).total_seconds() != interval or bar.synthetic or bars[i - 1].synthetic):
            highs.clear()
            lows.clear()
            consumed_highs.clear()
            consumed_lows.clear()
        if bar.synthetic:
            continue
        pivot_index = i - config.pivot_right
        if pivot_index >= config.pivot_left:
            if _pivot_at(bars, pivot_index, config.pivot_left, config.pivot_right, 'high', interval):
                highs.append(SwingPoint(pivot_index, i, bars[pivot_index].high, 'high'))
            if _pivot_at(bars, pivot_index, config.pivot_left, config.pivot_right, 'low', interval):
                lows.append(SwingPoint(pivot_index, i, bars[pivot_index].low, 'low'))
        if i == 0:
            continue
        previous_close = bars[i - 1].close
        latest_high = next((x for x in reversed(highs) if x.index not in consumed_highs), None)
        latest_low = next((x for x in reversed(lows) if x.index not in consumed_lows), None)
        bullish_cross = bool(latest_high and previous_close <= latest_high.price < bar.close and (bar.close > bar.open))
        bearish_cross = bool(latest_low and previous_close >= latest_low.price > bar.close and (bar.close < bar.open))
        if not bullish_cross and (not bearish_cross):
            continue
        if bullish_cross and latest_high:
            consumed_highs.add(latest_high.index)
        if bearish_cross and latest_low:
            consumed_lows.add(latest_low.index)
        atr = calculate_atr(bars, i, config.atr_lookback, interval)
        if atr is None or atr <= 0:
            continue
        body = abs(bar.close - bar.open)
        if body <= config.displacement_factor * atr:
            continue
        ratio = body / atr
        if bullish_cross and latest_high:
            candidates = [x for x in lows if x.index > latest_high.index and x.confirmed_at_index < i]
            protected = next((x for x in reversed(candidates) if x.index not in consumed_lows and _contiguous(bars, x.confirmed_at_index, i, interval) and (not any((bars[j].close < x.price for j in range(x.confirmed_at_index + 1, i))))), None)
            if protected is not None:
                protected_swing = ProtectedSwing(protected.index, protected.confirmed_at_index, i, protected.price, 'low', 'LONG', latest_high.price, ratio)
                events.append(StructureBreak(i, _utc_text(bar.timestamp + timedelta(seconds=interval)), 'LONG', latest_high.index, latest_high.price, protected_swing, body, atr, ratio))
        elif bearish_cross and latest_low:
            candidates = [x for x in highs if x.index > latest_low.index and x.confirmed_at_index < i]
            protected = next((x for x in reversed(candidates) if x.index not in consumed_highs and _contiguous(bars, x.confirmed_at_index, i, interval) and (not any((bars[j].close > x.price for j in range(x.confirmed_at_index + 1, i))))), None)
            if protected is not None:
                protected_swing = ProtectedSwing(protected.index, protected.confirmed_at_index, i, protected.price, 'high', 'SHORT', latest_low.price, ratio)
                events.append(StructureBreak(i, _utc_text(bar.timestamp + timedelta(seconds=interval)), 'SHORT', latest_low.index, latest_low.price, protected_swing, body, atr, ratio))
    return events

def protected_swings_from_breaks(events: Sequence[StructureBreak]) -> list[ProtectedSwing]:
    return [event.protected_swing for event in events]

@dataclass(slots=True)
class FairValueGap:
    created_index: int
    created_at_utc: str
    top: float
    bottom: float
    midpoint: float
    direction: Direction
    mitigated_index: int | None = None
    mitigated_at_utc: str | None = None
    stale_data_gap_index: int | None = None
    stale_data_gap_at_utc: str | None = None

    @property
    def is_mitigated(self) -> bool:
        return self.mitigated_index is not None

    @property
    def is_stale(self) -> bool:
        return self.stale_data_gap_index is not None

    @property
    def is_active(self) -> bool:
        return not self.is_mitigated and (not self.is_stale)

def _fvg_at(bars: Sequence[OHLCBar], index: int, timeframe_seconds: int) -> FairValueGap | None:
    if index < 2 or not _contiguous(bars, index - 2, index, timeframe_seconds):
        return None
    first, third = (bars[index - 2], bars[index])
    if first.high < third.low:
        bottom, top = (first.high, third.low)
        return FairValueGap(index, _utc_text(third.timestamp + timedelta(seconds=timeframe_seconds)), top, bottom, (top + bottom) / 2.0, 'LONG')
    if first.low > third.high:
        bottom, top = (third.high, first.low)
        return FairValueGap(index, _utc_text(third.timestamp + timedelta(seconds=timeframe_seconds)), top, bottom, (top + bottom) / 2.0, 'SHORT')
    return None

def scan_and_track_fvgs(bars: Sequence[OHLCBar], *, timeframe_seconds: int=60) -> list[FairValueGap]:
    _validate_bars(bars)
    fvgs: list[FairValueGap] = []
    active: list[FairValueGap] = []
    for i, bar in enumerate(bars):
        if bar.synthetic or (i and (bar.timestamp - bars[i - 1].timestamp).total_seconds() != timeframe_seconds):
            stale_time = _utc_text(bar.timestamp + timedelta(seconds=timeframe_seconds))
            for gap in active:
                if gap.is_active:
                    gap.stale_data_gap_index = i
                    gap.stale_data_gap_at_utc = stale_time
            active.clear()
        for gap in active:
            if gap.is_mitigated:
                continue
            touched = bar.low <= gap.midpoint if gap.direction == 'LONG' else bar.high >= gap.midpoint
            if touched:
                gap.mitigated_index = i
                gap.mitigated_at_utc = _utc_text(bar.timestamp + timedelta(seconds=timeframe_seconds))
        if not bar.synthetic:
            new_gap = _fvg_at(bars, i, timeframe_seconds)
            if new_gap is not None:
                fvgs.append(new_gap)
                active.append(new_gap)
    return fvgs

def active_fvgs_at(bars: Sequence[OHLCBar], as_of_index: int, *, timeframe_seconds: int=60) -> list[FairValueGap]:
    if as_of_index < 0 or as_of_index >= len(bars):
        raise IndexError('AS_OF_INDEX_OUT_OF_RANGE')
    tracked = scan_and_track_fvgs(bars[:as_of_index + 1], timeframe_seconds=timeframe_seconds)
    return [gap for gap in tracked if gap.created_index < as_of_index and gap.is_active]

@dataclass(frozen=True, slots=True)
class SessionWindow:
    name: str
    timezone_name: str
    start: time
    end: time

    def __post_init__(self) -> None:
        try:
            ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError('SESSION_TIMEZONE_UNKNOWN') from exc
        if self.start == self.end:
            raise ValueError('SESSION_WINDOW_CANNOT_BE_24_HOURS')

    def contains(self, timestamp_utc: str | datetime) -> bool:
        local = _utc(timestamp_utc).astimezone(ZoneInfo(self.timezone_name)).timetz().replace(tzinfo=None)
        if self.start <= self.end:
            return self.start <= local <= self.end
        return local >= self.start or local <= self.end
NY_AM_SESSION = SessionWindow('NY_AM', 'America/New_York', time(7, 20), time(10, 45))

def is_in_session(timestamp_utc: str | datetime, sessions: Sequence[SessionWindow]=(NY_AM_SESSION,)) -> bool:
    return any((session.contains(timestamp_utc) for session in sessions))

@dataclass(frozen=True, slots=True)
class SweepEvent:
    index: int
    event_timestamp_utc: str
    direction: Direction
    sweep_extreme: float
    swept_protected_swing: ProtectedSwing

    @property
    def reference_swing_price(self) -> float:
        return self.swept_protected_swing.price

def detect_m15_sweeps(bars: Sequence[OHLCBar], *, structure_config: StructureConfig=StructureConfig(timeframe_seconds=900)) -> list[SweepEvent]:
    _validate_bars(bars)
    if structure_config.timeframe_seconds != 900:
        raise ValueError('M15_STRUCTURE_CONFIG_REQUIRED')
    protected = protected_swings_from_breaks(detect_protected_swings(bars, config=structure_config))
    consumed: set[tuple[int, SwingType]] = set()
    events: list[SweepEvent] = []
    for i, bar in enumerate(bars):
        if bar.synthetic:
            continue
        eligible = [p for p in protected if p.protected_at_index < i and (p.swing_index, p.swing_type) not in consumed and _contiguous(bars, p.protected_at_index, i, 900)]
        for level in eligible:
            if level.swing_type == 'high' and bar.close > level.price or (level.swing_type == 'low' and bar.close < level.price):
                consumed.add((level.swing_index, level.swing_type))
        eligible = [p for p in eligible if (p.swing_index, p.swing_type) not in consumed]
        high_level = next((p for p in reversed(eligible) if p.swing_type == 'high'), None)
        low_level = next((p for p in reversed(eligible) if p.swing_type == 'low'), None)
        high_swept = bool(high_level and bar.high > high_level.price and (bar.close < high_level.price))
        low_swept = bool(low_level and bar.low < low_level.price and (bar.close > low_level.price))
        if high_swept and low_swept:
            if high_level:
                consumed.add((high_level.swing_index, 'high'))
            if low_level:
                consumed.add((low_level.swing_index, 'low'))
            continue
        if low_swept and low_level:
            events.append(SweepEvent(i, _utc_text(bar.timestamp + timedelta(seconds=900)), 'LONG', bar.low, low_level))
            consumed.add((low_level.swing_index, 'low'))
        elif high_swept and high_level:
            events.append(SweepEvent(i, _utc_text(bar.timestamp + timedelta(seconds=900)), 'SHORT', bar.high, high_level))
            consumed.add((high_level.swing_index, 'high'))
    return events

def find_m1_mss_after_sweep(m1_bars: Sequence[OHLCBar], sweep: SweepEvent, *, n_bars: int, structure_config: StructureConfig=StructureConfig(timeframe_seconds=60)) -> StructureBreak | None:
    _validate_bars(m1_bars)
    if n_bars < 1:
        raise ValueError('M1_MSS_WINDOW_MUST_BE_POSITIVE')
    if structure_config.timeframe_seconds != 60:
        raise ValueError('M1_STRUCTURE_CONFIG_REQUIRED')
    start_time = _utc(sweep.event_timestamp_utc)
    timestamps = [bar.timestamp for bar in m1_bars]
    start_index = bisect_left(timestamps, start_time)
    if start_index >= len(m1_bars) or m1_bars[start_index].timestamp != start_time:
        return None
    end_index = min(len(m1_bars), start_index + n_bars)
    events = detect_protected_swings(m1_bars, config=structure_config)
    by_index = {event.break_index: event for event in events}
    for i in range(start_index, end_index):
        bar = m1_bars[i]
        if bar.synthetic:
            return None
        if i > start_index and (bar.timestamp - m1_bars[i - 1].timestamp).total_seconds() != 60:
            return None
        invalidated = bar.close < sweep.sweep_extreme if sweep.direction == 'LONG' else bar.close > sweep.sweep_extreme
        if invalidated:
            return None
        event = by_index.get(i)
        if event and event.direction == sweep.direction:
            return event
    return None

@dataclass(frozen=True, slots=True)
class Instrument369Spec:
    symbol: str
    price_quantum: float
    step_unit: float
    tick_size: float
    tolerance_ticks: float = 1.0
    levels_each_side: int = 10
    metadata_verified: bool = False
    metadata_evidence_sha256: str | None = None
    metadata_source_uri: str | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError('369_SYMBOL_REQUIRED')
        _finite_positive(self.price_quantum, '369_PRICE_QUANTUM_INVALID')
        _finite_positive(self.step_unit, '369_STEP_UNIT_INVALID')
        _finite_positive(self.tick_size, '369_TICK_SIZE_INVALID')
        _finite_nonnegative(self.tolerance_ticks, '369_TOLERANCE_INVALID')
        if self.levels_each_side < 1:
            raise ValueError('369_LEVEL_COUNT_MUST_BE_POSITIVE')
        if self.metadata_verified and (not self.metadata_source_uri or not self.metadata_source_uri.strip() or len(self.metadata_evidence_sha256 or '') != 64 or any((ch not in '0123456789abcdef' for ch in (self.metadata_evidence_sha256 or '').lower()))):
            raise ValueError('369_INSTRUMENT_METADATA_EVIDENCE_INCOMPLETE')

def _digital_root(nonnegative_integer: int) -> int:
    if nonnegative_integer < 1:
        raise ValueError('369_NORMALIZED_PRICE_MUST_BE_AT_LEAST_ONE')
    return 1 + (nonnegative_integer - 1) % 9

def calculate_369_step(price: float, *, price_quantum: float=1.0, step_unit: float=1.0) -> float:
    price_value = _finite_positive(price, '369_REFERENCE_PRICE_INVALID')
    quantum = _finite_positive(price_quantum, '369_PRICE_QUANTUM_INVALID')
    unit = _finite_positive(step_unit, '369_STEP_UNIT_INVALID')
    normalized = int(Decimal(str(price_value)) / Decimal(str(quantum)))
    root = _digital_root(normalized)
    base_step = 12 if root in (1, 4, 7) else 15 if root in (2, 5, 8) else 18
    return float(Decimal(base_step) * Decimal(str(unit)))

def project_369_levels(reference_swing_price: float, spec: Instrument369Spec, *, levels_each_side: int | None=None) -> tuple[float, ...]:
    count = spec.levels_each_side if levels_each_side is None else levels_each_side
    if count < 1:
        raise ValueError('369_LEVEL_COUNT_MUST_BE_POSITIVE')
    step = calculate_369_step(reference_swing_price, price_quantum=spec.price_quantum, step_unit=spec.step_unit)
    reference = Decimal(str(_finite_positive(reference_swing_price, '369_REFERENCE_PRICE_INVALID')))
    tick = Decimal(str(spec.tick_size))
    levels: set[float] = set()
    for multiple in range(1, count + 1):
        offset = Decimal(str(step)) * multiple
        for raw in (reference - offset, reference + offset):
            if raw > 0:
                quantized = (raw / tick).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * tick
                levels.add(float(quantized))
    return tuple(sorted(levels))

def is_price_at_369_level(price: float, reference_swing_price: float, spec: Instrument369Spec) -> bool:
    current = _finite_positive(price, '369_TEST_PRICE_INVALID')
    tolerance = spec.tick_size * spec.tolerance_ticks
    return any((abs(current - level) <= tolerance for level in project_369_levels(reference_swing_price, spec)))
DERIV_PUBLIC_MARKET_DATA_ENDPOINT = 'wss://api.derivws.com/trading/v1/options/ws/public'
DERIV_TICKS_HISTORY_DOCS = 'https://developers.deriv.com/docs/data/ticks-history/'

@dataclass(frozen=True, slots=True)
class DerivHistoryManifest:
    provider: str
    symbol: str
    granularity_seconds: int
    requested_start_epoch: int
    requested_end_epoch: int
    content_sha256: str
    request_count: int
    source_uri: str
    source_verified: bool = False
    acquisition_evidence_sha256: str | None = None
    source_attestation_id: str | None = None
    endpoint_uri: str = 'wss://api.derivws.com/trading/v1/options/ws/public'

@dataclass(frozen=True, slots=True)
class DerivHistoryResult:
    bars: tuple[OHLCBar, ...]
    manifest: DerivHistoryManifest

def hash_bars(bars: Sequence[OHLCBar]) -> str:
    canonical = [[bar.timestamp_utc, format(bar.open, '.12g'), format(bar.high, '.12g'), format(bar.low, '.12g'), format(bar.close, '.12g'), bool(bar.synthetic)] for bar in bars]
    payload = json.dumps(canonical, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def normalize_deriv_candle_payload(payload: Mapping[str, Any], *, symbol: str, granularity_seconds: int, start_epoch: int | None=None, end_epoch: int | None=None, missing_policy: MissingPolicy='drop') -> list[OHLCBar]:
    if granularity_seconds not in (60, 900):
        raise ValueError('DERIV_GRANULARITY_NOT_SUPPORTED_FOR_LAYER9')
    if missing_policy not in ('drop', 'forward_fill'):
        raise ValueError('MISSING_CANDLE_POLICY_INVALID')
    for epoch, label in ((start_epoch, 'START'), (end_epoch, 'END')):
        if epoch is not None and (epoch < 0 or epoch % granularity_seconds):
            raise ValueError(f'DERIV_REQUEST_{label}_NOT_GRANULARITY_ALIGNED')
    if start_epoch is not None and end_epoch is not None and (end_epoch < start_epoch):
        raise ValueError('DERIV_REQUEST_WINDOW_INVALID')
    if payload.get('error'):
        raise ValueError('DERIV_API_ERROR')
    echo = payload.get('echo_req')
    if not isinstance(echo, Mapping):
        raise ValueError('DERIV_RESPONSE_ECHO_MISSING')
    if echo.get('ticks_history') != symbol:
        raise ValueError('DERIV_RESPONSE_SYMBOL_MISMATCH')
    if echo.get('style') != 'candles':
        raise ValueError('DERIV_RESPONSE_STYLE_MISMATCH')
    if echo.get('granularity') != granularity_seconds:
        raise ValueError('DERIV_RESPONSE_GRANULARITY_MISMATCH')
    if start_epoch is not None and echo.get('start') is not None:
        if int(echo['start']) != start_epoch:
            raise ValueError('DERIV_RESPONSE_START_MISMATCH')
    if end_epoch is not None and echo.get('end') is not None:
        try:
            echoed_end = int(echo['end'])
        except (TypeError, ValueError) as exc:
            raise ValueError('DERIV_RESPONSE_END_INVALID') from exc
        if echoed_end != end_epoch:
            raise ValueError('DERIV_RESPONSE_END_MISMATCH')
    if payload.get('msg_type') != 'candles':
        raise ValueError('DERIV_RESPONSE_MESSAGE_TYPE_MISMATCH')
    raw = payload.get('candles')
    if not isinstance(raw, list) or not raw:
        raise ValueError('DERIV_CANDLE_RESPONSE_EMPTY_OR_INVALID')
    parsed: list[tuple[int, OHLCBar]] = []
    seen: set[int] = set()
    for row in raw:
        if not isinstance(row, Mapping):
            raise ValueError('DERIV_CANDLE_ROW_INVALID')
        try:
            epoch_value = row['epoch']
            if isinstance(epoch_value, bool) or not isinstance(epoch_value, int):
                raise ValueError('DERIV_CANDLE_EPOCH_NOT_INTEGER')
            epoch = epoch_value
            bar = OHLCBar(datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(), float(row['open']), float(row['high']), float(row['low']), float(row['close']))
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError('DERIV_CANDLE_ROW_INVALID') from exc
        if epoch in seen:
            raise ValueError('DERIV_DUPLICATE_CANDLE_EPOCH')
        seen.add(epoch)
        if start_epoch is not None and epoch < start_epoch:
            raise ValueError('DERIV_CANDLE_BEFORE_REQUEST_WINDOW')
        if end_epoch is not None and epoch > end_epoch:
            raise ValueError('DERIV_CANDLE_AFTER_REQUEST_WINDOW')
        parsed.append((epoch, bar))
    parsed.sort(key=lambda x: x[0])
    ordered = [bar for _, bar in parsed]
    previous_epoch: int | None = None
    for epoch, _bar in parsed:
        if epoch % granularity_seconds != 0:
            raise ValueError('DERIV_CANDLE_EPOCH_NOT_ALIGNED_TO_GRANULARITY')
        if previous_epoch is not None:
            delta = epoch - previous_epoch
            if delta <= 0 or delta % granularity_seconds != 0:
                raise ValueError('DERIV_CANDLE_INTERVAL_IRREGULAR')
        previous_epoch = epoch
    if missing_policy == 'drop':
        return ordered
    filled: list[OHLCBar] = []
    for bar in ordered:
        if filled:
            prev_epoch = int(filled[-1].timestamp.timestamp())
            current_epoch = int(bar.timestamp.timestamp())
            missing = (current_epoch - prev_epoch) // granularity_seconds - 1
            if missing < 0:
                raise ValueError('DERIV_CANDLE_ORDER_INVALID')
            for step in range(1, missing + 1):
                stamp = datetime.fromtimestamp(prev_epoch + step * granularity_seconds, tz=timezone.utc).isoformat()
                last = filled[-1].close
                filled.append(OHLCBar(stamp, last, last, last, last, synthetic=True))
        filled.append(bar)
    if end_epoch is not None and filled:
        last_epoch = int(filled[-1].timestamp.timestamp())
        for stamp_epoch in range(last_epoch + granularity_seconds, end_epoch + 1, granularity_seconds):
            last = filled[-1].close
            stamp = datetime.fromtimestamp(stamp_epoch, tz=timezone.utc).isoformat()
            filled.append(OHLCBar(stamp, last, last, last, last, synthetic=True))
    return filled

async def fetch_deriv_history(request: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]], *, symbol: str, start_epoch: int, end_epoch: int, granularity_seconds: int, batch_count: int=1000, missing_policy: MissingPolicy='drop', source_verified: bool=False, source_uri: str=DERIV_TICKS_HISTORY_DOCS, source_attestation_id: str | None=None, endpoint_uri: str=DERIV_PUBLIC_MARKET_DATA_ENDPOINT) -> DerivHistoryResult:
    if granularity_seconds not in (60, 900):
        raise ValueError('DERIV_GRANULARITY_NOT_SUPPORTED_FOR_LAYER9')
    if not symbol or not symbol.strip():
        raise ValueError('DERIV_SYMBOL_REQUIRED')
    if start_epoch < 0 or end_epoch <= start_epoch:
        raise ValueError('DERIV_REQUEST_WINDOW_INVALID')
    if start_epoch % granularity_seconds or end_epoch % granularity_seconds:
        raise ValueError('DERIV_REQUEST_WINDOW_NOT_GRANULARITY_ALIGNED')
    if not 1 <= batch_count <= 1000:
        raise ValueError('DERIV_BATCH_COUNT_OUT_OF_RANGE')
    if missing_policy not in ('drop', 'forward_fill'):
        raise ValueError('MISSING_CANDLE_POLICY_INVALID')
    if source_verified and (endpoint_uri != DERIV_PUBLIC_MARKET_DATA_ENDPOINT or not source_attestation_id or (not source_attestation_id.strip())):
        raise ValueError('DERIV_SOURCE_ATTESTATION_INCOMPLETE')
    all_bars: dict[int, OHLCBar] = {}
    acquisition_rows: list[dict[str, Any]] = []
    cursor = start_epoch
    request_count = 0
    max_pages = math.ceil((end_epoch - start_epoch + 1) / (batch_count * granularity_seconds)) + 3
    while cursor <= end_epoch:
        if request_count >= max_pages:
            raise ValueError('DERIV_PAGINATION_PAGE_LIMIT_EXCEEDED')
        chunk_end = min(end_epoch, cursor + (batch_count - 1) * granularity_seconds)
        payload = {'ticks_history': symbol, 'style': 'candles', 'granularity': granularity_seconds, 'start': int(cursor), 'end': str(int(chunk_end))}
        response = await request(payload)
        request_count += 1
        try:
            response_bytes = json.dumps(response, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False, default=str).encode('utf-8')
        except (TypeError, ValueError) as exc:
            raise ValueError('DERIV_RESPONSE_NOT_CANONICAL_JSON') from exc
        acquisition_rows.append({'request': payload, 'response_sha256': hashlib.sha256(response_bytes).hexdigest()})
        if response.get('error'):
            raise ValueError('DERIV_API_ERROR')
        rows = response.get('candles')
        if rows:
            page_bars = normalize_deriv_candle_payload(response, symbol=symbol, granularity_seconds=granularity_seconds, start_epoch=cursor, end_epoch=chunk_end, missing_policy='drop')
            for bar in page_bars:
                epoch = int(bar.timestamp.timestamp())
                previous = all_bars.get(epoch)
                if previous is not None and previous != bar:
                    raise ValueError('DERIV_OVERLAPPING_PAGE_CONFLICT')
                all_bars[epoch] = bar
        cursor = chunk_end + granularity_seconds
    if not all_bars:
        raise ValueError('DERIV_HISTORY_NO_CANDLES_RETURNED')
    ordered = [all_bars[k] for k in sorted(all_bars)]
    if missing_policy == 'forward_fill':
        ordered = normalize_deriv_candle_payload({'echo_req': {'ticks_history': symbol, 'style': 'candles', 'granularity': granularity_seconds, 'start': int(start_epoch), 'end': str(int(end_epoch))}, 'msg_type': 'candles', 'candles': [{'epoch': int(b.timestamp.timestamp()), 'open': b.open, 'high': b.high, 'low': b.low, 'close': b.close} for b in ordered]}, symbol=symbol, granularity_seconds=granularity_seconds, start_epoch=start_epoch, end_epoch=end_epoch, missing_policy='forward_fill')
    acquisition_payload = json.dumps(acquisition_rows, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    acquisition_hash = hashlib.sha256(acquisition_payload).hexdigest()
    manifest = DerivHistoryManifest('Deriv', symbol, granularity_seconds, int(start_epoch), int(end_epoch), hash_bars(ordered), request_count, source_uri, bool(source_verified), acquisition_hash, source_attestation_id, endpoint_uri)
    return DerivHistoryResult(tuple(ordered), manifest)

async def fetch_deriv_history_from_websocket(*, symbol: str, start_epoch: int, end_epoch: int, granularity_seconds: int, batch_count: int=1000, missing_policy: MissingPolicy='drop', source_verified: bool=False, source_attestation_id: str | None=None, endpoint_uri: str=DERIV_PUBLIC_MARKET_DATA_ENDPOINT, request_timeout_seconds: float=20.0) -> DerivHistoryResult:
    if endpoint_uri != DERIV_PUBLIC_MARKET_DATA_ENDPOINT:
        raise ValueError('DERIV_PUBLIC_RESEARCH_ENDPOINT_MISMATCH')
    if not math.isfinite(request_timeout_seconds) or request_timeout_seconds <= 0:
        raise ValueError('DERIV_REQUEST_TIMEOUT_INVALID')
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError('WEBSOCKETS_DEPENDENCY_REQUIRED') from exc
    async with websockets.connect(endpoint_uri, open_timeout=request_timeout_seconds, close_timeout=10, ping_interval=20, ping_timeout=20, max_size=2 ** 20) as websocket:

        async def request(payload: dict[str, Any]) -> Mapping[str, Any]:
            await websocket.send(json.dumps(payload, separators=(',', ':')))
            raw = await asyncio.wait_for(websocket.recv(), timeout=request_timeout_seconds)
            try:
                response = json.loads(raw)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError('DERIV_RESPONSE_JSON_INVALID') from exc
            if not isinstance(response, Mapping):
                raise ValueError('DERIV_RESPONSE_SCHEMA_INVALID')
            return response
        return await fetch_deriv_history(request, symbol=symbol, start_epoch=start_epoch, end_epoch=end_epoch, granularity_seconds=granularity_seconds, batch_count=batch_count, missing_policy=missing_policy, source_verified=source_verified, source_attestation_id=source_attestation_id, endpoint_uri=endpoint_uri)

@dataclass(frozen=True, slots=True)
class ExperimentDataset:
    symbol: str
    m1: DerivHistoryManifest
    m15: DerivHistoryManifest

    @property
    def combined_sha256(self) -> str:
        payload = f'{self.m1.content_sha256}:{self.m15.content_sha256}'
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def validate_experiment_dataset(m1_bars: Sequence[OHLCBar], m15_bars: Sequence[OHLCBar], dataset: ExperimentDataset, *, minimum_history_days: int=183) -> None:
    _validate_bars(m1_bars)
    _validate_bars(m15_bars)
    if minimum_history_days < 1:
        raise ValueError('MINIMUM_HISTORY_DAYS_INVALID')
    for bars, manifest, expected in ((m1_bars, dataset.m1, 60), (m15_bars, dataset.m15, 900)):
        if manifest.provider != 'Deriv' or not manifest.source_verified:
            raise ValueError('DERIV_SOURCE_VERIFICATION_REQUIRED')
        if manifest.endpoint_uri != DERIV_PUBLIC_MARKET_DATA_ENDPOINT or not manifest.source_attestation_id or (not manifest.source_attestation_id.strip()) or (not manifest.acquisition_evidence_sha256) or (len(manifest.acquisition_evidence_sha256) != 64) or any((ch not in '0123456789abcdef' for ch in manifest.acquisition_evidence_sha256.lower())):
            raise ValueError('DERIV_SOURCE_EVIDENCE_INCOMPLETE')
        if manifest.symbol != dataset.symbol or manifest.granularity_seconds != expected:
            raise ValueError('DERIV_DATASET_MANIFEST_MISMATCH')
        if not bars or hash_bars(bars) != manifest.content_sha256:
            raise ValueError('DERIV_DATASET_HASH_MISMATCH')
        if manifest.request_count < 1 or manifest.requested_end_epoch <= manifest.requested_start_epoch:
            raise ValueError('DERIV_DATASET_REQUEST_MANIFEST_INVALID')
        first_epoch = int(bars[0].timestamp.timestamp())
        last_epoch = int(bars[-1].timestamp.timestamp())
        if first_epoch != manifest.requested_start_epoch or last_epoch != manifest.requested_end_epoch:
            raise ValueError('DERIV_DATASET_REQUEST_WINDOW_COVERAGE_FAILED')
        if any((bar.synthetic for bar in bars)):
            raise ValueError('DERIV_SYNTHETIC_CANDLES_NOT_ALLOWED_FOR_EXPERIMENT')
        if any(((bars[i].timestamp - bars[i - 1].timestamp).total_seconds() != expected for i in range(1, len(bars)))):
            raise ValueError('DERIV_DATASET_CONTINUITY_FAILED')
        if last_epoch - first_epoch < minimum_history_days * 86400:
            raise ValueError('DERIV_HISTORY_WINDOW_TOO_SHORT')
    overlap_start = max(m1_bars[0].timestamp, m15_bars[0].timestamp)
    overlap_end = min(m1_bars[-1].timestamp, m15_bars[-1].timestamp)
    if (overlap_end - overlap_start).total_seconds() < minimum_history_days * 86400:
        raise ValueError('DERIV_M1_M15_OVERLAP_TOO_SHORT')

@dataclass(frozen=True, slots=True)
class CandidateSetup:
    sweep: SweepEvent
    mss: StructureBreak
    fvg: FairValueGap
    entry_index: int
    entry_price: float
    three69_aligned: bool

@dataclass(frozen=True, slots=True)
class TradeRecord:
    trade_id: str
    group: str
    symbol: str
    direction: Direction
    signal_timestamp_utc: str
    sweep_timestamp_utc: str
    mss_timestamp_utc: str
    fvg_created_timestamp_utc: str
    entry_timestamp_utc: str
    exit_timestamp_utc: str
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_price: float
    r_multiple: float
    net_r_multiple: float | None
    exit_reason: str
    protected_swing_price: float
    three69_aligned: bool
    dataset_sha256: str
TRADE_COLUMNS = ('trade_id', 'group', 'symbol', 'direction', 'signal_timestamp_utc', 'sweep_timestamp_utc', 'mss_timestamp_utc', 'fvg_created_timestamp_utc', 'entry_timestamp_utc', 'exit_timestamp_utc', 'entry_price', 'stop_loss', 'take_profit', 'exit_price', 'r_multiple', 'net_r_multiple', 'exit_reason', 'protected_swing_price', 'three69_aligned', 'dataset_sha256')
CRITICAL_TRADE_COLUMNS = ('trade_id', 'group', 'symbol', 'direction', 'signal_timestamp_utc', 'sweep_timestamp_utc', 'mss_timestamp_utc', 'fvg_created_timestamp_utc', 'entry_timestamp_utc', 'exit_timestamp_utc', 'entry_price', 'stop_loss', 'take_profit', 'exit_price', 'r_multiple', 'exit_reason', 'protected_swing_price', 'dataset_sha256')

@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    symbol: str
    instrument_369: Instrument369Spec
    m1_mss_window_bars: int
    max_holding_bars: int
    structure_m15: StructureConfig = field(default_factory=lambda: StructureConfig(timeframe_seconds=900))
    structure_m1: StructureConfig = field(default_factory=StructureConfig)
    sessions: tuple[SessionWindow, ...] = (NY_AM_SESSION,)
    max_fvg_wait_bars: int = 30
    take_profit_r: float = 2.0
    stop_buffer_ticks: float = 1.0
    cost_per_trade_r: float | None = None
    cost_model_id: str | None = None
    cost_model_evidence_sha256: str | None = None
    cost_model_verified: bool = False
    hypothesis_id: str = 'HYP-L9-369-VS-STRUCTURE-001'
    minimum_history_days: int = 183
    minimum_test_trades: int = 201
    minimum_expectancy_improvement_r: float = 0.1
    bootstrap_iterations: int = 2000
    bootstrap_block_days: int = 5
    confidence_level: float = 0.95
    random_seed: int = 369

    def __post_init__(self) -> None:
        if not self.symbol.strip() or self.instrument_369.symbol != self.symbol:
            raise ValueError('EXPERIMENT_SYMBOL_SPEC_MISMATCH')
        if self.m1_mss_window_bars < 1 or self.max_holding_bars < 1:
            raise ValueError('EXPERIMENT_BAR_LIMIT_INVALID')
        if self.max_fvg_wait_bars < 1:
            raise ValueError('FVG_WAIT_LIMIT_INVALID')
        if not math.isfinite(self.take_profit_r) or self.take_profit_r <= 0:
            raise ValueError('TAKE_PROFIT_R_INVALID')
        if not math.isfinite(self.stop_buffer_ticks) or self.stop_buffer_ticks < 0:
            raise ValueError('STOP_BUFFER_TICKS_INVALID')
        if self.cost_per_trade_r is not None and (not math.isfinite(self.cost_per_trade_r) or self.cost_per_trade_r < 0):
            raise ValueError('COST_PER_TRADE_R_INVALID')
        if self.cost_per_trade_r is not None and (not self.cost_model_verified or not self.cost_model_id or len(self.cost_model_evidence_sha256 or '') != 64 or any((ch not in '0123456789abcdef' for ch in (self.cost_model_evidence_sha256 or '').lower()))):
            raise ValueError('COST_MODEL_EVIDENCE_REQUIRED')
        if self.cost_per_trade_r is None and self.cost_model_verified:
            raise ValueError('COST_MODEL_VALUE_MISSING')
        if not self.hypothesis_id.strip():
            raise ValueError('HYPOTHESIS_ID_REQUIRED')
        if self.minimum_test_trades < 201 or self.minimum_expectancy_improvement_r < 0.1:
            raise ValueError('EXPERIMENT_DECISION_THRESHOLD_BELOW_REGISTERED_GATE')
        if self.bootstrap_iterations < 100 or self.bootstrap_block_days < 1:
            raise ValueError('BOOTSTRAP_CONFIG_INVALID')
        if not 0.5 < self.confidence_level < 1:
            raise ValueError('BOOTSTRAP_CONFIDENCE_INVALID')
        if self.structure_m15.timeframe_seconds != 900 or self.structure_m1.timeframe_seconds != 60:
            raise ValueError('EXPERIMENT_TIMEFRAME_CONFIG_INVALID')

def _first_fvg_retest(m1_bars: Sequence[OHLCBar], mss: StructureBreak, direction: Direction, *, max_wait_bars: int, sessions: Sequence[SessionWindow]) -> tuple[FairValueGap, int, float] | None:
    start_create = mss.break_index
    last_create = len(m1_bars) - 1
    for i in range(start_create, last_create + 1):
        gap = _fvg_at(m1_bars, i, 60)
        if gap is None or gap.direction != direction:
            continue
        if not is_in_session(gap.created_at_utc, sessions):
            return None
        stop_index = min(len(m1_bars), i + 1 + max_wait_bars)
        for j in range(i + 1, stop_index):
            bar = m1_bars[j]
            if bar.synthetic or (bar.timestamp - m1_bars[j - 1].timestamp).total_seconds() != 60:
                return None
            touched = bar.low <= gap.midpoint if direction == 'LONG' else bar.high >= gap.midpoint
            if touched:
                fill_time = bar.timestamp + timedelta(seconds=60)
                if not is_in_session(fill_time, sessions):
                    return None
                return (gap, j, gap.midpoint)
        return None
    return None

def build_candidate_setups(m15_bars: Sequence[OHLCBar], m1_bars: Sequence[OHLCBar], config: ExperimentConfig) -> list[CandidateSetup]:
    _validate_bars(m15_bars)
    _validate_bars(m1_bars)
    sweeps = detect_m15_sweeps(m15_bars, structure_config=config.structure_m15)
    used_fvgs: set[int] = set()
    setups: list[CandidateSetup] = []
    for sweep in sweeps:
        if not is_in_session(sweep.event_timestamp_utc, config.sessions):
            continue
        mss = find_m1_mss_after_sweep(m1_bars, sweep, n_bars=config.m1_mss_window_bars, structure_config=config.structure_m1)
        if mss is None or not is_in_session(mss.break_timestamp_utc, config.sessions):
            continue
        fvg_entry = _first_fvg_retest(m1_bars, mss, sweep.direction, max_wait_bars=config.max_fvg_wait_bars, sessions=config.sessions)
        if fvg_entry is None:
            continue
        gap, entry_index, entry_price = fvg_entry
        if gap.created_index in used_fvgs:
            continue
        used_fvgs.add(gap.created_index)
        aligned = is_price_at_369_level(sweep.sweep_extreme, sweep.reference_swing_price, config.instrument_369)
        setups.append(CandidateSetup(sweep, mss, gap, entry_index, entry_price, aligned))
    return setups

def _trade_id(group: str, symbol: str, setup: CandidateSetup) -> str:
    raw = '|'.join((group, symbol, setup.sweep.event_timestamp_utc, setup.mss.break_timestamp_utc, setup.fvg.created_at_utc))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]

def _simulate_setup(bars: Sequence[OHLCBar], setup: CandidateSetup, *, group: str, symbol: str, dataset_sha256: str, max_holding_bars: int, take_profit_r: float, cost_per_trade_r: float | None, stop_buffer_price: float=0.0) -> TradeRecord:
    direction = setup.sweep.direction
    entry = setup.entry_price
    buffer = _finite_nonnegative(stop_buffer_price, 'STOP_BUFFER_PRICE_INVALID')
    stop = setup.fvg.bottom - buffer if direction == 'LONG' else setup.fvg.top + buffer
    risk = entry - stop if direction == 'LONG' else stop - entry
    if not math.isfinite(risk) or risk <= 0:
        raise ValueError('FVG_STOP_DISTANCE_INVALID')
    target = entry + risk * take_profit_r if direction == 'LONG' else entry - risk * take_profit_r
    last_index = min(len(bars) - 1, setup.entry_index + max_holding_bars - 1)
    exit_price = bars[last_index].close
    exit_index = last_index
    exit_reason = 'TIME_EXIT'
    for i in range(setup.entry_index, last_index + 1):
        bar = bars[i]
        if bar.synthetic or (i > 0 and (bar.timestamp - bars[i - 1].timestamp).total_seconds() != 60):
            exit_price = bars[i - 1].close if i > setup.entry_index else entry
            exit_index = max(setup.entry_index, i - 1)
            exit_reason = 'DATA_GAP_EXIT'
            break
        if direction == 'LONG':
            stop_hit = bar.low <= stop
            target_hit = bar.high >= target
            if stop_hit:
                exit_price = min(stop, bar.open) if bar.open < stop else stop
                exit_index, exit_reason = (i, 'STOP_LOSS')
                break
            if i == setup.entry_index:
                continue
            if target_hit:
                exit_price = target
                exit_index, exit_reason = (i, 'TAKE_PROFIT')
                break
        else:
            stop_hit = bar.high >= stop
            target_hit = bar.low <= target
            if stop_hit:
                exit_price = max(stop, bar.open) if bar.open > stop else stop
                exit_index, exit_reason = (i, 'STOP_LOSS')
                break
            if i == setup.entry_index:
                continue
            if target_hit:
                exit_price = target
                exit_index, exit_reason = (i, 'TAKE_PROFIT')
                break
    gross_r = (exit_price - entry) / risk if direction == 'LONG' else (entry - exit_price) / risk
    net_r = None if cost_per_trade_r is None else gross_r - cost_per_trade_r
    entry_time = _utc_text(bars[setup.entry_index].timestamp + timedelta(seconds=60))
    exit_time = _utc_text(bars[exit_index].timestamp + timedelta(seconds=60))
    return TradeRecord(_trade_id(group, symbol, setup), group, symbol, direction, setup.sweep.event_timestamp_utc, setup.sweep.event_timestamp_utc, setup.mss.break_timestamp_utc, setup.fvg.created_at_utc, entry_time, exit_time, entry, stop, target, exit_price, gross_r, net_r, exit_reason, setup.sweep.reference_swing_price, setup.three69_aligned, dataset_sha256)

def _metrics(records: Sequence[TradeRecord]) -> dict[str, Any]:
    records = sorted(records, key=lambda x: (x.exit_timestamp_utc, x.trade_id))
    rs = [float(x.r_multiple) for x in records]
    wins = [x for x in rs if x > 0]
    losses = [x for x in rs if x < 0]
    gross_wins, gross_losses = (sum(wins), abs(sum(losses)))
    equity = peak = 0.0
    drawdown = 0.0
    for value in rs:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    net_values = [x.net_r_multiple for x in records]
    have_net = bool(net_values) and all((x is not None for x in net_values))
    net_rs = [float(x) for x in net_values] if have_net else []
    net_wins = [x for x in net_rs if x > 0]
    net_losses = [x for x in net_rs if x < 0]
    net_drawdown = _max_drawdown_r(net_rs) if net_rs else None
    net_expectancy = fmean(net_rs) if net_rs else None
    return {'group': records[0].group if records else None, 'total_trades': len(records), 'win_rate': len(wins) / len(rs) if rs else None, 'expectancy_r': fmean(rs) if rs else None, 'net_expectancy_r': net_expectancy, 'profit_factor': gross_wins / gross_losses if gross_losses > 0 else None, 'max_drawdown_r': drawdown if rs else None, 'net_profit_factor': sum(net_wins) / abs(sum(net_losses)) if have_net and sum(net_losses) < 0 else None, 'net_max_drawdown_r': net_drawdown, 'average_r_multiple': fmean(rs) if rs else None}

def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError('BOOTSTRAP_SAMPLE_EMPTY')
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight

def _block_bootstrap(control: Sequence[TradeRecord], test: Sequence[TradeRecord], *, iterations: int, block_days: int, confidence_level: float, seed: int, use_net: bool=False) -> dict[str, float | int] | None:
    if not control or not test:
        return None
    by_day: dict[str, dict[str, list[float]]] = {}
    observations = [(group, row) for group, rows in (('control', control), ('test', test)) for row in rows]
    observed_dates = [_utc(row.exit_timestamp_utc).date() for _group, row in observations]
    first_day, last_day = (min(observed_dates), max(observed_dates))
    calendar = [first_day + timedelta(days=offset) for offset in range((last_day - first_day).days + 1)]
    by_day = {day.isoformat(): {'control': [], 'test': []} for day in calendar}
    for group, row in observations:
        day = _utc(row.exit_timestamp_utc).date().isoformat()
        value = row.net_r_multiple if use_net else row.r_multiple
        if value is None:
            raise ValueError('NET_BOOTSTRAP_REQUIRES_COMPLETE_VERIFIED_COSTS')
        by_day[day][group].append(float(value))
    days = [day.isoformat() for day in calendar]
    if len(days) < block_days * 2:
        return None
    blocks = [days[i:i + block_days] for i in range(0, len(days) - block_days + 1)]
    rng = random.Random(seed)
    deltas: list[float] = []
    dd_improvements: list[float] = []
    tail = (1.0 - confidence_level) / 2.0
    for _ in range(iterations):
        selected_days: list[str] = []
        while len(selected_days) < len(days):
            selected_days.extend(rng.choice(blocks))
        selected_days = selected_days[:len(days)]
        control_rs: list[float] = []
        test_rs: list[float] = []
        for day in selected_days:
            control_rs.extend(by_day[day]['control'])
            test_rs.extend(by_day[day]['test'])
        if not control_rs or not test_rs:
            continue
        deltas.append(fmean(test_rs) - fmean(control_rs))
        dd_improvements.append(_max_drawdown_r(control_rs) - _max_drawdown_r(test_rs))
    if len(deltas) < max(100, iterations // 2):
        return None
    return {'replicates': len(deltas), 'expectancy_delta_ci_low': _percentile(deltas, tail), 'expectancy_delta_ci_high': _percentile(deltas, 1.0 - tail), 'drawdown_improvement_ci_low': _percentile(dd_improvements, tail), 'drawdown_improvement_ci_high': _percentile(dd_improvements, 1.0 - tail)}

def _max_drawdown_r(values: Sequence[float]) -> float:
    equity = peak = drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown

def build_trade_frame(records: Sequence[TradeRecord]):
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError('PANDAS_REQUIRED_FOR_INSTITUTIONAL_TRADE_FRAME') from exc
    frame = pd.DataFrame([asdict(record) for record in records], columns=TRADE_COLUMNS)
    validate_trade_frame(frame)
    return frame

def validate_trade_frame(frame: Any) -> None:
    try:
        columns = list(frame.columns)
    except Exception as exc:
        raise ValueError('TRADE_FRAME_MUST_BE_A_DATAFRAME') from exc
    if tuple(columns) != TRADE_COLUMNS:
        raise ValueError('TRADE_FRAME_SCHEMA_MISMATCH')
    if frame['trade_id'].duplicated().any():
        raise ValueError('TRADE_ID_DUPLICATE')
    if frame[list(CRITICAL_TRADE_COLUMNS)].isnull().any().any():
        raise ValueError('TRADE_FRAME_CRITICAL_NULL')
    for name in ('entry_price', 'stop_loss', 'take_profit', 'exit_price', 'r_multiple', 'protected_swing_price'):
        values = frame[name].astype(float).tolist()
        if not all((math.isfinite(x) for x in values)):
            raise ValueError('TRADE_FRAME_NONFINITE_CRITICAL_VALUE')
    non_null_net = frame['net_r_multiple'].dropna().astype(float).tolist()
    if not all((math.isfinite(x) for x in non_null_net)):
        raise ValueError('TRADE_FRAME_NET_R_NONFINITE')
    for row in frame.to_dict(orient='records'):
        direction = row['direction']
        entry = float(row['entry_price'])
        stop = float(row['stop_loss'])
        target = float(row['take_profit'])
        exit_price = float(row['exit_price'])
        risk = entry - stop if direction == 'LONG' else stop - entry if direction == 'SHORT' else -1.0
        if risk <= 0:
            raise ValueError('TRADE_FRAME_RISK_GEOMETRY_INVALID')
        if direction == 'LONG' and target <= entry:
            raise ValueError('TRADE_FRAME_TARGET_GEOMETRY_INVALID')
        if direction == 'SHORT' and target >= entry:
            raise ValueError('TRADE_FRAME_TARGET_GEOMETRY_INVALID')
        expected_r = (exit_price - entry) / risk if direction == 'LONG' else (entry - exit_price) / risk
        if not math.isclose(expected_r, float(row['r_multiple']), rel_tol=1e-09, abs_tol=1e-09):
            raise ValueError('TRADE_FRAME_R_MULTIPLE_MISMATCH')
        stamps = [_utc(row[name]) for name in ('signal_timestamp_utc', 'sweep_timestamp_utc', 'mss_timestamp_utc', 'fvg_created_timestamp_utc', 'entry_timestamp_utc', 'exit_timestamp_utc')]
        if stamps != sorted(stamps):
            raise ValueError('TRADE_FRAME_EVENT_TIME_ORDER_INVALID')

@dataclass(frozen=True, slots=True)
class ExperimentResult:
    trades: Any
    metrics: Any
    statistics: Mapping[str, Any]
    decision: str
    dataset_sha256: str
    candidate_setup_count: int

def run_experiment(m15_bars: Sequence[OHLCBar], m1_bars: Sequence[OHLCBar], dataset: ExperimentDataset, *, config: ExperimentConfig, code_commit_sha: str) -> ExperimentResult:
    if not code_commit_sha or len(code_commit_sha) not in (40, 64) or any((ch not in '0123456789abcdef' for ch in code_commit_sha.lower())):
        raise ValueError('EXPERIMENT_CODE_COMMIT_SHA_REQUIRED')
    if not config.instrument_369.metadata_verified:
        raise ValueError('369_INSTRUMENT_SPEC_EVIDENCE_REQUIRED')
    validate_experiment_dataset(m1_bars, m15_bars, dataset, minimum_history_days=config.minimum_history_days)
    if dataset.symbol != config.symbol:
        raise ValueError('EXPERIMENT_SYMBOL_MISMATCH')
    setups = build_candidate_setups(m15_bars, m1_bars, config)
    control: list[TradeRecord] = []
    test: list[TradeRecord] = []
    digest = dataset.combined_sha256
    for setup in setups:
        control.append(_simulate_setup(m1_bars, setup, group='Control', symbol=config.symbol, dataset_sha256=digest, max_holding_bars=config.max_holding_bars, take_profit_r=config.take_profit_r, cost_per_trade_r=config.cost_per_trade_r, stop_buffer_price=config.instrument_369.tick_size * config.stop_buffer_ticks))
        if setup.three69_aligned:
            test.append(_simulate_setup(m1_bars, setup, group='Test_369', symbol=config.symbol, dataset_sha256=digest, max_holding_bars=config.max_holding_bars, take_profit_r=config.take_profit_r, cost_per_trade_r=config.cost_per_trade_r, stop_buffer_price=config.instrument_369.tick_size * config.stop_buffer_ticks))
    all_records = control + test
    trades_frame = build_trade_frame(all_records)
    metrics_rows = [_metrics(control), _metrics(test)]
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError('PANDAS_REQUIRED_FOR_INSTITUTIONAL_METRICS_FRAME') from exc
    metrics_frame = pd.DataFrame(metrics_rows, columns=('group', 'total_trades', 'win_rate', 'expectancy_r', 'net_expectancy_r', 'profit_factor', 'max_drawdown_r', 'net_profit_factor', 'net_max_drawdown_r', 'average_r_multiple'))
    control_metrics, test_metrics = metrics_rows
    gross_delta = test_metrics['expectancy_r'] - control_metrics['expectancy_r'] if test_metrics['expectancy_r'] is not None and control_metrics['expectancy_r'] is not None else None
    net_delta = test_metrics['net_expectancy_r'] - control_metrics['net_expectancy_r'] if test_metrics['net_expectancy_r'] is not None and control_metrics['net_expectancy_r'] is not None else None
    cost_verified = config.cost_per_trade_r is not None and config.cost_model_verified
    delta = net_delta if cost_verified else gross_delta
    bootstrap = _block_bootstrap(control, test, iterations=config.bootstrap_iterations, block_days=config.bootstrap_block_days, confidence_level=config.confidence_level, seed=config.random_seed, use_net=cost_verified) if test else None
    n_test = len(test)
    expectation_pass = bool(n_test >= config.minimum_test_trades and delta is not None and (delta >= config.minimum_expectancy_improvement_r) and (bootstrap is not None) and (bootstrap['expectancy_delta_ci_low'] > 0))
    drawdown_pass = bool(n_test >= config.minimum_test_trades and bootstrap is not None and (bootstrap['drawdown_improvement_ci_low'] > 0))
    if n_test < config.minimum_test_trades:
        decision = 'INSUFFICIENT_SAMPLE'
    elif bootstrap is None:
        decision = 'INSUFFICIENT_INDEPENDENT_BLOCKS'
    elif expectation_pass or drawdown_pass:
        decision = 'RETAIN_369_FOR_FURTHER_OOS_VALIDATION' if cost_verified else 'PROVISIONAL_GROSS_GATE_PASS_COST_MODEL_REQUIRED'
    else:
        decision = 'DEPRECATE_369_FROM_RESEARCH_CANDIDATE'
    config_payload = {'symbol': config.symbol, 'instrument_369': asdict(config.instrument_369), 'm1_mss_window_bars': config.m1_mss_window_bars, 'max_holding_bars': config.max_holding_bars, 'structure_m15': asdict(config.structure_m15), 'structure_m1': asdict(config.structure_m1), 'sessions': [{'name': x.name, 'timezone': x.timezone_name, 'start': x.start.isoformat(), 'end': x.end.isoformat()} for x in config.sessions], 'max_fvg_wait_bars': config.max_fvg_wait_bars, 'take_profit_r': config.take_profit_r, 'stop_buffer_ticks': config.stop_buffer_ticks, 'cost_per_trade_r': config.cost_per_trade_r, 'cost_model_id': config.cost_model_id, 'cost_model_evidence_sha256': config.cost_model_evidence_sha256, 'cost_model_verified': config.cost_model_verified, 'minimum_history_days': config.minimum_history_days, 'minimum_test_trades': config.minimum_test_trades, 'minimum_expectancy_improvement_r': config.minimum_expectancy_improvement_r, 'bootstrap_iterations': config.bootstrap_iterations, 'bootstrap_block_days': config.bootstrap_block_days, 'confidence_level': config.confidence_level, 'random_seed': config.random_seed, 'hypothesis_id': config.hypothesis_id}
    config_hash = hashlib.sha256(json.dumps(config_payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
    experiment_id = hashlib.sha256(f'{config.hypothesis_id}:{digest}:{code_commit_sha}:{config_hash}'.encode('utf-8')).hexdigest()[:24]
    statistics = {'experiment_id': experiment_id, 'run_timestamp_utc': _utc_text(datetime.now(timezone.utc)), 'hypothesis_id': config.hypothesis_id, 'objective': 'Test whether the pre-registered 369 filter improves M15/M1 structure-only expectancy or reduces drawdown.', 'dataset_hashes': {'m1': dataset.m1.content_sha256, 'm15': dataset.m15.content_sha256}, 'source_acquisition_evidence': {'m1': {'sha256': dataset.m1.acquisition_evidence_sha256, 'attestation_id': dataset.m1.source_attestation_id, 'endpoint_uri': dataset.m1.endpoint_uri}, 'm15': {'sha256': dataset.m15.acquisition_evidence_sha256, 'attestation_id': dataset.m15.source_attestation_id, 'endpoint_uri': dataset.m15.endpoint_uri}}, 'data_windows': {'m1_start_utc': m1_bars[0].timestamp_utc, 'm1_end_utc': m1_bars[-1].timestamp_utc, 'm15_start_utc': m15_bars[0].timestamp_utc, 'm15_end_utc': m15_bars[-1].timestamp_utc}, 'strategy_version': ENGINE_VERSION, 'code_commit_sha': code_commit_sha, 'config_hash': config_hash, 'random_seeds': [config.random_seed], 'search_space': 'one frozen configuration; no parameter sweep in this run', 'trial_count': 1, 'selection_rule': {'minimum_test_trades': config.minimum_test_trades, 'minimum_expectancy_improvement_r': config.minimum_expectancy_improvement_r, 'confidence_level': config.confidence_level, 'retain_if': 'expectancy delta clears minimum and bootstrap lower CI > 0, OR drawdown improvement bootstrap lower CI > 0'}, 'oos_reservation': 'NOT_PERFORMED; comparative backtest is not prospective OOS evidence', 'config': config_payload, 'config_hash': config_hash, 'result': {'decision': decision, 'candidate_setup_count': len(setups), 'control_trade_count': len(control), 'test_trade_count': len(test)}, 'control': control_metrics, 'test_369': test_metrics, 'expectancy_delta_r': delta, 'gross_expectancy_delta_r': gross_delta, 'net_expectancy_delta_r': net_delta, 'block_bootstrap': bootstrap, 'expectancy_gate_pass': expectation_pass, 'drawdown_gate_pass': drawdown_pass, 'minimum_test_trades': config.minimum_test_trades, 'minimum_expectancy_improvement_r': config.minimum_expectancy_improvement_r, 'cost_model_supplied': config.cost_per_trade_r is not None, 'cost_model_id': config.cost_model_id, 'cost_model_evidence_sha256': config.cost_model_evidence_sha256, 'net_expectancy_status': 'CALCULATED_FROM_VERIFIED_COST_MODEL' if config.cost_per_trade_r is not None else 'UNDETERMINED_COST_MODEL_MISSING', 'decision_basis': 'NET_R_WITH_VERIFIED_COST_MODEL' if cost_verified else 'GROSS_R_PROVISIONAL_ONLY_COST_MODEL_MISSING', 'experiment_version': ENGINE_VERSION, 'dataset_sha256': digest, 'research_only': True, 'capital_authority': False, 'live_execution': False, 'limitations': ['No prospective out-of-sample qualification is performed by this comparison.', 'OHLC candle data cannot reveal intrabar event ordering; stop-first handling is conservative.', 'Entry timestamp is a candle-close representation of an assumed midpoint limit fill, not tick-level fill evidence.', 'Max drawdown is a realized-R sequence metric and does not model concurrent capital or portfolio exposure limits.', 'London session windows must be explicitly supplied; only the New York AM window is enabled by default.', '369 step mapping and projection offsets are a deterministic research hypothesis, not an externally validated market law.', 'Only one frozen configuration is evaluated; parameter or instrument sweeps require multiple-comparison controls and untouched OOS data.']}
    return ExperimentResult(trades_frame, metrics_frame, statistics, decision, digest, len(setups))
__all__ = ['CAPITAL_AUTHORITY', 'LIVE_EXECUTION', 'ORDER_SUBMISSION_PERMITTED', 'RESEARCH_ONLY', 'ENGINE_VERSION', 'OHLCBar', 'StructureConfig', 'SwingPoint', 'ProtectedSwing', 'StructureBreak', 'calculate_atr', 'detect_protected_swings', 'protected_swings_from_breaks', 'FairValueGap', 'scan_and_track_fvgs', 'active_fvgs_at', 'SessionWindow', 'NY_AM_SESSION', 'is_in_session', 'SweepEvent', 'detect_m15_sweeps', 'find_m1_mss_after_sweep', 'Instrument369Spec', 'calculate_369_step', 'project_369_levels', 'DERIV_PUBLIC_MARKET_DATA_ENDPOINT', 'DERIV_TICKS_HISTORY_DOCS', 'is_price_at_369_level', 'DerivHistoryManifest', 'DerivHistoryResult', 'normalize_deriv_candle_payload', 'fetch_deriv_history', 'fetch_deriv_history_from_websocket', 'hash_bars', 'ExperimentDataset', 'validate_experiment_dataset', 'CandidateSetup', 'TradeRecord', 'TRADE_COLUMNS', 'CRITICAL_TRADE_COLUMNS', 'ExperimentConfig', 'build_candidate_setups', 'build_trade_frame', 'validate_trade_frame', 'ExperimentResult', 'run_experiment']
