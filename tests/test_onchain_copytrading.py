from datetime import datetime, timedelta

from research.onchain_copytrading import (
    CopyRiskConfig,
    CopyRiskEngine,
    ExecutionConfig,
    ExecutionSimulator,
    LeadTrade,
    MarketData,
    MarketSnapshot,
    Side,
    TokenSafety,
    TokenSafetyGate,
    average_loser,
    average_winner,
    entry_slippage_bps,
    expectancy,
    maximum_drawdown,
    profit_factor,
    ulcer_index,
    win_rate,
)


def snapshot(price=100.0, liquidity=1_000_000.0, cap=10_000_000.0):
    return MarketSnapshot(
        timestamp=datetime(2026, 1, 1, 0, 0, 5),
        token="TOKEN",
        mid_price=price,
        liquidity_usd=liquidity,
        market_cap_usd=cap,
        volume_1m_usd=100_000.0,
        spread_bps=20.0,
    )


def lead(side=Side.BUY, price=100.0):
    return LeadTrade(
        trade_id="T1",
        trader_wallet="W1",
        token="TOKEN",
        side=side,
        timestamp=datetime(2026, 1, 1),
        price=price,
        notional_usd=1_000.0,
    )


def test_max_chase_aborts_buy():
    simulator = ExecutionSimulator(
        ExecutionConfig(
            base_failed_tx_rate=0.0,
            impact_coefficient=0.0,
            seed=1,
        )
    )
    result = simulator.execute(
        lead=lead(price=100.0),
        market=snapshot(price=105.0),
        notional_usd=100.0,
        max_chase_pct=0.02,
    )
    assert not result.success
    assert result.reason == "MAX_CHASE_ABORT"


def test_execution_is_not_close_fill():
    simulator = ExecutionSimulator(
        ExecutionConfig(
            base_failed_tx_rate=0.0,
            impact_coefficient=0.20,
            seed=1,
        )
    )
    result = simulator.execute(
        lead=lead(price=100.0),
        market=snapshot(price=100.0),
        notional_usd=5_000.0,
        max_chase_pct=0.20,
    )
    assert result.success
    assert result.fill_price is not None
    assert result.fill_price > result.reference_price
    assert result.slippage_usd > 0


def test_token_safety_rejects_honeypot():
    gate = TokenSafetyGate(CopyRiskConfig())
    allowed, reason = gate.check(TokenSafety(honeypot=True, liquidity_usd=100_000))
    assert not allowed
    assert reason == "HONEYPOT"


def test_risk_halts_after_daily_drawdown():
    risk = CopyRiskEngine(CopyRiskConfig(daily_drawdown_limit_pct=3.0))
    allowed, reasons, _ = risk.pre_trade(
        equity_usd=1_000.0,
        daily_drawdown_pct=3.0,
        weekly_drawdown_pct=0.0,
        safety=TokenSafety(liquidity_usd=100_000),
    )
    assert not allowed
    assert "DAILY_DRAWDOWN_HALT" in reasons


def test_metrics_are_copier_metrics():
    pnls = [10.0, -5.0, 20.0, -15.0]
    assert expectancy(pnls) == 2.5
    assert profit_factor(pnls) == 2.0
    assert win_rate(pnls) == 0.5
    assert average_winner(pnls) == 15.0
    assert average_loser(pnls) == -10.0


def test_drawdown_and_ulcer_index():
    curve = [100.0, 110.0, 99.0, 105.0]
    assert maximum_drawdown(curve) == 0.10
    assert ulcer_index(curve) > 0


def test_entry_slippage_direction():
    assert entry_slippage_bps(100.0, 101.0, Side.BUY) == 100.0
    assert entry_slippage_bps(100.0, 99.0, Side.SELL) == 101.0101010101011


def test_market_data_is_timestamp_aware():
    rows = [
        snapshot(),
        MarketSnapshot(
            timestamp=datetime(2026, 1, 1, 0, 0, 10),
            token="TOKEN",
            mid_price=110.0,
            liquidity_usd=1_000_000.0,
            market_cap_usd=10_000_000.0,
            volume_1m_usd=100_000.0,
            spread_bps=20.0,
        ),
    ]
    market = MarketData(rows)
    found = market.at_or_after(
        "TOKEN",
        datetime(2026, 1, 1, 0, 0, 7),
    )
    assert found is not None
    assert found.mid_price == 110.0
