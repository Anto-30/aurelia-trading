from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timezone

import pytest

from research.labs.silver_bullet import (
    BacktestConfig,
    Candle,
    DerivCandleClient,
    FVG,
    SessionWindow,
    TradeFill,
    compute_metrics,
    detect_fvg,
    get_window_bounds,
    is_in_window,
    simulate_trade_path,
    validate_candles,
    validate_complete_coverage,
)


def candle(minute: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(epoch=minute * 60, open=o, high=h, low=l, close=c)


def test_ny_window_epoch_shifts_for_dst_without_manual_offsets():
    window = SessionWindow("NY_AM", time(10, 0), time(11, 0))
    winter = get_window_bounds(date(2026, 1, 15), window)
    summer = get_window_bounds(date(2026, 7, 15), window)
    assert winter.start_epoch == int(datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc).timestamp())
    assert summer.start_epoch == int(datetime(2026, 7, 15, 14, 0, tzinfo=timezone.utc).timestamp())
    assert winter.end_epoch - winter.start_epoch == 3600
    assert summer.end_epoch - summer.start_epoch == 3600


def test_window_uses_start_inclusive_end_exclusive_and_second_precision():
    window = SessionWindow("NY_AM", time(10, 0), time(11, 0))
    start, end = get_window_bounds(date(2026, 7, 15), window).start_epoch, get_window_bounds(date(2026, 7, 15), window).end_epoch
    assert is_in_window(start, start, end)
    assert is_in_window(end - 1, start, end)
    assert not is_i¶»§q«^