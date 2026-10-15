"""Research-only, bar-based mean-reversion backtest primitives.

This module is deliberately not a Deriv execution adapter and does not qualify a
strategy. Signals are computed using completed bars and executed no earlier than
the next bar's open. Costs are charged on position changes, not on every bar.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Optional


@dataclass(frozen=True)
class Trade:
    direction: int
    entry_price: float
    exit_price: float
    gross_return: float
    cost_return: float
    net_return: float
    bars_held: int


@dataclass(frozen=True)
class BacktestResult:
    trades: tuple[Trade, ...]
    expectancy: float
    profit_factor: Optional[float]
    win_rate: float
    max_drawdown: float
    ulcer_index: float
    total_return: float


class RiskHalt(Exception):
    """Raised when inputs are invalid or a risk circuit breaker is active."""


class Layer6RiskEngine:
    """Fail-closed research risk guard; it never submits or manages broker orders."""

    def __init__(
        self,
        max_daily_drawdown_pct: float,
        max_position_size: float,
        account_equity: float,
        max_weekly_drawdown_pct: float = 0.05,
    ) -> None:
        values = (
            max_daily_drawdown_pct,
            max_weekly_drawdown_pct,
            max_position_size,
            account_equity,
        )
        if not all(isfinite(x) for x in values):
            raise ValueError("Risk parameters must be finite")
        if not (0 < max_daily_drawdown_pct < 1):
            raise ValueError("Daily drawdown threshold must be in (0, 1)")
        if not (0 < max_weekly_drawdown_pct < 1):
            raise ValueError("Weekly drawdown threshold must be in (0, 1)")
        if max_position_size <= 0 or account_equity <= 0:
            raise ValueError("Position limit and equity must be positive")
        self.max_daily_drawdown_pct = max_daily_drawdown_pct
        self.max_weekly_drawdown_pct = max_weekly_drawdown_pct
        self.max_position_size = max_position_size
        self.start_of_day_equity = account_equity
        self.start_of_week_equity = account_equity
        self.halted = False

    def check_circuit_breaker(self, current_equity: float) -> bool:
        if not isfinite(current_equity) or current_equity <= 0:
            self.halted = True
            return True
        daily_dd = (self.start_of_day_equity - current_equity) / self.start_of_day_equity
        weekly_dd = (self.start_of_week_equity - current_equity) / self.start_of_week_equity
        if daily_dd >= self.max_daily_drawdown_pct or weekly_dd >= self.max_weekly_drawdown_pct:
            self.halted = True
        return self.halted

    def validate_net_position(self, current_position: float, proposed_delta: float) -> bool:
        if self.halted:
            return False
        if not isfinite(current_position) or not isfinite(proposed_delta):
            return False
        resulting = current_position + proposed_delta
        return abs(resulting) <= self.max_position_size


def _validate_prices(prices: Iterable[float]) -> list[float]:
    result = list(prices)
    if len(result) < 2:
        raise ValueError("At least two prices are required")
    if any(not isfinite(p) or p <= 0 for p in result):
        raise ValueError("Prices must be finite and positive")
    return result


def run_mean_reversion_backtest(
    closes: Iterable[float],
    *,
    opens: Optional[Iterable[float]] = None,
    window: int = 20,
    z_threshold: float = 2.0,
    per_side_cost_bps: float = 2.0,
) -> BacktestResult:
    """Run a conservative single-position research replay on price bars.

    A signal from close[t] is acted on at open[t+1] (or close[t+1] when opens
    are omitted). Position exits occur on a zero-crossing signal, with final
    liquidation at the final available price. Costs are charged for each
    entry/exit/reversal side. The caller must supply trustworthy, point-in-time
    bars and instrument-appropriate cost assumptions.
    """
    prices = _validate_prices(closes)
    if window < 2 or not isfinite(z_threshold) or z_threshold <= 0:
        raise ValueError("window must be >= 2 and z_threshold must be positive")
    if not isfinite(per_side_cost_bps) or per_side_cost_bps < 0:
        raise ValueError("per_side_cost_bps must be finite and non-negative")
    open_prices = list(opens) if opens is not None else prices
    if len(open_prices) != len(prices) or any(
        not isfinite(p) or p <= 0 for p in open_prices
    ):
        raise ValueError("opens must match closes and contain finite positive prices")

    signals = [0] * len(prices)
    for i in range(window - 1, len(prices)):
        sample = prices[i - window + 1 : i + 1]
        mean = sum(sample) / window
        variance = sum((x - mean) ** 2 for x in sample) / (window - 1)
        sd = variance ** 0.5
        if sd == 0:
            continue
        z = (prices[i] - mean) / sd
        if z >= z_threshold:
            signals[i] = -1
        elif z <= -z_threshold:
            signals[i] = 1

    trades: list[Trade] = []
    direction = 0
    entry = 0.0
    entry_index = 0
    cost = per_side_cost_bps / 10000.0

    def close_trade(exit_price: float, idx: int) -> None:
        nonlocal direction, entry, entry_index
        if direction == 0:
            return
        gross = direction * (exit_price - entry) / entry
        total_cost = 2 * cost
        net = gross - total_cost
        trades.append(Trade(direction, entry, exit_price, gross, total_cost, net, idx-entry_index))
        direction, entry, entry_index = 0, 0.0, 0

    for i in range(1, len(prices)):
        target = signals[i - 1]  # completed prior candle only
        execution_price = open_prices[i]
        if direction and (target == 0 or target != direction):
            close_trade(execution_price, i)
        if direction == 0 and target != 0 and i < len(prices) - 0:
            direction, entry, entry_index = target, execution_price, i

    close_trade(prices[-1], len(prices) - 1)
    if not trades:
        return BacktestResult((), 0.0, None, 0.0, 0.0, 0.0, 0.0)

    returns = [t.net_return for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else None)
    equity, peak, drawdowns = 1.0, 1.0, []
    for r in returns:
        equity *= max(0.0, 1.0 + r)
        peak = max(peak, equity)
        drawdowns.append((equity / peak - 1.0) * 100.0)
    mdd = min(drawdowns, default=0.0) / 100.0
    ulcer = (sum(d * d for d in drawdowns) / len(drawdowns)) ** 0.5 / 100.0
    return BacktestResult(
        tuple(trades),
        sum(returns) / len(returns),
        pf,
        len(wins) / len(returns),
        mdd,
        ulcer,
        equity - 1.0,
    )
