"""Deterministic OHLC backtester for research-only candidate signals.

Assumptions are explicit: fixed quantity, account-currency commission per side,
adverse slippage in basis points, stop-first resolution when OHLC touches both
stop and target on one candle, and conservative gap-through-stop fills.
No stake-sizing policy or broker execution is implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import math
from pathlib import Path
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
    usd_per_point_per_unit: float
    spread_points: float = 0.0
    slippage_points: float = 0.0

    def __post_init__(self) -> None:
        values = (self.initial_capital, self.quantity,
                  self.commission_per_side, self.slippage_bps,
                  self.usd_per_point_per_unit, self.spread_points, self.slippage_points)
        if not all(math.isfinite(float(v)) for v in values):
            raise ValueError("backtest configuration values must be finite")
        if self.initial_capital <= 0 or self.quantity <= 0 or self.usd_per_point_per_unit <= 0:
            raise ValueError("initial_capital, quantity and USD-per-point value must be positive")
        if any(value < 0 for value in (
            self.commission_per_side, self.slippage_bps,
            self.spread_points, self.slippage_points
        )):
            raise ValueError("commission, spread and slippage must be non-negative")


@dataclass(frozen=True)
class BacktestResult:
    trade_ledger: tuple[dict[str, object], ...]
    rejection_ledger: tuple[dict[str, object], ...]
    equity_curve: tuple[float, ...]
    metrics: dict[str, float | int | str | None]


def _slipped(
    price: float,
    direction: str,
    *,
    entry: bool,
    bps: float,
    slippage_points: float = 0.0,
    spread_points: float = 0.0,
) -> float:
    """Apply adverse slippage and half-spread on each side of a midpoint-price bar."""
    impact = price * bps / 10_000.0 + slippage_points + spread_points / 2.0
    is_buy = (direction == "long" and entry) or (direction == "short" and not entry)
    adjusted = price + impact if is_buy else price - impact
    if not math.isfinite(adjusted) or adjusted <= 0:
        raise ValueError("NON_POSITIVE_PRICE_AFTER_EXECUTION_COSTS")
    return adjusted


def load_verified_cost_config(config_path: str, resolution: str) -> dict[str, float | str]:
    """Load explicit costs; unknown or unverified profile blocks qualification."""
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to load config/costs.yaml") from exc
    raw_config = Path(config_path).read_bytes()
    config_sha256 = hashlib.sha256(raw_config).hexdigest()
    try:
        document = yaml.safe_load(raw_config.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("COST_CONFIG_NOT_UTF8") from exc
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("COST_CONFIG_SCHEMA_UNSUPPORTED")
    if document.get("instrument") != "R_100":
        raise ValueError("COST_CONFIG_INSTRUMENT_MISMATCH")
    if document.get("status") != "VERIFIED_SOURCE_BACKED_COSTS":
        raise ValueError("COST_CONFIG_NOT_SOURCE_VERIFIED")
    if document.get("pnl_model") != "LINEAR_INDEX_POINT_VALUE":
        raise ValueError("COST_PNL_MODEL_NOT_VERIFIED")
    if document.get("bar_price_basis") != "MIDPOINT":
        raise ValueError("BAR_PRICE_BASIS_NOT_MIDPOINT")
    if document.get("economics_verified") is not True:
        raise ValueError("CONTRACT_ECONOMICS_NOT_VERIFIED")
    try:
        slippage_multiplier = float(document.get("max_slippage_sensitivity_multiplier"))
    except (TypeError, ValueError) as exc:
        raise ValueError("MAX_SLIPPAGE_SENSITIVITY_MULTIPLIER_INVALID") from exc
    if not math.isfinite(slippage_multiplier) or slippage_multiplier < 1.0:
        raise ValueError("MAX_SLIPPAGE_SENSITIVITY_MULTIPLIER_INVALID")
    if not str(document.get("contract_type") or "").strip():
        raise ValueError("CONTRACT_TYPE_MISSING")
    try:
        usd_per_point = float(document.get("usd_per_point_per_unit"))
    except (TypeError, ValueError) as exc:
        raise ValueError("USD_PER_POINT_VALUE_UNKNOWN_OR_INVALID") from exc
    if not math.isfinite(usd_per_point) or usd_per_point <= 0:
        raise ValueError("USD_PER_POINT_VALUE_UNKNOWN_OR_INVALID")
    economic_source = str(document.get("economics_source") or "").strip()
    if not economic_source:
        raise ValueError("CONTRACT_ECONOMICS_SOURCE_MISSING")
    try:
        economic_observed = datetime.fromisoformat(
            str(document.get("economics_observed_at_utc")).replace("Z", "+00:00")
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("CONTRACT_ECONOMICS_TIMESTAMP_INVALID") from exc
    if economic_observed.tzinfo is None or economic_observed.utcoffset() is None:
        raise ValueError("CONTRACT_ECONOMICS_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    economic_age = (datetime.now(economic_observed.tzinfo) - economic_observed).total_seconds()
    if economic_age < 0 or economic_age > 86400:
        raise ValueError("CONTRACT_ECONOMICS_STALE_OR_FUTURE")
    profile = document.get("resolutions", {}).get(resolution)
    if not isinstance(profile, dict):
        raise ValueError(f"COST_PROFILE_MISSING:{resolution}")
    required = ("spread_points", "slippage_points", "commission_per_unit_usd_per_side")
    values: dict[str, float] = {}
    for key in required:
        raw = profile.get(key)
        if raw is None:
            raise ValueError(f"COST_INPUT_UNKNOWN:{resolution}:{key}")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"COST_INPUT_INVALID:{resolution}:{key}") from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"COST_INPUT_INVALID:{resolution}:{key}")
        values[key] = value
    if profile.get("verified") is not True:
        raise ValueError(f"COST_PROFILE_UNVERIFIED:{resolution}")
    accepted_statuses = ("VERIFIED_MEASURED", "VERIFIED_CONTRACT_QUOTE", "VERIFIED_NO_FEE")
    for key, label in (("spread_status", "SPREAD"), ("slippage_status", "SLIPPAGE"),
                       ("commission_status", "COMMISSION")):
        if profile.get(key) not in accepted_statuses:
            raise ValueError(f"COST_{label}_NOT_VERIFIED:{resolution}")
    if not str(profile.get("source") or "").strip():
        raise ValueError(f"COST_SOURCE_MISSING:{resolution}")
    try:
        observed = datetime.fromisoformat(str(profile.get("observed_at_utc")).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"COST_TIMESTAMP_INVALID:{resolution}") from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError(f"COST_TIMESTAMP_MUST_BE_TIMEZONE_AWARE:{resolution}")
    age = (datetime.now(observed.tzinfo) - observed).total_seconds()
    if age < 0 or age > 86400:
        raise ValueError(f"COST_PROFILE_STALE_OR_FUTURE:{resolution}")
    values["source"] = str(profile["source"])
    values["cost_config_sha256"] = config_sha256
    values["max_slippage_sensitivity_multiplier"] = slippage_multiplier
    values["usd_per_point_per_unit"] = usd_per_point
    values["contract_type"] = str(document["contract_type"])
    values["pnl_model"] = str(document["pnl_model"])
    values["economics_source"] = economic_source
    return values


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
        if not (
            0 <= signal.sweep_index <= signal.reclaim_index
            < signal.confirmation_index < signal.entry_index < len(bars)
        ):
            rejection_ledger.append({"confirmation_index": signal.confirmation_index, "reason": "INVALID_SIGNAL_INDEX_ORDER"})
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
        # The generator's candidate records the next-bar open. A mismatch
        # indicates a stale or misaligned signal ledger and must be rejected.
        if not math.isclose(signal.entry_price, entry_bar.open, rel_tol=0.0, abs_tol=1e-12):
            rejection_ledger.append({"confirmation_index": signal.confirmation_index, "reason": "ENTRY_PRICE_MISMATCH"})
            continue
        raw_entry = entry_bar.open
        entry = _slipped(
            raw_entry, signal.direction, entry=True, bps=config.slippage_bps,
            slippage_points=config.slippage_points, spread_points=config.spread_points,
        )
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
        exit_price = _slipped(
            raw_exit, signal.direction, entry=False, bps=config.slippage_bps,
            slippage_points=config.slippage_points, spread_points=config.spread_points,
        )
        raw_gross_pnl = (
            (raw_exit - raw_entry) * config.quantity * config.usd_per_point_per_unit
            if signal.direction == "long"
            else (raw_entry - raw_exit) * config.quantity * config.usd_per_point_per_unit
        )
        after_price_costs_pnl = (
            (exit_price - entry) * config.quantity * config.usd_per_point_per_unit
            if signal.direction == "long"
            else (entry - exit_price) * config.quantity * config.usd_per_point_per_unit
        )
        execution_cost = raw_gross_pnl - after_price_costs_pnl
        commission = 2.0 * config.commission_per_side * config.quantity
        net_pnl = after_price_costs_pnl - commission
        risk_per_unit = abs(entry - stop)
        risk_cash = risk_per_unit * config.quantity * config.usd_per_point_per_unit
        r_multiple = net_pnl / risk_cash if risk_cash > 0 else 0.0
        equity += net_pnl
        equity_curve.append(equity)
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak if peak > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        entry_time = datetime.fromisoformat(entry_bar.timestamp_utc.replace("Z", "+00:00"))
        exit_time = datetime.fromisoformat(bars[exit_index].timestamp_utc.replace("Z", "+00:00"))
        duration_minutes = max(0, int((exit_time - entry_time).total_seconds() / 60))
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
            "duration_minutes": duration_minutes,
            "price_unit": "index_points",
            "pnl_currency": "USD",
            "usd_per_point_per_unit": config.usd_per_point_per_unit,
            "quantity": config.quantity,
            "gross_pnl": raw_gross_pnl,
            "execution_cost": execution_cost,
            "pnl_after_price_costs": after_price_costs_pnl,
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
    metrics: dict[str, float | int | None] = {
        "total_trades": len(pnls),
        "rejected_signals": len(rejection_ledger),
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
        "expectancy_per_trade": sum(pnls) / len(pnls) if pnls else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else (None if gross_profit > 0 else 0.0),
        "max_drawdown": max_drawdown,
        "drawdown_basis": "REALIZED_EQUITY_AFTER_CLOSED_TRADES_ONLY; excludes intratrade mark-to-market drawdown",
        "avg_trade_duration_minutes": (
            sum(int(trade["duration_minutes"]) for trade in trade_ledger) / len(trade_ledger)
            if trade_ledger else 0.0
        ),
        "net_pnl": sum(pnls),
        "ending_equity": equity,
        "execution_cost_paid": sum(float(t["execution_cost"]) for t in trade_ledger),
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
