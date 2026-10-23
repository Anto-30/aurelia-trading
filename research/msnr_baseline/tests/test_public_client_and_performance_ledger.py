from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from performance_ledger import EmpiricalValidationEngine, LedgerError
from deriv_public_market_data import (
    DerivPublicMarketDataClient,
    PublicMarketDataError,
    validate_candle_response,
    validate_history_response,
    validate_public_payload,
)


def raw_trades():
    return pd.DataFrame({
        "entry_time": ["2024-01-02T00:00:00Z", "2024-01-01T00:00:00Z", "2024-01-03T00:00:00Z"],
        "exit_time": ["2024-01-02T01:00:00Z", "2024-01-01T01:00:00Z", "2024-01-03T01:00:00Z"],
        "entry_price": [100.0, 100.0, 100.0], "exit_price": [101.0, 99.0, 100.5],
        "direction": [1, 1, -1], "size": [2.0, 2.0, 1.0], "initial_risk": [2.0, 2.0, 1.0],
    })


def engine(multiplier=1.0):
    return EmpiricalValidationEngine(commission_per_unit_round_trip=0.01, spread_pips_round_trip=2.0,
        pip_size_price=0.1, slippage_bps_per_fill=5.0, linear_multiplier=multiplier, initial_equity=1000.0)


def test_perf_ledger_post_cost_metrics_and_exit_order():
    ledger, metrics = engine().generate_performance_ledger(raw_trades())
    assert len(ledger) == 3
    assert list(ledger["exit_time"]) == sorted(ledger["exit_time"])
    assert (ledger["transaction_cost"] > 0).all()
    assert np.allclose(ledger["net_pnl"], ledger["gross_pnl"] - ledger["transaction_cost"])
    assert metrics["expectancy_r"] == pytest.approx(ledger["r_multiple"].mean())
    assert metrics["total_transaction_costs"] == pytest.approx(ledger["transaction_cost"].sum())
    assert metrics["final_equity"] == pytest.approx(1000.0 + ledger["net_pnl"].sum())
    assert metrics["max_drawdown_abs"] >= 0
    assert metrics["cost_assumptions"]["qualification_status"].startswith("NOT_QUALIFIED")


def test_perf_ledger_costs_include_commission_spread_and_both_slippage_fills():
    df = raw_trades().iloc[[0]].copy()
    result = engine().apply_linear_cost_model(df).iloc[0]
    commission = .01 * 2.0
    spread = 2.0 * .1 * 2.0
    slippage = (100.0 + 101.0) * 5.0 / 10000 * 2.0
    assert result["transaction_cost"] == pytest.approx(commission + spread + slippage)
    triple = engine(multiplier=3).apply_linear_cost_model(df).iloc[0]
    assert triple["gross_pnl"] == pytest.approx(result["gross_pnl"] * 3)
    assert triple["spread_cost"] == pytest.approx(result["spread_cost"] * 3)


def test_perf_ledger_rejects_double_charge_bad_direction_bad_risk_and_missing_columns():
    with pytest.raises(LedgerError, match="already be costed"):
        engine().apply_linear_cost_model(raw_trades().assign(net_pnl=100))
    with pytest.raises(LedgerError, match="direction"):
        engine().apply_linear_cost_model(raw_trades().assign(direction=0))
    with pytest.raises(LedgerError, match="positive"):
        engine().apply_linear_cost_model(raw_trades().assign(initial_risk=0))
    with pytest.raises(LedgerError, match="Missing required"):
        engine().apply_linear_cost_model(raw_trades().drop(columns=["size"]))


def test_perf_ledger_rejects_missing_timestamps_and_all_derived_columns():
    missing_time = raw_trades().copy()
    missing_time.loc[0, "entry_time"] = ""
    with pytest.raises(LedgerError, match="cannot be missing or unparseable"):
        engine().apply_linear_cost_model(missing_time)

    # Every output-derived field, including equity/drawdown columns, must be
    # rejected to prevent an already-costed ledger from being charged twice.
    with pytest.raises(LedgerError, match="already be costed"):
        engine().apply_linear_cost_model(raw_trades().assign(drawdown_abs=0.0))


