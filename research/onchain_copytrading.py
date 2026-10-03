"""AURELIA on-chain copy-trading research engine.

Research/shadow only. This module has NO capital authority and MUST NOT
call a live broker/wallet. It models lead-wallet events, copier latency,
DEX-style executable-price degradation, max-chase guards, failures,
fees, token safety and deterministic Layer-6-style risk gates.

All numeric thresholds are research defaults and require calibration against
observed on-chain/quote/receipt data before any deployment decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from math import sqrt
from random import Random
from statistics import mean
from typing import Iterable, Optional, Sequence


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class LeadTrade:
    trade_id: str
    trader_wallet: str
    token: str
    side: Side
    timestamp: datetime
    price: float
    notional_usd: float


@dataclass(frozen=True)
class MarketSnapshot:
    timestamp: datetime
    token: str
    mid_price: float
    liquidity_usd: float
    market_cap_usd: float
    volume_1m_usd: float
    spread_bps: float
    failed_tx_probability: float = 0.0


@dataclass(frozen=True)
class TokenSafety:
    honeypot: bool = False
    buy_tax_pct: float = 0.0
    sell_tax_pct: float = 0.0
    liquidity_usd: float = 0.0
    trading_paused: bool = False
    blacklist_capability: bool = False
    mint_authority_present: bool = False


@dataclass(frozen=True)
class CopyRiskConfig:
    daily_drawdown_limit_pct: float = 3.0
    weekly_drawdown_limit_pct: float = 6.0
    base_position_pct: float = 1.0
    hard_position_cap_pct: float = 2.0
    max_global_exposure_pct: float = 10.0
    max_token_exposure_pct: float = 2.0
    max_trader_exposure_pct: float = 5.0
    minimum_liquidity_usd: float = 50_000.0
    max_buy_tax_pct: float = 5.0
    max_sell_tax_pct: float = 5.0
    max_chase_pct: float = 2.0
    max_hold_minutes: float = 10.0
    max_consecutive_failures: int = 3


@dataclass(frozen=True)
class ExecutionConfig:
    latency_min_s: float = 1.0
    latency_max_s: float = 5.0
    fee_bps: float = 50.0
    base_failed_tx_rate: float = 0.01
    impact_coefficient: float = 0.15
    max_market_impact_pct: float = 0.03
    seed: int = 42


@dataclass(frozen=True)
class Fill:
    success: bool
    side: Side
    requested_at: datetime
    filled_at: Optional[datetime]
    reference_price: float
    fill_price: Optional[float]
    quantity: float
    notional_usd: float
    fee_usd: float
    slippage_usd: float
    reason: str


@dataclass
class CopyTradeResult:
    lead_trade_id: str
    token: str
    trader_wallet: str
    lead_entry_at: datetime
    lead_exit_at: Optional[datetime] = None
    entry: Optional[Fill] = None
    exit: Optional[Fill] = None
    planned_risk_usd: float = 0.0
    net_pnl_usd: Optional[float] = None

    @property
    def r_multiple(self) -> Optional[float]:
        if self.net_pnl_usd is None or self.planned_risk_usd <= 0:
            return None
        return self.net_pnl_usd / self.planned_risk_usd


class MarketData:
    def __init__(self, snapshots: Iterable[MarketSnapshot]):
        self._rows = {}
        for row in snapshots:
            self._rows.setdefault(row.token, []).append(row)
        for rows in self._rows.values():
            rows.sort(key=lambda x: x.timestamp)

    def at_or_after(self, token: str, timestamp: datetime) -> Optional[MarketSnapshot]:
        for row in self._rows.get(token, ()):
            if row.timestamp >= timestamp:
                return row
        return None


class TokenSafetyGate:
    def __init__(self, config: CopyRiskConfig):
        self.config = config

    def check(self, token: TokenSafety) -> tuple[bool, str]:
        checks = (
            (token.honeypot, "HONEYPOT"),
            (token.buy_tax_pct > self.config.max_buy_tax_pct, "BUY_TAX_TOO_HIGH"),
            (token.sell_tax_pct > self.config.max_sell_tax_pct, "SELL_TAX_TOO_HIGH"),
            (token.liquidity_usd < self.config.minimum_liquidity_usd, "LIQUIDITY_TOO_LOW"),
            (token.trading_paused, "TRADING_PAUSED"),
            (token.blacklist_capability, "BLACKLIST_CAPABILITY"),
            (token.mint_authority_present, "MINT_AUTHORITY_PRESENT"),
        )
        for failed, reason in checks:
            if failed:
                return False, reason
        return True, "PASS"


class ExecutionSimulator:
    """Research execution model; it never submits a transaction."""

    def __init__(self, config: ExecutionConfig):
        self.config = config
        self.rng = Random(config.seed)

    def latency(self) -> float:
        return self.rng.uniform(
            self.config.latency_min_s,
            self.config.latency_max_s,
        )

    def impact_pct(self, notional_usd: float, market: MarketSnapshot) -> float:
        if market.liquidity_usd <= 0:
            return float("inf")
        participation = notional_usd / market.liquidity_usd
        base = self.config.impact_coefficient * sqrt(max(participation, 0.0))
        cap_factor = min(
            3.0,
            max(1.0, sqrt(1_000_000.0 / max(market.market_cap_usd, 1.0))),
        )
        return base * cap_factor

    def execute(
        self,
        lead: LeadTrade,
        market: MarketSnapshot,
        notional_usd: float,
        max_chase_pct: float,
    ) -> Fill:
        if market.liquidity_usd <= 0:
            return self._reject(lead, market, "LIQUIDITY_INVALID")

        if self.rng.random() < min(
            1.0,
            self.config.base_failed_tx_rate + market.failed_tx_probability,
        ):
            return self._reject(lead, market, "TRANSACTION_FAILED")

        impact = self.impact_pct(notional_usd, market)
        if impact > self.config.max_market_impact_pct:
            return self._reject(lead, market, "MARKET_IMPACT_TOO_HIGH")

        spread = market.spread_bps / 10_000.0
        if lead.side is Side.BUY:
            fill_price = market.mid_price * (1.0 + spread / 2.0 + impact)
            if fill_price > lead.price * (1.0 + max_chase_pct):
                return self._reject(lead, market, "MAX_CHASE_ABORT")
        else:
            fill_price = market.mid_price * (1.0 - spread / 2.0 - impact)
            if fill_price < lead.price * (1.0 - max_chase_pct):
                return self._reject(lead, market, "MAX_CHASE_ABORT")

        quantity = notional_usd / max(fill_price, 1e-18)
        fee = notional_usd * self.config.fee_bps / 10_000.0
        slippage = abs(fill_price - market.mid_price) * quantity

        return Fill(
            True, lead.side, market.timestamp, market.timestamp,
            market.mid_price, fill_price, quantity, notional_usd,
            fee, slippage, "FILLED",
        )

    @staticmethod
    def _reject(lead: LeadTrade, market: MarketSnapshot, reason: str) -> Fill:
        return Fill(
            False, lead.side, market.timestamp, None, market.mid_price,
            None, 0.0, 0.0, 0.0, 0.0, reason,
        )


class CopyRiskEngine:
    """Deterministic Layer-6-style research gate. No capital authority."""

    def __init__(self, config: CopyRiskConfig):
        self.config = config
        self.consecutive_failures = 0

    def position_size(
        self,
        equity_usd: float,
        current_global_exposure_usd: float = 0.0,
        token_exposure_usd: float = 0.0,
        trader_exposure_usd: float = 0.0,
    ) -> tuple[float, str]:
        base = equity_usd * self.config.base_position_pct / 100.0
        hard = equity_usd * self.config.hard_position_cap_pct / 100.0
        global_room = max(
            0.0,
            equity_usd * self.config.max_global_exposure_pct / 100.0
            - current_global_exposure_usd,
        )
        token_room = max(
            0.0,
            equity_usd * self.config.max_token_exposure_pct / 100.0
            - token_exposure_usd,
        )
        trader_room = max(
            0.0,
            equity_usd * self.config.max_trader_exposure_pct / 100.0
            - trader_exposure_usd,
        )
        size = min(base, hard, global_room, token_room, trader_room)
        return size, "PASS" if size > 0 else "EXPOSURE_LIMIT"

    def pre_trade(
        self,
        *,
        equity_usd: float,
        daily_drawdown_pct: float,
        weekly_drawdown_pct: float,
        safety: TokenSafety,
        current_global_exposure_usd: float = 0.0,
        token_exposure_usd: float = 0.0,
        trader_exposure_usd: float = 0.0,
    ) -> tuple[bool, tuple[str, ...], float]:
        reasons = []
        if daily_drawdown_pct >= self.config.daily_drawdown_limit_pct:
            reasons.append("DAILY_DRAWDOWN_HALT")
        if weekly_drawdown_pct >= self.config.weekly_drawdown_limit_pct:
            reasons.append("WEEKLY_DRAWDOWN_HALT")
        if self.consecutive_failures >= self.config.max_consecutive_failures:
            reasons.append("CONSECUTIVE_FAILURE_HALT")

        safety_ok, safety_reason = TokenSafetyGate(self.config).check(safety)
        if not safety_ok:
            reasons.append(safety_reason)

        size, size_reason = self.position_size(
            equity_usd,
            current_global_exposure_usd,
            token_exposure_usd,
            trader_exposure_usd,
        )
        if size_reason != "PASS":
            reasons.append(size_reason)

        return not reasons, tuple(reasons), size

    def record_execution(self, success: bool) -> None:
        self.consecutive_failures = 0 if success else self.consecutive_failures + 1


def expectancy(pnls: Sequence[float]) -> float:
    return mean(pnls) if pnls else 0.0


def profit_factor(pnls: Sequence[float]) -> float:
    gross_profit = sum(x for x in pnls if x > 0)
    gross_loss = -sum(x for x in pnls if x < 0)
    if gross_loss == 0:
        return float("inf") if gross_profit else 0.0
    return gross_profit / gross_loss


def win_rate(pnls: Sequence[float]) -> float:
    return sum(x > 0 for x in pnls) / len(pnls) if pnls else 0.0


def average_winner(pnls: Sequence[float]) -> float:
    values = [x for x in pnls if x > 0]
    return mean(values) if values else 0.0


def average_loser(pnls: Sequence[float]) -> float:
    values = [x for x in pnls if x < 0]
    return mean(values) if values else 0.0


def maximum_drawdown(equity_curve: Sequence[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    maximum = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            maximum = max(maximum, 1.0 - equity / peak)
    return maximum


def ulcer_index(equity_curve: Sequence[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    squared = []
    for equity in equity_curve:
        peak = max(peak, equity)
        drawdown_pct = 100.0 * (equity / peak - 1.0)
        squared.append(drawdown_pct ** 2)
    return sqrt(mean(squared))


def total_slippage_usd(results: Sequence[CopyTradeResult]) -> float:
    total = 0.0
    for result in results:
        if result.entry and result.entry.success:
            total += result.entry.slippage_usd
        if result.exit and result.exit.success:
            total += result.exit.slippage_usd
    return total


def metric_report(
    results: Sequence[CopyTradeResult],
    equity_curve: Sequence[float],
) -> dict:
    pnls = [r.net_pnl_usd for r in results if r.net_pnl_usd is not None]
    return {
        "trades": len(pnls),
        "expectancy_usd": expectancy(pnls),
        "profit_factor": profit_factor(pnls),
        "win_rate": win_rate(pnls),
        "average_winner_usd": average_winner(pnls),
        "average_loser_usd": average_loser(pnls),
        "maximum_drawdown": maximum_drawdown(equity_curve),
        "ulcer_index": ulcer_index(equity_curve),
        "r_multiples": [r.r_multiple for r in results if r.r_multiple is not None],
        "total_slippage_usd": total_slippage_usd(results),
        "ending_equity": equity_curve[-1] if equity_curve else None,
    }


def entry_delay_seconds(lead: LeadTrade, detected_at: datetime) -> float:
    return max(0.0, (detected_at - lead.timestamp).total_seconds())


def entry_slippage_bps(lead_price: float, copy_price: float, side: Side) -> float:
    if lead_price <= 0 or copy_price <= 0:
        raise ValueError("prices must be positive")
    if side is Side.BUY:
        return 10_000.0 * (copy_price / lead_price - 1.0)
    return 10_000.0 * (lead_price / copy_price - 1.0)


def slippage_adjusted_return(
    starting_capital: float,
    ending_capital: float,
    slippage_usd: float,
) -> float:
    if starting_capital <= 0:
        raise ValueError("starting_capital must be positive")
    return ((ending_capital + slippage_usd) / starting_capital) - 1.0
