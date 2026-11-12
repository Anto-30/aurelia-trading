"""Causal MSNR entry overlays; isolated research plane, never execution.

The canonical MSNR detector remains the sole source of setup events. This
module consumes its StrategyCandidate outputs and compares entry timing only:
V0 next-bar-open baseline, V1 subsequent displacement-close, V2 subsequent
displacement-created FVG retrace. It does not create HTF POIs or new MSNR signals.

Prices are OHLC-derived research proxies, not executable quotes or fills.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Literal, Sequence

from research.labs.deterministic_intraday_strategies import (
    StrategyBar,
    StrategyCandidate,
)

OverlayVariant = Literal["V0_BASELINE", "V1_DISPLACEMENT_CLOSE", "V2_FVG_RETRACE"]
OverlayStatus = Literal[
    "FILLED_PROXY", "NO_POST_SIGNAL_BAR", "NO_DISPLACEMENT",
    "NO_FVG", "PENDING_DISPLACEMENT_WINDOW",
    "NO_RETRACE_WITHIN_WINDOW", "GAP_THROUGH_ZONE", "PENDING_RETRACE",
]


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("OVERLAY_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None:
        raise ValueError("OVERLAY_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(timezone.utc)


def _validate_bars(bars: Sequence[StrategyBar]) -> None:
    previous: datetime | None = None
    for bar in bars:
        if not isinstance(bar, StrategyBar):
            raise ValueError("OVERLAY_BAR_TYPE_INVALID")
        stamp = _utc(bar.timestamp_utc)
        if previous is not None and stamp <= previous:
            raise ValueError("OVERLAY_BAR_TIMESTAMPS_NOT_INCREASING")
        previous = stamp


@dataclass(frozen=True)
class EntryOverlayConfig:
    atr_period: int = 14
    displacement_body_atr: float = 1.0
    max_bars_after_signal: int = 20
    max_retrace_bars_after_displacement: int = 5
    version: str = "msnr-entry-overlays-v1"

    def __post_init__(self) -> None:
        if self.atr_period < 2:
            raise ValueError("OVERLAY_ATR_PERIOD_INVALID")
        if not isfinite(self.displacement_body_atr) or self.displacement_body_atr <= 0:
            raise ValueError("OVERLAY_DISPLACEMENT_THRESHOLD_INVALID")
        if self.max_bars_after_signal < 1 or self.max_retrace_bars_after_displacement < 1:
            raise ValueError("OVERLAY_SEARCH_WINDOW_INVALID")
        if not self.version.strip():
            raise ValueError("OVERLAY_VERSION_MISSING")


@dataclass(frozen=True)
class EntryOverlayEvent:
    strategy_id: str
    strategy_version: str
    overlay_version: str
    variant: OverlayVariant
    direction: str
    signal_timestamp_utc: str
    status: OverlayStatus
    entry_timestamp_utc: str | None
    entry_price_proxy: float | None
    displacement_timestamp_utc: str | None = None
    fvg_lower: float | None = None
    fvg_upper: float | None = None
    reason: str = ""

    def as_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload.update({
            "research_only": True,
            "capital_authority": False,
            "order_submission_permitted": False,
            "price_is_executable": False,
        })
        return payload


def _atr_before(bars: Sequence[StrategyBar], index: int, period: int) -> float | None:
    """ATR using only bars strictly before index; current displacement excluded."""
    if index < period + 1:
        return None
    ranges: list[float] = []
    for j in range(index - period, index):
        current, previous = bars[j], bars[j - 1]
        ranges.append(max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        ))
    value = sum(ranges) / len(ranges)
    return value if value > 0 and isfinite(value) else None


def _displacement(
    bars: Sequence[StrategyBar], signal_index: int, config: EntryOverlayConfig,
    direction: str,
) -> int | None:
    stop = min(len(bars), signal_index + 1 + config.max_bars_after_signal)
    for i in range(signal_index + 1, stop):
        atr = _atr_before(bars, i, config.atr_period)
        if atr is None:
            continue
        bar = bars[i]
        aligned = bar.close > bar.open if direction == "LONG" else bar.close < bar.open
        if aligned and abs(bar.close - bar.open) >= config.displacement_body_atr * atr:
            return i
    return None


def _fvg_at(
    bars: Sequence[StrategyBar], index: int, direction: str,
) -> tuple[float, float] | None:
    if index < 2:
        return None
    left, right = bars[index - 2], bars[index]
    if direction == "LONG" and right.low > left.high:
        return (left.high, right.low)
    if direction == "SHORT" and right.high < left.low:
        return (right.high, left.low)
    return None


def _retrace_entry(
    bars: Sequence[StrategyBar], displacement_index: int,
    zone: tuple[float, float], direction: str, max_bars: int,
) -> tuple[int, float] | str | None:
    lower, upper = zone
    stop = min(len(bars), displacement_index + 1 + max_bars)
    for i in range(displacement_index + 1, stop):
        bar = bars[i]
        if direction == "LONG":
            # Bullish FVG is approached from above; a gap below the zone is
            # not silently treated as a fill at the more favorable zone price.
            if bar.open < lower:
                return "GAP_THROUGH_ZONE"
            if lower <= bar.open <= upper:
                return (i, bar.open)
            if bar.open > upper and bar.low <= upper:
                return (i, upper)
        else:
            # Bearish FVG is approached from below.
            if bar.open > upper:
                return "GAP_THROUGH_ZONE"
            if lower <= bar.open <= upper:
                return (i, bar.open)
            if bar.open < lower and bar.high >= lower:
                return (i, lower)
    return None


def build_msnr_entry_overlays(
    bars: Sequence[StrategyBar],
    signals: Sequence[StrategyCandidate],
    *,
    config: EntryOverlayConfig = EntryOverlayConfig(),
) -> tuple[EntryOverlayEvent, ...]:
    """Build three entry overlays from canonical MSNR signal timestamps.

    Input bars must be a chronological prefix. The canonical detector is not
    called or modified here. Signal timestamps must exactly match a bar in
    that prefix. V0/V1/V2 prices are OHLC proxies, never broker fills.
    """
    _validate_bars(bars)
    if not bars:
        return ()
    index_by_timestamp = {bar.timestamp_utc: i for i, bar in enumerate(bars)}
    output: list[EntryOverlayEvent] = []

    for signal in signals:
        if signal.strategy_id != "MSNR_LIQUIDITY_SWEEP":
            raise ValueError("OVERLAY_ACCEPTS_CANONICAL_MSNR_SIGNALS_ONLY")
        if signal.capital_authority or signal.order_submission_permitted:
            raise ValueError("OVERLAY_SIGNAL_MUST_BE_NON_EXECUTABLE")
        signal_index = index_by_timestamp.get(signal.signal_timestamp_utc)
        if signal_index is None:
            raise ValueError("OVERLAY_SIGNAL_TIMESTAMP_NOT_IN_BAR_PREFIX")
        direction = signal.direction
        if direction not in ("LONG", "SHORT"):
            raise ValueError("OVERLAY_SIGNAL_DIRECTION_INVALID")

        common = dict(
            strategy_id=signal.strategy_id,
            strategy_version=signal.version,
            overlay_version=config.version,
            direction=direction,
            signal_timestamp_utc=signal.signal_timestamp_utc,
        )
        if signal_index + 1 >= len(bars):
            output.extend((
                EntryOverlayEvent(**common, variant="V0_BASELINE", status="NO_POST_SIGNAL_BAR",
                                  entry_timestamp_utc=None, entry_price_proxy=None,
                                  reason="NO_BAR_AFTER_CANONICAL_SIGNAL"),
                EntryOverlayEvent(**common, variant="V1_DISPLACEMENT_CLOSE", status="NO_POST_SIGNAL_BAR",
                                  entry_timestamp_utc=None, entry_price_proxy=None,
                                  reason="NO_BAR_AFTER_CANONICAL_SIGNAL"),
                EntryOverlayEvent(**common, variant="V2_FVG_RETRACE", status="NO_POST_SIGNAL_BAR",
                                  entry_timestamp_utc=None, entry_price_proxy=None,
                                  reason="NO_BAR_AFTER_CANONICAL_SIGNAL"),
            ))
            continue

        baseline = bars[signal_index + 1]
        output.append(EntryOverlayEvent(
            **common, variant="V0_BASELINE", status="FILLED_PROXY",
            entry_timestamp_utc=baseline.timestamp_utc, entry_price_proxy=baseline.open,
            reason="NEXT_BAR_OPEN_AFTER_CANONICAL_MSNR_SIGNAL;OHLC_PROXY_ONLY",
        ))

        displacement_index = _displacement(bars, signal_index, config, direction)
        if displacement_index is None:
            window_complete = len(bars) >= signal_index + 1 + config.max_bars_after_signal
            status: OverlayStatus = "NO_DISPLACEMENT" if window_complete else "PENDING_DISPLACEMENT_WINDOW"
            reason = ("NO_ALIGNED_BODY_THRESHOLD_WITHIN_COMPLETE_SEARCH_WINDOW"
                      if window_complete else "INSUFFICIENT_FUTURE_BARS_TO_CLOSE_DISPLACEMENT_WINDOW")
            output.append(EntryOverlayEvent(
                **common, variant="V1_DISPLACEMENT_CLOSE", status=status,
                entry_timestamp_utc=None, entry_price_proxy=None, reason=reason,
            ))
            output.append(EntryOverlayEvent(
                **common, variant="V2_FVG_RETRACE", status=status,
                entry_timestamp_utc=None, entry_price_proxy=None, reason=reason,
            ))
            continue

        displacement = bars[displacement_index]
        output.append(EntryOverlayEvent(
            **common, variant="V1_DISPLACEMENT_CLOSE", status="FILLED_PROXY",
            entry_timestamp_utc=displacement.timestamp_utc,
            entry_price_proxy=displacement.close,
            displacement_timestamp_utc=displacement.timestamp_utc,
            reason="ALIGNED_DISPLACEMENT_CLOSE;OHLC_PROXY_ONLY",
        ))

        zone = _fvg_at(bars, displacement_index, direction)
        if zone is None:
            output.append(EntryOverlayEvent(
                **common, variant="V2_FVG_RETRACE", status="NO_FVG",
                entry_timestamp_utc=None, entry_price_proxy=None,
                displacement_timestamp_utc=displacement.timestamp_utc,
                reason="DISPLACEMENT_DID_NOT_CREATE_DIRECTIONAL_THREE_BAR_FVG",
            ))
            continue

        retrace = _retrace_entry(
            bars, displacement_index, zone, direction,
            config.max_retrace_bars_after_displacement,
        )
        if retrace == "GAP_THROUGH_ZONE":
            status: OverlayStatus = "GAP_THROUGH_ZONE"
            entry_index, entry_price = None, None
            reason = "PRICE_GAPPED_THROUGH_FVG_WITHOUT_CONSERVATIVE_TOUCH_FILL"
        elif retrace is None:
            entry_index, entry_price = None, None
            observed = len(bars) - displacement_index - 1
            if observed < config.max_retrace_bars_after_displacement:
                status = "PENDING_RETRACE"
                reason = "RETRACE_WINDOW_INCOMPLETE;MORE_FUTURE_BARS_REQUIRED"
            else:
                status = "NO_RETRACE_WITHIN_WINDOW"
                reason = "NO_FVG_RETRACE_WITHIN_COMPLETE_CONFIGURED_WINDOW"
        else:
            entry_index, entry_price = retrace
            status = "FILLED_PROXY"
            reason = "FIRST_CAUSAL_FVG_RETRACE;OHLC_PROXY_ONLY"

        output.append(EntryOverlayEvent(
            **common, variant="V2_FVG_RETRACE", status=status,
            entry_timestamp_utc=bars[entry_index].timestamp_utc if entry_index is not None else None,
            entry_price_proxy=entry_price,
            displacement_timestamp_utc=displacement.timestamp_utc,
            fvg_lower=zone[0], fvg_upper=zone[1], reason=reason,
        ))

    return tuple(output)