def test_perf_factor_uses_post_cost_wins_and_losses():
    ledger, metrics = engine().generate_performance_ledger(raw_trades())
    wins = ledger.loc[ledger["net_pnl"] > 0, "net_pnl"].sum()
    losses = abs(ledger.loc[ledger["net_pnl"] < 0, "net_pnl"].sum())
    assert metrics["profit_factor_net"] == pytest.approx(wins / losses)
    assert metrics["expectancy_r"] == pytest.approx(ledger["r_multiple"].mean())
    assert metrics["max_drawdown_abs"] == pytest.approx(ledger["drawdown_abs"].max())


def test_new_public_request_schema_and_forbidden_keys():
    validate_public_payload({"active_symbols": "brief"})
    validate_public_payload({"ticks": "R_100", "subscribe": 1})
    validate_public_payload({"ticks_history": "R_100", "start": 100, "end": "200", "style": "candles", "granularity": 60, "count": 5000})
    # Current schema supports an explicit enum of candle intervals, not arbitrary positive integers.
    validate_public_payload({"ticks_history": "R_100", "start": 100, "end": "200", "style": "candles", "granularity": 120, "subscribe": 0, "adjust_start_time": 1})
    validate_public_payload({"ticks_history": "R_100", "start": 100, "end": "200", "style": "candles", "granularity": 900, "subscribe": 1})
    for granularity in (1, 59, 61, 899, 901, 86401, True, 1.0):
        with pytest.raises(PublicMarketDataError, match="granularity must be one of"):
            validate_public_payload({"ticks_history": "R_100", "start": 100, "end": "200", "style": "candles", "granularity": granularity})
    bad = [
        {"buy": "proposal-id", "price": 1}, {"sell": 1, "price": 0}, {"proposal": 1},
        {"balance": 1}, {"otp": "secret"}, {"Authorization": "Bearer x"}, {"loginid": "CR123"},
        {"ticks": "R_100", "passthrough": {"loginid": "CR123"}},
        {"ticks_history": "R_100", "start": 100, "end": "200", "style": "candles", "granularity": 60, "subscribe": 2},
        {"ticks_history": "R_100", "start": 100, "end": "200", "style": "candles", "granularity": 60, "adjust_start_time": 2},
        {"ticks_history": "R_100", "start": 100, "end": "200", "style": "candles", "granularity": 0},
        {"ticks": "R_100", "extra": "unknown"},
    ]
    for payload in bad:
        with pytest.raises(PublicMarketDataError):
            validate_public_payload(payload)


def test_client_is_pinned_to_public_endpoint_and_current_history_schema():
    client = DerivPublicMarketDataClient()
    assert client.endpoint == "wss://api.derivws.com/trading/v1/options/ws/public"
    with pytest.raises(PublicMarketDataError):
        DerivPublicMarketDataClient(endpoint="wss://api.derivws.com/trading/v1/options/ws/real?otp=x")
    rows = validate_candle_response({"msg_type":"candles","candles":[{"open":100,"high":102,"low":99,"close":101,"epoch":100}]})
    assert rows[0]["epoch"] == 100
    with pytest.raises(PublicMarketDataError, match="missing a required"):
        validate_candle_response({"msg_type":"candles","candles":[{"open":100,"high":102,"low":99,"epoch":100}]})
    prices, times = validate_history_response({"msg_type":"history","history":{"prices":[1.0,1.1],"times":[100,101]}})
    assert prices == [1.0,1.1] and times == [100,101]
    with pytest.raises(PublicMarketDataError, match="both prices and times"):
        validate_history_response({"msg_type":"history","history":{"prices":[1.0]}})


def test_history_builder_keeps_ticks_history_request_key():
    client = DerivPublicMarketDataClient()
    with pytest.raises(PublicMarketDataError, match="Candle granularity must be one of"):
        asyncio.run(client.ticks_history(underlying_symbol="R_100", start_epoch=100, end_epoch=160, granularity_seconds=61))
    seen = {}
    async def fake_request(payload, expected_msg_type=None):
        seen["payload"] = payload
        seen["expected"] = expected_msg_type
        return {"msg_type":"candles","candles":[{"open":1,"high":1.1,"low":.9,"close":1,"epoch":100}]}
    client.request = fake_request
    asyncio.run(client.ticks_history(underlying_symbol="R_100",start_epoch=100,end_epoch=160,granularity_seconds=60))
    assert seen["payload"]["ticks_history"] == "R_100"
    assert "subscribe" not in seen["payload"]  # one-shot history request: omit optional flag
    assert "symbol" not in seen["payload"] and "underlying_symbol" not in seen["payload"] and "loginid" not in seen["payload"]
    assert seen["expected"] == "candles"
