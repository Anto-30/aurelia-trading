from datetime import datetime, timedelta, timezone

from research.labs.signal_conflict import SweepLevel, liquidity_sweep_candidate, resolve_signal_conflict

UTC = timezone.utc


def test_high_sweep_requires_close_back_below_known_level():
    start = datetime(2026, 10, 12, 14, 0, tzinfo=UTC)
    level = SweepLevel(100.0, "prior_high", start - timedelta(hours=1), "prior-session-high")
    kwargs = dict(bar_start=start, bar_end=start + timedelta(minutes=5), open_price=99.5,
                  high=101.0, low=99.0, complete=True, level=level,
                  decision_time=start + timedelta(minutes=5))
    confirmed = liquidity_sweep_candidate(close=99.8, **kwargs)
    not_confirmed = liquidity_sweep_candidate(close=100.2, **kwargs)
    assert confirmed["direction"] == "SHORT"
    assert not_confirmed["strategy"] == "NO_TRADE"


def test_low_sweep_returns_long_only_after_close_back_above():
    start = datetime(2026, 10, 12, 14, 0, tzinfo=UTC)
    level = SweepLevel(100.0, "prior_low", start - timedelta(hours=1), "prior-session-low")
    result = liquidity_sweep_candidate(bar_start=start, bar_end=start + timedelta(minutes=5),
        open_price=100.5, high=101.0, low=99.0, close=100.2, complete=True,
        level=level, decision_time=start + timedelta(minutes=5))
    assert result["direction"] == "LONG"


def test_rejects_level_not_known_before_bar_and_future_bar():
    start = datetime(2026, 10, 12, 14, 0, tzinfo=UTC)
    late_level = SweepLevel(100.0, "prior_high", start, "invalid-level")
    result = liquidity_sweep_candidate(bar_start=start, bar_end=start + timedelta(minutes=5),
        open_price=99.5, high=101.0, low=99.0, close=99.8, complete=True,
        level=late_level, decision_time=start + timedelta(minutes=5))
    assert result["strategy"] == "NO_TRADE"
    earlier_level = SweepLevel(100.0, "prior_high", start - timedelta(hours=1), "known-level")
    future = liquidity_sweep_candidate(bar_start=start, bar_end=start + timedelta(minutes=5),
        open_price=99.5, high=101.0, low=99.0, close=99.8, complete=True,
        level=earlier_level, decision_time=start + timedelta(minutes=4))
    assert future["strategy"] == "NO_TRADE"


def test_conflicting_directional_modules_resolve_to_no_trade():
    orb = {"strategy": "ORB_CLOSE", "direction": "LONG"}
    sweep = {"strategy": "LIQUIDITY_SWEEP", "direction": "SHORT"}
    result = resolve_signal_conflict(orb, sweep)
    assert result["strategy"] == "NO_TRADE"
    assert result["direction"] == "NONE"


def test_same_direction_multiple_modules_are_not_silently_combined():
    orb = {"strategy": "ORB_CLOSE", "direction": "LONG"}
    sweep = {"strategy": "LIQUIDITY_SWEEP", "direction": "LONG"}
    assert resolve_signal_conflict(orb, sweep)["strategy"] == "NO_TRADE"
