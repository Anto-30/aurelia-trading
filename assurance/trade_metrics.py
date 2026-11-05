"""Transparent cost-adjusted research metrics; no execution authority or trade recommendations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import fsum, isfinite
from typing import Iterable, Any


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"INVALID_NUMERIC_{name.upper()}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"INVALID_NUMERIC_{name.upper()}") from exc
    if not isfinite(number):
        raise ValueError(f"NON_FINITE_{name.upper()}")
    return number


@dataclass(frozen=True)
class TradeObservation:
    """One closed research trade; all modeled costs are separately recorded."""

    gross_pnl: float
    spread_costs: float
    commission_costs: float
    payout_costs: float
    slippage_costs: float
    risk_amount: float

    def net_pnl(self) -> float:
        gross = _finite(self.gross_pnl, "gross_pnl")
        costs = (
            _finite(self.spread_costs, "spread_costs"),
            _finite(self.commission_costs, "commission_costs"),
            _finite(self.payout_costs, "payout_costs"),
            _finite(self.slippage_costs, "slippage_costs"),
        )
        risk = _finite(self.risk_amount, "risk_amount")
        if min(costs) < 0:
            raise ValueError("COSTS_MUST_BE_NON_NEGATIVE")
        if risk <= 0:
            raise ValueError("RISK_AMOUNT_MUST_BE_POSITIVE")
        net = gross - fsum(costs)
        if not isfinite(net):
            raise ValueError("NET_PNL_NON_FINITE")
        return net

    def net_r(self) -> float:
        result = self.net_pnl() / _finite(self.risk_amount, "risk_amount")
        if not isfinite(result):
            raise ValueError("NET_R_NON_FINITE")
        return result


@dataclass(frozen=True)
class ResearchMetrics:
    trade_count: int
    net_profit: float
    expectancy_per_trade: float
    profit_factor: float | None
    profit_factor_status: str
    maximum_drawdown_currency: float
    maximum_drawdown_r: float
    average_win_currency: float | None
    average_loss_currency: float | None
    total_spread_costs: float
    total_commission_costs: float
    total_payout_costs: float
    total_slippage_costs: float


def _max_drawdown(values: Iterable[float]) -> float:
    peak = 0.0
    worst = 0.0
    cumulative = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        worst = max(worst, peak - cumulative)
    return worst


def compute_research_metrics(trades: Iterable[TradeObservation]) -> ResearchMetrics:
    """Compute gross profit factor, net expectancy and net equity drawdowns.

    Expectancy is the mean of trade net P&L after spread, commissions, payout
    costs, and slippage. Profit factor is gross profit divided by absolute gross
    loss on gross P&L. If the sample has no gross losses, it is null rather than
    non-standard JSON infinity; net performance and costs are still reported.
    """
    rows = list(trades)
    if not rows:
        raise ValueError("RESEARCH_TRADES_REQUIRED")
    if any(not isinstance(row, TradeObservation) for row in rows):
        raise ValueError("INVALID_TRADE_OBSERVATION")

    net = [row.net_pnl() for row in rows]
    net_r = [row.net_r() for row in rows]
    gross = [_finite(row.gross_pnl, "gross_pnl") for row in rows]
    gross_profit = fsum(value for value in gross if value > 0)
    gross_loss = -fsum(value for value in gross if value < 0)
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
        pf_status = "DEFINED"
    else:
        profit_factor = None
        pf_status = "UNDEFINED_NO_GROSS_LOSSES"
    winning = [value for value in net if value > 0]
    losing = [-value for value in net if value < 0]
    return ResearchMetrics(
        trade_count=len(rows),
        net_profit=fsum(net),
        expectancy_per_trade=fsum(net) / len(rows),
        profit_factor=profit_factor,
        profit_factor_status=pf_status,
        maximum_drawdown_currency=_max_drawdown(net),
        maximum_drawdown_r=_max_drawdown(net_r),
        average_win_currency=fsum(winning) / len(winning) if winning else None,
        average_loss_currency=fsum(losing) / len(losing) if losing else None,
        total_spread_costs=fsum(_finite(row.spread_costs, "spread_costs") for row in rows),
        total_commission_costs=fsum(_finite(row.commission_costs, "commission_costs") for row in rows),
        total_payout_costs=fsum(_finite(row.payout_costs, "payout_costs") for row in rows),
        total_slippage_costs=fsum(_finite(row.slippage_costs, "slippage_costs") for row in rows),
    )


def out_of_sample_degradation(
    in_sample_expectancy: float,
    out_of_sample_expectancy: float,
    *,
    rejection_threshold: float = 0.30,
) -> dict[str, float | str | bool]:
    """Apply (IS expectancy - OOS expectancy) / IS expectancy."""
    ins = _finite(in_sample_expectancy, "in_sample_expectancy")
    oos = _finite(out_of_sample_expectancy, "out_of_sample_expectancy")
    threshold = _finite(rejection_threshold, "rejection_threshold")
    if threshold < 0 or threshold >= 1:
        raise ValueError("OOS_DEGRADATION_THRESHOLD_OUT_OF_RANGE")
    if ins <= 0:
        return {
            "degradation_fraction": None,
            "rejection_threshold": threshold,
            "status": "REJECT_NON_POSITIVE_IN_SAMPLE_EXPECTANCY",
            "rejected": True,
        }
    degradation = (ins - oos) / ins
    return {
        "degradation_fraction": degradation,
        "rejection_threshold": threshold,
        "status": "REJECT_EXCESSIVE_OOS_DEGRADATION" if degradation > threshold else "PASS_DEGRADATION_THRESHOLD",
        "rejected": degradation > threshold,
    }


def report_to_dict(
    metrics: ResearchMetrics, *, is_expectancy: float, oos_expectancy: float
) -> dict[str, Any]:
    """Build JSON-safe metrics; deliberately omits standalone win-rate claims."""
    degradation = out_of_sample_degradation(is_expectancy, oos_expectancy)
    return {
        "schema": "aurelia.research_metrics.v1",
        "metrics": asdict(metrics),
        "out_of_sample": degradation,
        "strategy_accepted_by_metrics_gate": (
            metrics.expectancy_per_trade > 0
            and metrics.profit_factor is not None
            and metrics.profit_factor > 1.0
            and not degradation["rejected"]
        ),
        "execution_authorization_granted": False,
        "evidence_class": "RESEARCH_METRICS_ONLY",
    }
