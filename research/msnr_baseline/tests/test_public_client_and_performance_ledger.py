from __future__ import annotations

import asyncio
import json
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
    validate_tick_response,
)
from fetch_history import (
    FetchError,
    build_candle_payload,
    normalize_candles,
    validate_fetch_controls,
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


def test_history_fetcher_normalizes_only_strict_json_candle_types_and_exact_coverage():
    rows = [
        {"epoch": 60, "open": 100, "high": 101, "low": 99, "close": 100.5},
        {"epoch": 120, "open": 100.5, "high": 102, "low": 100, "close": 101.5},
    ]
    normalized = normalize_candles(rows, 60, 180, 60)
    assert normalized == [
        {"epoch": 60, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5},
        {"epoch": 120, "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.5},
    ]

    invalid_candles = (
        {**rows[0], "epoch": True},
        {**rows[0], "epoch": "60"},
        {**rows[0], "epoch": 60.0},
        {**rows[0], "epoch": -1},
        {**rows[0], "epoch": 10000000000},
        {**rows[0], "open": "100"},
        {**rows[0], "open": True},
        {**rows[0], "close": False},
        {**rows[0], "high": float("nan")},
        {**rows[0], "low": float("inf")},
    )
    for candle in invalid_candles:
        with pytest.raises(FetchError):
            normalize_candles([candle], 60, 120, 60)

    for bad_args in (
        (True, 0, 0),
        (0, 0, 0),
        (-1, 0, 0),
        (float("nan"), 0, 0),
        (float("inf"), 0, 0),
        ("1", 0, 0),
        (1, True, 0),
        (1, -1, 0),
        (1, 11, 0),
        (1, 1.0, 0),
        (1, 0, True),
        (1, 0, -1),
        (1, 0, float("nan")),
        (1, 0, float("inf")),
        (1, 0, "1"),
    ):
        with pytest.raises(FetchError):
            validate_fetch_controls(*bad_args)

    assert validate_fetch_controls(1, 2, 0) == (1.0, 2, 0.0)


def test_history_fetcher_builds_bounded_valid_current_api_candle_request():
    payload = build_candle_payload(60, 180, 60)
    assert payload == {
        "ticks_history": "R_100",
        "start": 60,
        "end": "120",
        "style": "candles",
        "granularity": 60,
        "req_id": 1,
    }

    for args in (
        (True, 180, 60),
        (60, 180.0, 60),
        (180, 120, 60),
        (60, 180, True),
        (60, 180, 61),
        (60, 10000000000, 60),
        (60, 60 + 5001 * 60, 60),
    ):
        with pytest.raises(FetchError):
            build_candle_payload(*args)


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
    validate_public_payload({"ticks": ["R_100", "frxEURUSD"], "subscribe": 1})
    for invalid_tick_request in (
        {"ticks": "R_100", "subscribe": True},
        {"ticks": "R_100", "subscribe": 1.0},
        {"ticks": "R-100"},
        {"ticks": "A" * 31},
        {"ticks": ["R_100", "R-100"]},
    ):
        with pytest.raises(PublicMarketDataError):
            validate_public_payload(invalid_tick_request)
    with pytest.raises(PublicMarketDataError, match="array of non-empty strings"):
        validate_public_payload({"active_symbols": "full", "contract_type": [None]})
    validate_public_payload({"ticks_history": "R_100", "start": 100, "end": "200", "style": "candles", "granularity": 60, "count": 5000})
    validate_public_payload({"ticks_history": "frxEURUSD", "end": "latest", "style": "ticks"})
    with pytest.raises(PublicMarketDataError, match="end is required"):
        validate_public_payload({"ticks_history": "R_100", "style": "ticks"})
    for symbol in ("R", "R-100", "A" * 31, "éR100", "R_100\n"):
        with pytest.raises(PublicMarketDataError, match="2-30 character ASCII word"):
            validate_public_payload({"ticks_history": symbol, "end": "latest", "style": "ticks"})
    # Current schema supports an explicit enum of candle intervals, not arbitrary positive integers.
    validate_public_payload({"ticks_history": "R_100", "start": 100, "end": "200", "style": "candles", "granularity": 120, "subscribe": 1, "adjust_start_time": 1})
    validate_public_payload({"ticks_history": "R_100", "start": 100, "end": "200", "style": "candles", "granularity": 900, "subscribe": 1})
    for granularity in (1, 59, 61, 899, 901, 86401, True, 1.0):
        with pytest.raises(PublicMarketDataError, match="granularity must be one of"):
            validate_public_payload({"ticks_history": "R_100", "start": 100, "end": "200", "style": "candles", "granularity": granularity})
    with pytest.raises(PublicMarketDataError, match="only applicable"):
        validate_public_payload({"ticks_history": "R_100", "start": 100, "end": "200", "style": "ticks", "granularity": 60})
    for key in ("subscribe", "adjust_start_time"):
        for invalid_value in (0, True, False, 1.0, "1"):
            with pytest.raises(PublicMarketDataError, match=f"{key} must be integer 1"):
                validate_public_payload({"ticks_history": "R_100", "start": 100, "end": "200", "style": "ticks", key: invalid_value})
    schema_invalid = [
        {"ticks_history": "R_100", "start": True, "end": "200", "style": "ticks"},
        {"ticks_history": "R_100", "start": 10000000000, "end": "200", "style": "ticks"},
        {"ticks_history": "R_100", "start": 100, "end": 200, "style": "ticks"},
        {"ticks_history": "R_100", "start": 100, "end": "12345678901", "style": "ticks"},
        {"ticks_history": "R_100", "start": 201, "end": "200", "style": "ticks"},
        {"ticks_history": "R_100", "start": 100, "end": "200", "style": "ticks", "count": True},
    ]
    for payload in schema_invalid:
        with pytest.raises(PublicMarketDataError):
            validate_public_payload(payload)
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


def test_market_data_response_validators_reject_coerced_json_types():
    valid_candle = {"open": 100, "high": 102, "low": 99, "close": 101, "epoch": 100}
    for field, invalid_value in (
        ("open", "100"),
        ("high", True),
        ("low", False),
        ("close", "101.0"),
        ("epoch", "100"),
        ("epoch", True),
        ("epoch", 100.0),
        ("epoch", -1),
        ("epoch", 10000000000),
    ):
        candle = {**valid_candle, field: invalid_value}
        with pytest.raises(PublicMarketDataError):
            validate_candle_response({"msg_type": "candles", "candles": [candle]})

    invalid_histories = (
        {"prices": ["1.1"], "times": [100]},
        {"prices": [True], "times": [100]},
        {"prices": [1.1], "times": ["100"]},
        {"prices": [1.1], "times": [True]},
        {"prices": [1.1], "times": [100.0]},
        {"prices": [1.1], "times": [-1]},
        {"prices": [1.1], "times": [10000000000]},
    )
    for history in invalid_histories:
        with pytest.raises(PublicMarketDataError):
            validate_history_response({"msg_type": "history", "history": history})

    with pytest.raises(PublicMarketDataError, match="Expected candles response"):
        validate_candle_response(None)
    with pytest.raises(PublicMarketDataError, match="Expected history response"):
        validate_history_response(None)


def test_history_response_validator_rejects_empty_history_responses():
    with pytest.raises(PublicMarketDataError, match="at least one"):
        validate_history_response({"msg_type": "history", "history": {"prices": [], "times": []}})


def test_history_builder_keeps_ticks_history_request_key():
    client = DerivPublicMarketDataClient()
    with pytest.raises(PublicMarketDataError, match="Candle granularity must be one of"):
        asyncio.run(client.ticks_history(underlying_symbol="R_100", start_epoch=100, end_epoch=160, granularity_seconds=61))
    with pytest.raises(PublicMarketDataError, match="integer epochs"):
        asyncio.run(client.ticks_history(underlying_symbol="R_100", start_epoch=True, end_epoch=160, granularity_seconds=60))
    with pytest.raises(PublicMarketDataError, match="count must be an integer"):
        asyncio.run(client.ticks_history(underlying_symbol="R_100", start_epoch=100, end_epoch=160, granularity_seconds=60, count=1.5))
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


def test_tick_response_validator_rejects_coercion_bad_epochs_and_wrong_symbols():
    valid = {"msg_type": "tick", "tick": {"quote": 101.25, "epoch": 1700000000, "symbol": "R_100", "pip_size": 2}}
    clean = validate_tick_response(valid, requested_symbol="R_100")
    assert clean == {"quote": 101.25, "epoch": 1700000000}

    invalid_ticks = (
        {"quote": "101.25", "epoch": 1700000000},
        {"quote": True, "epoch": 1700000000},
        {"quote": float("nan"), "epoch": 1700000000},
        {"quote": float("inf"), "epoch": 1700000000},
        {"quote": -1, "epoch": 1700000000},
        {"quote": 101.25, "epoch": "1700000000"},
        {"quote": 101.25, "epoch": True},
        {"quote": 101.25, "epoch": 1700000000.0},
        {"quote": 101.25, "epoch": -1},
        {"quote": 101.25, "epoch": 10000000000},
        {"quote": 101.25, "epoch": 1700000000, "symbol": "frxEURUSD"},
        {"quote": 101.25, "epoch": 1700000000, "symbol": "R-100"},
        {"quote": 101.25, "epoch": 1700000000, "symbol": None},
    )
    for tick in invalid_ticks:
        with pytest.raises(PublicMarketDataError):
            validate_tick_response({"msg_type": "tick", "tick": tick}, requested_symbol="R_100")

    with pytest.raises(PublicMarketDataError, match="Expected tick response"):
        validate_tick_response(None, requested_symbol="R_100")
    with pytest.raises(PublicMarketDataError, match="Requested tick symbol"):
        validate_tick_response(valid, requested_symbol="R-100")


def test_stream_ticks_rejects_invalid_symbol_and_reconnect_parameters_before_connect(monkeypatch):
    client = DerivPublicMarketDataClient()
    def should_not_connect(*args, **kwargs):
        raise AssertionError("invalid inputs must be rejected before WebSocket connection")
    monkeypatch.setattr("deriv_public_market_data.websockets.connect", should_not_connect)

    async def consume(symbol, max_reconnects=5, initial_backoff_seconds=1.0):
        async for _ in client.stream_ticks(
            underlying_symbol=symbol,
            max_reconnects=max_reconnects,
            initial_backoff_seconds=initial_backoff_seconds,
        ):
            return

    for symbol in ("R-100", "A" * 31, "éR100", ""):
        with pytest.raises(PublicMarketDataError, match="Stream symbol"):
            asyncio.run(consume(symbol))
    for reconnects in (True, -1, 101, 1.0):
        with pytest.raises(PublicMarketDataError, match="Reconnect count"):
            asyncio.run(consume("R_100", max_reconnects=reconnects))
    for backoff in (True, 0, -1, float("nan"), float("inf"), "1", 10 ** 1000):
        with pytest.raises(PublicMarketDataError, match="Reconnect backoff"):
            asyncio.run(consume("R_100", initial_backoff_seconds=backoff))


def test_client_timeouts_must_be_finite_positive_numeric_seconds():
    for bad in (True, False, 0, -1, float("nan"), float("inf"), float("-inf"), "1", 10 ** 1000):
        with pytest.raises(PublicMarketDataError, match="finite positive number"):
            DerivPublicMarketDataClient(connect_timeout=bad)
        with pytest.raises(PublicMarketDataError, match="finite positive number"):
            DerivPublicMarketDataClient(response_timeout=bad)
    client = DerivPublicMarketDataClient(connect_timeout=0.25, response_timeout=1)
    assert client.connect_timeout == 0.25
    assert client.response_timeout == 1.0


def test_stream_ticks_uses_public_request_and_yields_only_validated_tick(monkeypatch):
    received = {}

    class FakeSocket:
        def __init__(self, messages):
            self.messages = list(messages)
        async def send(self, payload):
            received["request"] = json.loads(payload)
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not self.messages:
                raise StopAsyncIteration
            return json.dumps(self.messages.pop(0))

    class FakeConnection:
        def __init__(self, socket):
            self.socket = socket
        async def __aenter__(self):
            return self.socket
        async def __aexit__(self, exc_type, exc, tb):
            return False

    message = {"msg_type": "tick", "tick": {"quote": 123.45, "epoch": 1700000000, "symbol": "R_100", "pip_size": 2}}
    monkeypatch.setattr(
        "deriv_public_market_data.websockets.connect",
        lambda *args, **kwargs: FakeConnection(FakeSocket([message])),
    )
    client = DerivPublicMarketDataClient()

    async def take_first_tick():
        stream = client.stream_ticks(underlying_symbol="R_100", max_reconnects=0)
        try:
            return await anext(stream)
        finally:
            await stream.aclose()

    result = asyncio.run(take_first_tick())
    assert received["request"]["ticks"] == "R_100"
    assert received["request"]["subscribe"] == 1
    assert received["request"]["req_id"] == 1001
    assert result["msg_type"] == "tick"
    assert result["underlying_symbol_requested"] == "R_100"
    assert result["epoch"] == 1700000000
    assert result["quote"] == 123.45


def test_stream_ticks_rejects_coercible_quote_in_mocked_websocket(monkeypatch):
    class FakeSocket:
        def __init__(self):
            self.messages = [json.dumps({"msg_type": "tick", "tick": {"quote": "123.45", "epoch": 1700000000, "symbol": "R_100"}})]
        async def send(self, payload):
            return None
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not self.messages:
                raise StopAsyncIteration
            return self.messages.pop(0)

    class FakeConnection:
        async def __aenter__(self):
            self.socket = FakeSocket()
            return self.socket
        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "deriv_public_market_data.websockets.connect",
        lambda *args, **kwargs: FakeConnection(),
    )
    client = DerivPublicMarketDataClient()

    async def take_first_tick():
        stream = client.stream_ticks(underlying_symbol="R_100", max_reconnects=0)
        return await anext(stream)

    with pytest.raises(PublicMarketDataError, match="max reconnect count"):
        asyncio.run(take_first_tick())


def test_malformed_api_error_payloads_fail_with_controlled_public_data_errors(monkeypatch):
    class FakeSocket:
        async def send(self, payload):
            return None
        async def recv(self):
            return '{"req_id": 1001, "error": "not-an-object"}'

    class FakeConnection:
        async def __aenter__(self):
            return FakeSocket()
        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "deriv_public_market_data.websockets.connect",
        lambda *args, **kwargs: FakeConnection(),
    )
    with pytest.raises(PublicMarketDataError, match="malformed error object"):
        asyncio.run(DerivPublicMarketDataClient().request({"ticks": "R_100"}))


