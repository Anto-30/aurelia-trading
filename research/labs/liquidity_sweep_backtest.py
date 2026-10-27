"""Deterministic OHLC backtester for research-only candidate signals.

Assumptions are explicit: fixed quantity, account-currency commission per side,
adverse slippage in basis points, stop-first resolution when OHLC touches both
stop and target on one candle, and conservative gap-through-stop fills.
No stake-sizing policy or broker execution is implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Iterable, Sequence

from research.labs.liquidity_sweep_strategy import (
    OHLCBar, ResearchSignal, _parse_bar,
)

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float
    quantity: float
    commission_per_side: float
    slippage_bps: float

    def __post_init__(self) -> None:
        values = (self.initial_capital, self.quantity,
                  self.commission_per_side, self.slippage_bps)
        if not all(math.isfinite(float(v)) for v in values):
            raise ValueError("backtest configuration values must be finite")
        if self.initial_capital <= 0 or self.quantity <= 0:
            raise ValueError("initial_capital and quantity must be positive")
        if self.commission_per_side < 0 or self.slippage_bps < 0:
            raise ValueError("commission and slippage must be non-negative")


@dataclass(frozen=True)
class BacktestResult:
    trade_ledger: tuple[dict[str, object], ...]
    rejection_ledger: tuple[dict[str, object], ...]
    equity_curve: tuple[float, ...]
    metrics: dict[str, float | int]


def _slipped(price: float, direction: str, *, entry: bool, bps: float) -> float:
    """Apply adverse execution slippage to a buy/sell implied by trade direction."""
    slip = price * bps / 10_000.0
    is_buy = (direction == "long" and entry) or (direction == "short" and not entry)
    return price + slip if is_buy else price - slip


def _valid_series(raw_bars: Iterable[OHLCBar]) -> list[OHLCBar]:
    bars = [_parse_bar(item) for item in raw_bars]
    times = [datetime.fromisoformat(item.timestamp_utc.replace("Z", "+00:00")) for item in bars]
    if any(left >= right for left, right in zip(times, times[1:])):
        raise ValueError("bar timestamps must be strictly increasing")
    return bars


def run_backtest(
    raw_bars: Sequence[OHLCBar],
    signals: Sequence[ResearchSignal],
    config: BacktestConfig,
) -> BacktestResult:
    """Simulate signals on the supplied OHLC series, using no unstated costs."""
    bars = _valid_series(raw_bars)
    trade_ledger: list[dict[str, object]] = []
    rejection_ledger: list[dict[str, object]] = []
    equity_curve = [float(config.initial_capital)]
    equity = float(config.initial_capital)
    peak = equity
    max_drawdown = 0.0
    last_exit_index = -1

    ordered = sorted(signals, key=lambda signal: (signal.entry_index, signal.confirmation_index))
    for signal in ordered:
        if signal.direction not in ("long", "short"):
            rejection_ledger.append({"confirmation_index": signal.confirmation_index, "reason": "INVALID_DIRECTION"})
            continue
        if not (0 <= signal.entry_index < len(bars)):
            rejection_ledger.append({"confirmation_index": signal.confirmation_index, "reason": "ENTRY_INDEX_OUT_OF_RANGE"})
            continue
        if signal.entry_index <= last_exit_index:
            rejection_ledger.append({"confirmation_index": signal.confirmation_index, "reason": "OVERLAPPING_POSITION"})
            continue
        if not all(math.isfinite(v) for v in (
            signal.entry_price, signal.stop_price, signal.target_price, signal.reward_risk
        )):
            rejection_ledger.append({"confirmation_index": signal.confirmation_index, "reason": "NONFINITE_SIGNAL"})
            continue
        entry_bar = bars[signal.entry_index]
        # Reprice from the supplied bar's actual open; never trust a stale
        # cached entry price if data and signal ledger differ.
        raw_entry = entry_bar.open
        entry = _slipped(raw_entry, signal.direction, entry=True, bps=config.slippage_bps)
        stop = signal.stop_price
        target = signal.target_price
        if signal.direction == "long" and not (stop < entry < target):
            rejection_ledger.append({"confirmation_index": signal.confirmation_index, "reason": "INVALID_LONG_LEVELS"})
            continue
        if signal.direction == "short" and not (target < entry < stop):
            rejection_ledger.append({"confirmation_index": signal.confirmation_index, "reason": "INVALID_SHORT_LEVELS"})
            continue

        exit_index: int | None = None
        raw_exit: float | None = None
        exit_reason: str | None = None
        for idx in range(signal.entry_index, len(bars)):
            candle = bars[idx]
            if signal.direction == "long":
                stop_hit = candle.low <= stop
                target_hit = candle.high >= target
                if stop_hit:
                    raw_exit = min(stop, candle.open)  # gap-through-stop is filled at worse open
                    exit_reason = "STOP"
                elif target_hit:
                    raw_exit = target
                    exit_reason = "TARGET"
            else:
                stop_hit = candle.high >= stop
                target_hit = candle.low <= target
                if stop_hit:
                    raw_exit = max(stop, candle.open)
                    exit_reason = "STOP"
                elif target_hit:
                    raw_exit = target
                    exit_reason = "TARGET"
            if exit_reason is not None:
                exit_index = idx
                break
        if exit_index is None:
            exit_index = len(bars) - 1
            raw_exit = bars[exit_index].close
            exit_reason = "END_OF_DATA"

        assert raw_exit is not None
        exit_price = _slipped(raw_exit, signal.direction, entry=False, bps=config.slippage_bps)
        gross_pnl = (
            (exit_price - entry) * config.quantity
            if signal.direction == "long"
            else (entry - exit_price) * config.quantity
        )
        commission = 2.0 * config.commission_per_side
        net_pnl = gross_pnl - commission
        risk_per_unit = abs(entry - stop)
        risk_cash = risk_per_unit * config.quantity
        r_multiple = net_pnl / risk_cash if risk_cash > 0 else 0.0
        equity += net_pnl
        equity_curve.append(equity)
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak if peak > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        trade_ledger.append({
            "direction": signal.direction,
            "confirmation_index": signal.confirmation_index,
            "entry_index": signal.entry_index,
            "entry_timestamp_utc": entry_bar.timestamp_utc,
            "entry_price": entry,
            "exit_index": exit_index,
            "exit_timestamp_utc": bars[exit_index].timestamp_utc,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "quantity": config.quantity,
            "gross_pnl": gross_pnl,
            "commission": commission,
            "net_pnl": net_pnl,
            "r_multiple": r_multiple,
        })
        last_exit_index = exit_index

    pnls = [float(trade["net_pnl"]) for trade in trade_ledger]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    metrics: dict[str, float | int] = {
        "total_trades": len(pnls),
        "rejected_signals": len(rejection_ledger),
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
        "expectancy_per_trade": sum(pnls) / len(pnls) if pnls else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else (math.inf if gross_profit > 0 else 0.0),
        "max_drawdown": max_drawdown,
        "net_pnl": sum(pnls),
        "ending_equity": equity,
        "commission_paid": sum(float(t["commission"]) for t in trade_ledger),
        "average_r_multiple": (
            sum(float(t["r_multiple"]) for t in trade_ledger) / len(trade_ledger)
            if trade_ledger else 0.0
        ),
    }
    return BacktestResult(tuple(trade_ledger), tuple(rejection_ledger), tuple(equity_curve), metrics)


def run_walk_forward(
    raw_bars: Sequence[OHLCBar],
    signal_factory,
    config: BacktestConfig,
    *,
    train_window: int,
    test_window: int,
) -> list[dict[str, object]]:
    """Run chronological test folds; callback receives train bars and test bars.

    signal_factory(train_bars, test_bars) must return signals indexed locally
    to test_bars. This prevents accidental use of global test indices. Training
    data may calibrate parameters, but test candles must not influence them.
    """
    bars = _valid_series(raw_bars)
    if isinstance(train_window, bool) or not isinstance(train_window, int) or train_window <= 0:
        raise ValueError("train_window must be a positive integer")
    if isinstance(test_window, bool) or not isinstance(test_window, int) or test_window <= 0:
        raise ValueError("test_window must be a positive integer")
    folds: list[dict[str, object]] = []
    start = 0
    while start + train_window + test_window <= len(bars):
        train_end = start + train_window
        test_end = train_end + test_window
        train = bars[start:train_end]
        test = bars[train_end:test_end]
        signals = signal_factory(train, test)
        result = run_backtest(test, signals, config)
        folds.append({
            "train_start": train[0].timestamp_utc,
            "train_end": train[-1].timestamp_utc,
            "test_start": test[0].timestamp_utc,
            "test_end": test[-1].timestamp_utc,
            "metrics": result.metrics,
            "trade_ledger": result.trade_ledger,
            "rejection_ledger": result.rejection_ledger,
        })
        start += test_window
    if not folds:
        raise ValueError("data is too short for one complete walk-forward fold")
    return folds
