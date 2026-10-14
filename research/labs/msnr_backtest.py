"""Deterministic event-driven OHLC backtester; research-only, no broker transport.

Signals are known only after their signal candle closes and can enter no earlier
than the next candle's open. Prices are assumed to be mid-price OHLC; the engine
applies a configurable half-spread and adverse slippage on each fill. This is a
generic price-difference research model, NOT a Deriv contract payout model.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Literal, Sequence

Side = Literal["LONG", "SHORT"]
ExitReason = Literal["STOP", "TARGET", "END_OF_DATA"]


class BacktestInputError(ValueError):
    """Raised when input data or assumptions are invalid."""


@dataclass(frozen=True)
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class TradeSignal:
    signal_index: int
    side: Side
    stop_distance: float
    target_distance: float
    probability: float


@dataclass(frozen=True)
class BacktestConfig:
    units: float = 1.0
    spread: float = 0.0
    slippage_per_fill: float = 0.0
    commission_per_unit_round_trip: float = 0.0
    min_probability: float = 0.55
    max_probability: float = 0.75


@dataclass(frozen=True)
class Trade:
    signal_index: int
    entry_index: int
    exit_index: int
    side: Side
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    exit_reason: ExitReason
    net_pnl: float
    probability: float


@dataclass(frozen=True)
class BacktestResult:
    trades: tuple[Trade, ...]
    skipped_signals: tuple[tuple[int, str], ...]
    ending_equity: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    win_rate: float
    max_drawdown: float
    expectancy: float


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool):
        raise BacktestInputError(f"{name.upper()}_INVALID")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise BacktestInputError(f"{name.upper()}_INVALID") from exc
    if not isfinite(result):
        raise BacktestInputError(f"{name.upper()}_NONFINITE")
    return result


def _validate(candles: Sequence[Candle], signals: Sequence[TradeSignal], cfg: BacktestConfig) -> None:
    if len(candles) < 2:
        raise BacktestInputError("AT_LEAST_TWO_CANDLES_REQUIRED")
    previous_time = None
    for i, c in enumerate(candles):
        if previous_time is not None and c.timestamp <= previous_time:
            raise BacktestInputError("CANDLE_TIMESTAMPS_MUST_STRICTLY_INCREASE")
        previous_time = c.timestamp
        o, h, l, cl = (_finite(getattr(c, k), k) for k in ("open", "high", "low", "close"))
        if l > min(o, cl) or h < max(o, cl) or l > h:
            raise BacktestInputError(f"CANDLE_OHLC_INVALID_AT_{i}")
    for name in ("units", "spread", "slippage_per_fill", "commission_per_unit_round_trip",
                 "min_probability", "max_probability"):
        _finite(getattr(cfg, name), name)
    if cfg.units <= 0 or cfg.spread < 0 or cfg.slippage_per_fill < 0 or cfg.commission_per_unit_round_trip < 0:
        raise BacktestInputError("COSTS_AND_UNITS_OUT_OF_RANGE")
    if not 0 <= cfg.min_probability <= cfg.max_probability <= 1:
        raise BacktestInputError("PROBABILITY_BOUNDS_INVALID")
    seen = set()
    for s in signals:
        if isinstance(s.signal_index, bool) or not isinstance(s.signal_index, int):
            raise BacktestInputError("SIGNAL_INDEX_MUST_BE_INTEGER")
        if s.signal_index < 0 or s.signal_index >= len(candles) - 1:
            raise BacktestInputError("SIGNAL_REQUIRES_A_FOLLOWING_CANDLE")
        if s.signal_index in seen:
            raise BacktestInputError("DUPLICATE_SIGNAL_INDEX")
        seen.add(s.signal_index)
        if s.side not in ("LONG", "SHORT"):
            raise BacktestInputError("SIGNAL_SIDE_INVALID")
        if _finite(s.stop_distance, "stop_distance") <= 0 or _finite(s.target_distance, "target_distance") <= 0:
            raise BacktestInputError("STOP_AND_TARGET_DISTANCES_MUST_BE_POSITIVE")
        _finite(s.probability, "probability")


def run_backtest(
    candles: Iterable[Candle],
    signals: Iterable[TradeSignal],
    config: BacktestConfig = BacktestConfig(),
    *,
    initial_equity: float = 0.0,
) -> BacktestResult:
    """Run one-position-at-a-time replay; all signals occur at candle close.

    If both stop and target are touched within one OHLC candle, stop wins
    conservatively because intrabar ordering is unknowable from OHLC alone.
    Signals generated while a position is open are skipped. Any open position
    is marked out at the last candle close, with normal exit costs.
    """
    bars = tuple(candles)
    sigs = tuple(signals)
    equity0 = _finite(initial_equity, "initial_equity")
    _validate(bars, sigs, config)
    by_index = {s.signal_index: s for s in sigs}
    trades: list[Trade] = []
    skipped: list[tuple[int, str]] = []
    equity_curve = [equity0]
    position = None
    half_spread = config.spread / 2.0
    slip = config.slippage_per_fill

    def close_position(exit_index: int, raw_exit: float, reason: ExitReason) -> None:
        nonlocal position
        p = position
        exit_fill = raw_exit - half_spread - slip if p["side"] == "LONG" else raw_exit + half_spread + slip
        direction = 1.0 if p["side"] == "LONG" else -1.0
        pnl = direction * (exit_fill - p["entry"]) * config.units
        pnl -= config.commission_per_unit_round_trip * config.units
        trades.append(Trade(
            signal_index=p["signal_index"], entry_index=p["entry_index"], exit_index=exit_index,
            side=p["side"], entry_price=p["entry"], exit_price=exit_fill,
            stop_price=p["stop"], target_price=p["target"], exit_reason=reason,
            net_pnl=pnl, probability=p["probability"],
        ))
        equity_curve.append(equity_curve[-1] + pnl)
        position = None

    for i, bar in enumerate(bars):
        # If a position was open at this bar's open, a signal from the previous
        # candle was formed while that position was still open. It remains
        # ineligible even if this bar subsequently exits the existing position.
        position_was_open_at_open = position is not None
        if position is not None:
            long_side = position["side"] == "LONG"
            stop_hit = bar.low <= position["stop"] if long_side else bar.high >= position["stop"]
            target_hit = bar.high >= position["target"] if long_side else bar.low <= position["target"]
            if stop_hit:
                stop_exit = min(position["stop"], bar.open) if long_side else max(position["stop"], bar.open)
                close_position(i, stop_exit, "STOP")
            elif target_hit:
                close_position(i, position["target"], "TARGET")

        signal = by_index.get(i - 1)
        if signal is None:
            continue
        if signal.probability < config.min_probability or signal.probability > config.max_probability:
            skipped.append((signal.signal_index, "PROBABILITY_OUT_OF_POLICY"))
            continue
        if position_was_open_at_open or position is not None:
            skipped.append((signal.signal_index, "POSITION_ALREADY_OPEN"))
            continue
        entry = bar.open + half_spread + slip if signal.side == "LONG" else bar.open - half_spread - slip
        stop = entry - signal.stop_distance if signal.side == "LONG" else entry + signal.stop_distance
        target = entry + signal.target_distance if signal.side == "LONG" else entry - signal.target_distance
        position = {
            "signal_index": signal.signal_index, "entry_index": i, "side": signal.side,
            "entry": entry, "stop": stop, "target": target, "probability": signal.probability,
        }
        stop_hit = bar.low <= stop if signal.side == "LONG" else bar.high >= stop
        target_hit = bar.high >= target if signal.side == "LONG" else bar.low <= target
        if stop_hit:
            stop_exit = min(stop, bar.open) if signal.side == "LONG" else max(stop, bar.open)
            close_position(i, stop_exit, "STOP")
        elif target_hit:
            close_position(i, target, "TARGET")

    if position is not None:
        close_position(len(bars) - 1, bars[-1].close, "END_OF_DATA")

    pnls = [t.net_pnl for t in trades]
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    peak = equity0
    max_dd = 0.0
    for eq in equity_curve:
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
    return BacktestResult(
        trades=tuple(trades), skipped_signals=tuple(skipped),
        ending_equity=equity_curve[-1], gross_profit=gross_profit, gross_loss=gross_loss,
        profit_factor=(gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else None)),
        win_rate=(sum(p > 0 for p in pnls) / len(pnls) if pnls else 0.0),
        max_drawdown=max_dd, expectancy=(sum(pnls) / len(pnls) if pnls else 0.0),
    )
