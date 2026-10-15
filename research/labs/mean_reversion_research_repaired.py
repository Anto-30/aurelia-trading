"""Research-only mean-reversion replay and an illustrative Layer 6 guard.

This module is not registered in the runtime, is not a Deriv adapter, and does
not qualify a strategy. Signals use completed closes; execution occurs no earlier
than the next supplied open. The caller is responsible for data provenance,
chronology, gaps, corporate/action adjustments where applicable, and realistic
instrument-specific execution costs.

The drawdown and Ulcer metrics are measured on completed-trade equity, not
intrabar mark-to-market equity. A close-only simulator cannot estimate the latter.
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


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _positive_equity(value: object) -> bool:
    return _finite_number(value) and float(value) > 0


class Layer6RiskEngine:
    """Fail-closed in-memory research guard; never submits or manages broker orders.

    Baselines use caller-supplied period starts. The caller must roll daily and
    weekly anchors at the correct calendar boundaries. A breach is sticky: rolling
    an anchor cannot clear a halt. This object is not durable across restarts and
    must not be used as a production risk control.
    """

    def __init__(
        self,
        max_daily_drawdown_pct: float,
        max_position_size: float,
        account_equity: float,
        max_weekly_drawdown_pct: float = 0.05,
    ) -> None:
        vals = (max_daily_drawdown_pct, max_weekly_drawdown_pct,
                max_position_size, account_equity)
        if not all(_finite_number(x) for x in vals):
            raise ValueError("Risk parameters must be finite numbers")
        if not 0 < max_daily_drawdown_pct < 1 or not 0 < max_weekly_drawdown_pct < 1:
            raise ValueError("Drawdown thresholds must be in (0, 1)")
        if max_position_size <= 0 or account_equity <= 0:
            raise ValueError("Position limit and equity must be positive")
        self.max_daily_drawdown_pct = float(max_daily_drawdown_pct)
        self.max_weekly_drawdown_pct = float(max_weekly_drawdown_pct)
        self.max_position_size = float(max_position_size)
        self.start_of_day_equity = float(account_equity)
        self.start_of_week_equity = float(account_equity)
        self.halted = False

    def check_circuit_breaker(self, current_equity: float) -> bool:
        if not _positive_equity(current_equity):
            self.halted = True
            return True
        daily = (self.start_of_day_equity - current_equity) / self.start_of_day_equity
        weekly = (self.start_of_week_equity - current_equity) / self.start_of_week_equity
        if daily >= self.max_daily_drawdown_pct or weekly >= self.max_weekly_drawdown_pct:
            self.halted = True
        return self.halted

    def roll_day_baseline(self, current_equity: float) -> bool:
        """Set the new day anchor when called at a verified day boundary.

        Does not clear a halt. Invalid/stale equity is the caller's responsibility
        to prevent; invalid numeric values fail closed by setting the halt.
        """
        if not _positive_equity(current_equity):
            self.halted = True
            return False
        if self.halted:
            return False
        self.start_of_day_equity = float(current_equity)
        return True

    def roll_week_baseline(self, current_equity: float) -> bool:
        """Set the new week anchor when called at a verified week boundary."""
        if not _positive_equity(current_equity):
            self.halted = True
            return False
        if self.halted:
            return False
        self.start_of_week_equity = float(current_equity)
        return True

    def validate_net_position(self, current_position: float, proposed_delta: float) -> bool:
        if self.halted or not _finite_number(current_position) or not _finite_number(proposed_delta):
            return False
        return abs(float(current_position) + float(proposed_delta)) <= self.max_position_size


def _prices(values: Iterable[float], label: str) -> list[float]:
    result = list(values)
    if len(result) < 2 or any(not _finite_number(x) or x <= 0 for x in result):
        raise ValueError(f"{label} must contain at least two finite positive prices")
    return [float(x) for x in result]


def _rolling_zscores(prices: list[float], window: int) -> tuple[Optional[float], ...]:
    """Rolling sample z-scores; a prefix gives identical values for its shared bars."""
    zscores: list[Optional[float]] = [None] * len(prices)
    for i in range(window - 1, len(prices)):
        sample = prices[i - window + 1 : i + 1]
        mean = sum(sample) / window
        variance = sum((x - mean) ** 2 for x in sample) / (window - 1)
        sd = variance ** 0.5
        if sd > 0:
            zscores[i] = (prices[i] - mean) / sd
    return tuple(zscores)


def run_mean_reversion_backtest(
    closes: Iterable[float],
    *,
    opens: Optional[Iterable[float]] = None,
    window: int = 20,
    z_threshold: float = 2.0,
    per_side_cost_bps: float = 2.0,
) -> BacktestResult:
    """One-position mean reversion; enter next open, exit when z-score crosses mean.

    A prior completed close outside +/- z_threshold creates the next-bar entry
    intent. A position exits at the next open after the prior completed close's
    z-score crosses zero. On an opposite threshold, the current position closes;
    the opposite position cannot open until a later bar. Any still-open position
    is liquidated at the final close. This simple model omits intrabar stops,
    spread dynamics, rejects, requotes, measured latency, financing, leverage,
    payout schedules, and broker-confirmed fills.

    Costs are deducted as two fixed notional bps charges per completed trade.
    This is an explicit placeholder, not a claim about actual costs. Profit factor
    is None if there are no gross losses (rather than Infinity, which is not JSON
    interoperable). Returns and drawdowns are fractions (0.01 == 1%).
    """
    close = _prices(closes, "closes")
    op = _prices(opens, "opens") if opens is not None else close[:]
    if len(op) != len(close):
        raise ValueError("opens and closes must have equal length")
    if isinstance(window, bool) or not isinstance(window, int) or window < 2:
        raise ValueError("window must be an integer >= 2")
    if not _finite_number(z_threshold) or z_threshold <= 0:
        raise ValueError("z_threshold must be finite and positive")
    if not _finite_number(per_side_cost_bps) or per_side_cost_bps < 0:
        raise ValueError("per_side_cost_bps must be finite and non-negative")

    zscores = _rolling_zscores(close, window)
    trades: list[Trade] = []
    direction, entry, entry_i = 0, 0.0, 0
    side_cost = float(per_side_cost_bps) / 10000.0

    def finish(price: float, i: int) -> None:
        nonlocal direction, entry, entry_i
        if direction == 0:
            return
        gross = direction * (price - entry) / entry
        costs = 2 * side_cost
        trades.append(Trade(direction, entry, price, gross, costs,
                            gross - costs, max(0, i - entry_i)))
        direction, entry, entry_i = 0, 0.0, 0

    for i in range(1, len(close)):
        z = zscores[i - 1]  # only information known at the previous completed close
        if z is None:
            continue
        if (direction == -1 and z <= 0) or (direction == 1 and z >= 0):
            finish(op[i], i)
            continue
        if direction == 0:
            if z >= z_threshold:
                direction, entry, entry_i = -1, op[i], i
            elif z <= -z_threshold:
                direction, entry, entry_i = 1, op[i], i
    finish(close[-1], len(close) - 1)

    if not trades:
        return BacktestResult((), 0.0, None, 0.0, 0.0, 0.0, 0.0)
    returns = [t.net_return for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    equity, peak, drawdowns = 1.0, 1.0, []
    for trade_return in returns:
        equity *= max(0.0, 1.0 + trade_return)
        peak = max(peak, equity)
        drawdowns.append(equity / peak - 1.0)
    max_drawdown = min(drawdowns, default=0.0)
    ulcer_index = (sum(dd * dd for dd in drawdowns) / len(drawdowns)) ** 0.5
    return BacktestResult(
        tuple(trades),
        sum(returns) / len(returns),
        profit_factor,
        len(wins) / len(returns),
        max_drawdown,
        ulcer_index,
        equity - 1.0,
    )
