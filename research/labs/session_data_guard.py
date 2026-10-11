"""Fail-closed market-data and event-calendar guards for research pipelines.

Research-only: this module does not place orders or authorize live trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Iterable


@dataclass(frozen=True)
class Candle:
    """A candle with explicit start and end timestamps (UTC-aware or offset-aware)."""
    start: datetime
    end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    complete: bool = True

    def validate(self, *, now: datetime | None = None) -> None:
        for name, stamp in (("start", self.start), ("end", self.end)):
            if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError(f"{name} timestamp must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("candle end must be after start")
        if not self.complete:
            raise ValueError("incomplete candle")
        values = (self.open, self.high, self.low, self.close, self.volume)
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("non-finite OHLCV")
        if self.volume < 0 or self.low > min(self.open, self.close) or self.high < max(self.open, self.close) or self.low > self.high:
            raise ValueError("invalid OHLCV")
        if now is not None:
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("now must be timezone-aware")
            if self.end.astimezone(timezone.utc) > now.astimezone(timezone.utc):
                raise ValueError("candle has not ended by evaluation time")


def validate_candle_series(
    candles: Iterable[Candle],
    *,
    now: datetime | None = None,
    expected_interval: timedelta | None = None,
    reject_gaps: bool = False,
) -> list[Candle]:
    rows = list(candles)
    if not rows:
        raise ValueError("INSUFFICIENT EVIDENCE: empty candle series")
    if expected_interval is not None and expected_interval <= timedelta(0):
        raise ValueError("expected interval must be positive")
    for candle in rows:
        candle.validate(now=now)
        if expected_interval is not None and candle.end.astimezone(timezone.utc) - candle.start.astimezone(timezone.utc) != expected_interval:
            raise ValueError("candle interval mismatch")
    starts = [c.start.astimezone(timezone.utc) for c in rows]
    if starts != sorted(starts) or len(set(starts)) != len(starts):
        raise ValueError("candle starts must be unique and ordered")
    for previous, current in zip(rows, rows[1:]):
        previous_end = previous.end.astimezone(timezone.utc)
        current_start = current.start.astimezone(timezone.utc)
        if current_start < previous_end:
            raise ValueError("overlapping candles")
        if reject_gaps and expected_interval is not None and current_start > previous_end:
            raise ValueError("candle gap requires explicit session/calendar handling")
    return rows


@dataclass(frozen=True)
class CalendarSnapshot:
    fetched_at: datetime
    events: tuple[datetime, ...]
    source: str


def news_window_blocked(
    snapshot: CalendarSnapshot | None,
    *,
    now: datetime,
    max_age: timedelta = timedelta(minutes=15),
    before: timedelta = timedelta(minutes=15),
    after: timedelta = timedelta(minutes=15),
) -> tuple[bool, str]:
    """Block entries if calendar data is absent/stale/invalid or within an event window."""
    if now.tzinfo is None or now.utcoffset() is None:
        return True, "evaluation time is timezone-naive"
    if max_age < timedelta(0) or before < timedelta(0) or after < timedelta(0):
        return True, "invalid calendar guard configuration"
    if snapshot is None or not isinstance(snapshot.source, str) or not snapshot.source.strip():
        return True, "economic calendar unavailable"
    if snapshot.fetched_at.tzinfo is None or snapshot.fetched_at.utcoffset() is None:
        return True, "calendar timestamp is timezone-naive"
    age = now.astimezone(timezone.utc) - snapshot.fetched_at.astimezone(timezone.utc)
    if age < timedelta(0):
        return True, "calendar timestamp is in the future"
    if age > max_age:
        return True, "economic calendar is stale"
    for event in snapshot.events:
        if event.tzinfo is None or event.utcoffset() is None:
            return True, "event timestamp is timezone-naive"
        delta = event.astimezone(timezone.utc) - now.astimezone(timezone.utc)
        if -after <= delta <= before:
            return True, "inside configured high-impact event window"
    return False, "calendar current and outside configured event window"