def test_request_has_overall_deadline_when_irrelevant_messages_keep_arriving(monkeypatch):
    class DripSocket:
        async def send(self, payload):
            return None

        async def recv(self):
            await asyncio.sleep(0.005)
            return '{"req_id": -1, "msg_type": "tick"}'

    class DripConnection:
        async def __aenter__(self):
            return DripSocket()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "deriv_public_market_data.websockets.connect",
        lambda *args, **kwargs: DripConnection(),
    )
    client = DerivPublicMarketDataClient(response_timeout=0.06)
    with pytest.raises(PublicMarketDataError, match="response deadline exceeded"):
        asyncio.run(client.request({"ticks": "R_100"}, expected_msg_type="tick"))


@pytest.mark.parametrize("returned_epoch", [1666310399, 1666310460, 1792876920])
def test_ticks_history_rejects_candles_outside_requested_time_window(monkeypatch, returned_epoch):
    async def run():
        client = DerivPublicMarketDataClient()
        latest_candle_response = {
            "msg_type": "candles",
            "candles": [{
                "epoch": returned_epoch,
                "open": 668.69,
                "high": 669.60,
                "low": 668.11,
                "close": 669.60,
            }],
        }

        async def fake_request(payload, *, expected_msg_type=None):
            assert payload["start"] == 1666310400
            assert payload["end"] == "1666310460"
            assert expected_msg_type == "candles"
            return latest_candle_response

        monkeypatch.setattr(client, "request", fake_request)
        with pytest.raises(PublicMarketDataError, match="outside the requested half-open range"):
            await client.ticks_history(
                underlying_symbol="R_100",
                start_epoch=1666310400,
                end_epoch=1666310460,
                granularity_seconds=60,
                style="candles",
                count=1,
            )

    asyncio.run(run())


def test_ticks_history_accepts_candles_within_requested_time_window(monkeypatch):
    async def run():
        client = DerivPublicMarketDataClient()
        valid_response = {
            "msg_type": "candles",
            "candles": [{
                "epoch": 1666310400,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
            }],
        }

        async def fake_request(payload, *, expected_msg_type=None):
            return valid_response

        monkeypatch.setattr(client, "request", fake_request)
        result = await client.ticks_history(
            underlying_symbol="R_100",
            start_epoch=1666310400,
            end_epoch=1666310460,
            granularity_seconds=60,
            style="candles",
            count=1,
        )
        assert result == valid_response

    asyncio.run(run())
