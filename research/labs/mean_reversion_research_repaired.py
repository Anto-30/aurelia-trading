"""Research-only, bar-based mean-reversion backtest primitives.

Not a Deriv adapter and not strategy qualification. Signals use completed bars;
execution is no earlier than the next bar open. Costs are charged on trade sides.
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


class Layer6RiskEngine:
    """Fail-closed research guard; does not submit or manage broker orders."""
    def __init__(self, max_daily_drawdown_pct: float, max_position_size: float,
                 account_equity: float, max_weekly_drawdown_pct: float = 0.05):
        vals = (max_daily_drawdown_pct, max_weekly_drawdown_pct,
                max_position_size, account_equity)
        if not all(isfinite(x) for x in vals):
            raise ValueError("Risk parameters must be finite")
        if not 0 < max_daily_drawdown_pct < 1 or not 0 < max_weekly_drawdown_pct < 1:
            raise ValueError("Drawdown thresholds must be in (0, 1)")
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
        daily = (self.start_of_day_equity - current_equity) / self.start_of_day_equity
        weekly = (self.start_of_week_equity - current_equity) / self.start_of_week_equity
        if daily >= self.max_daily_drawdown_pct or weekly >= self.max_weekly_drawdown_pct:
            self.halted = True
        return self.halted

    def validate_net_position(self, current_position: float, proposed_delta: float) -> bool:
        if self.halted or not isfinite(current_position) or not isfinite(proposed_delta):
            return False
        return abs(current_position + proposed_delta) <= self.max_position_size


def _prices(values: Iterable[float], label: str) -> list[float]:
    result = list(values)
    if len(result) < 2 or any(not isfinite(x) or x <= 0 for x in result):
        raise ValueError(f"{label} must contain at least two finite positive prices")
    return result


def run_mean_reversion_backtest(closes: Iterable[float], *,
        opens: Optional[Iterable[float]] = None, window: int = 20,
        z_threshold: float = 2.0, per_side_cost_bps: float = 2.0) -> BacktestResult:
    """One-position Z-score mean reversion, entering next open and exiting at mean.

    Uses a sample standard deviation. Reversal signals close an existing position;
    a new opposite position is not opened on the same bar. The last position is
    liquidated at the last close. This simplified close/open model does not model
    intrabar stops, spread dynamics, rejects, latency, or contract payout mechanics.
    """
    close = _prices(closes, "closes")
    op = _prices(opens, "opens") if opens is not None else close[:]
    if len(op) != len(close):
        raise ValueError("opens and closes must have equal length")
    if not isinstance(window, int) or window < 2:
        raise ValueError("window must be an integer >= 2")
    if not isfinite(z_threshold) or z_threshold <= 0:
        raise ValueError("z_threshold must be finite and positive")
    if not isfinite(per_side_cost_bps) or per_side_cost_bps < 0:
        raise ValueError("per_side_cost_bps must be finite and non-negative")

    zscores: list[Optional[float]] = [None] * len(close)
    for i in range(window - 1, len(close)):
        sample = close[i-window+1:i+1]
        mean = sum(sample) / window
        sd = (sum((x-mean)**2 for x in sample) / (window-1))**0.5
        if sd > 0:
            zscores[i] = (close[i]-mean)/sd

    trades: list[Trade] = []
    direction, entry, entry_i = 0, 0.0, 0
    side_cost = per_side_cost_bps / 10000.0

    def finish(price: float, i: int) -> None:
        nonlocal direction, entry, entry_i
        if direction == 0:
            return
        gross = direction * (price-entry) / entry
        costs = 2 * side_cost
        trades.append(Trade(direction, entry, price, gross, costs, gross-costs, max(0, i-entry_i)))
        direction, entry, entry_i = 0, 0.0, 0

    for i in range(1, len(close)):
        z = zscores[i-1]  # only information available at prior completed close
        if z is None:
            continue
        if direction == -1 and z <= 0 or direction == 1 and z >= 0:
            finish(op[i], i)
            continue
        if direction == 0:
            if z >= z_threshold:
                direction, entry, entry_i = -1, op[i], i
            elif z <= -z_threshold:
                direction, entry, entry_i = 1, op[i], i
    finish(close[-1], len(close)-1)

    if not trades:
        return BacktestResult((), 0.0, None, 0.0, 0.0, 0.0, 0.0)
    rs = [t.net_return for t in trades]
    wins, losses = [r for r in rs if r > 0], [r for r in rs if r < 0]
    gp, gl = sum(wins), abs(sum(losses))
    pf = gp/gl if gl else (float("inf") if gp else None)
    equity, peak, dd = 1.0, 1.0, []
    for r in rs:
        equity *= max(0.0, 1+r)
        peak = max(peak, equity)
        dd.append((equity/peak - 1)*100)
    return BacktestResult(tuple(trades), sum(rs)/len(rs), pf,
        len(wins)/len(rs), min(dd, default=0)/100,
        (sum(x*x for x in dd)/len(dd))**0.5/100, equity-1)
