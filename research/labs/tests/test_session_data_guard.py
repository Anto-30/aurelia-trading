from datetime import datetime, timedelta, timezone

import pytest

from research.labs.session_data_guard import (
    CalendarSnapshot,
    Candle,
    news_window_blocked,
    validate_candle_series,
)

UTC = timezone.utc


def candle(start_minute, *, complete=True):
    start = datetime(2026, 10, 11, 13, start_minute, tzinfo=UTC)
    return Candle(start, start + timedelta(minutes=1), 100, 102, 99, 101, 10, complete)


def test_rejects_naive_timestamp():
    c = candle(0)
    with pytest.raises(ValueError, match="timezone-aware"):
        Candle(c.start.replace(tzinfo=None), c.end, 100, 102, 99, 101, 10).validate()


def test_rejects_unfinished_candle_even_if_marked_complete():
    c = candle(1)
    with pytest.raises(ValueError, match="not ended"):
        validate_candle_series([c], now=c.end - timedelta(seconds=1))


def test_rejects_duplicate_or_unordered_candles():
    c0, c1 = candle(0), candle(1)
    with pytest.raises(ValueError, match="unique and ordered"):
        validate_candle_series([c1, c0])
    with pytest.raises(ValueError, match="unique and ordered"):
        validate_candle_series([c0, c0])


def test_rejects_overlap_and_interval_mismatch():
    c0 = candle(0)
    overlap = Candle(c0.start + timedelta(seconds=30), c0.end + timedelta(seconds=30), 100, 102, 99, 101, 10)
    with pytest.raises(ValueError, match="overlapping"):
        validate_candle_series([c0, overlap])
    wrong = Candle(c0.start, c0.end + timedelta(seconds=1), 100, 102, 99, 101, 10)
    with pytest.raises(ValueError, match="interval mismatch"):
        validate_candle_series([wrong], expected_interval=timedelta(minutes=1))


def test_calendar_missing_or_stale_fails_closed():
    now = datetime(2026, 10, 11, 13, 0, tzinfo=UTC)
    assert news_window_blocked(None, now=now)[0]
    stale = CalendarSnapshot(now - timedelta(minutes=16), (), "test")
    assert news_window_blocked(stale, now=now)[0]


def test_calendar_blocks_event_window_and_allows_fresh_clear_window():
    now = datetime(2026, 10, 11, 13, 0, tzinfo=UTC)
    event = CalendarSnapshot(now - timedelta(minutes=1), (now + timedelta(minutes=10),), "test")
    assert news_window_blocked(event, now=now)[0]
    clear = CalendarSnapshot(now - timedelta(minutes=1), (now + timedelta(hours=2),), "test")
    assert not news_window_blocked(clear, now=now)[0]
