from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_history  # noqa: E402
import run_msnr_simulator as sim  # noqa: E402


def test_public_history_payload_uses_current_bounded_request_shape():
    start = 1_666_320_000  # aligned UTC minute
    end_exclusive = start + 3 * 86400
    req = fetch_history.build_candle_payload(start, end_exclusive, 60)
    assert req["ticks_history"] == "R_100"
    assert req["start"] == start
    assert req["end"] == str(end_exclusive - 60)
    assert "count" not in req  # bounded start/end mode; count selects latest-N history on the gateway
    assert (end_exclusive - start) // 60 <= 5000
    assert req["style"] == "candles"
    assert req["granularity"] == 60
    assert "symbol" not in req
    assert "loginid" not in req
    assert "adjust_start_time" not in req  # current schema only accepts 1 if set
    assert "subscribe" not in req  # one-shot request: omit rather than send legacy 0


def test_active_symbols_pip_size_is_price_unit_not_history_display_precision():
    assert fetch_history.validate_active_symbols_pip_size(0.0001) == 0.0001
    assert fetch_history.validate_active_symbols_pip_size(0.01) == 0.01
    with pytest.raises(fetch_history.FetchError):
        fetch_history.validate_active_symbols_pip_size(0)
    with pytest.raises(fetch_history.FetchError):
        fetch_history.validate_active_symbols_pip_size(float("inf"))
    with pytest.raises(fetch_history.FetchError):
        fetch_history.validate_active_symbols_pip_size(True)


def test_public_history_payload_rejects_over_limit_chunks():
    with pytest.raises(fetch_history.FetchError):
        fetch_history.build_candle_payload(0, 5001 * 60, 60)


def test_candle_normalizer_requires_every_current_schema_field_and_contiguity():
    start = 1_666_320_000
    good = [
        {"epoch": start, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5},
        {"epoch": start + 60, "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0},
    ]
    rows = fetch_history.normalize_candles(good, start, start + 120, 60)
    assert [row["epoch"] for row in rows] == [start, start + 60]
    bad = [dict(good[0]), dict(good[1])]
    del bad[1]["low"]
    with pytest.raises(fetch_history.FetchError, match="required fields"):
        fetch_history.normalize_candles(bad, start, start + 120, 60)
    gap = [good[0], {**good[1], "epoch": start + 120}]
    with pytest.raises(fetch_history.FetchError, match="continuity failure"):
        fetch_history.normalize_candles(gap, start, start + 180, 60)


def test_candle_normalizer_rejects_out_of_range_candle_even_when_window_is_complete():
    start = 1_666_320_000
    in_range = [
        {"epoch": start, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5},
        {"epoch": start + 60, "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0},
    ]
    # Reproduces a response containing full exact coverage plus an extra bar
    # outside the request. The old normalizer silently discarded that extra row.
    extra = {"epoch": start + 120, "open": 101.0, "high": 102.0, "low": 100.5, "close": 101.5}
    with pytest.raises(fetch_history.FetchError, match="outside requested interval"):
        fetch_history.normalize_candles(in_range + [extra], start, start + 120, 60)

    before = {"epoch": start - 60, "open": 99.0, "high": 100.0, "low": 98.0, "close": 99.5}
    with pytest.raises(fetch_history.FetchError, match="outside requested interval"):
        fetch_history.normalize_candles([before] + in_range, start, start + 120, 60)


def test_vectorized_features_have_strict_one_bar_execution_lag_and_no_forward_fill():
    n = 500
    close = 100.0 + np.sin(np.arange(n, dtype=float) / 7.0) * 2.0 + np.arange(n) * 0.002
    frame = pd.DataFrame({
        "epoch": np.arange(n, dtype=np.int64) * 60 + 1_666_320_000,
        "open": close - 0.05,
        "high": close + 0.25,
        "low": close - 0.25,
        "close": close,
    })
    features = sim.add_features(frame, sim.json.loads((ROOT / "config" / "model_frozen.json").read_text())["parameters"])
    assert (features["execution_signal"].iloc[1:].to_numpy() == features["signal_at_close"].iloc[:-1].to_numpy()).all()
    assert pd.isna(features["execution_atr"].iloc[0])
    assert features["execution_regime"].iloc[0] == 0
    assert not any(str(c).lower().endswith("ffill") for c in features.columns)


def test_chop_regime_hard_blocks_all_entries():
    n = 400
    frame = pd.DataFrame({
        "epoch": np.arange(n, dtype=np.int64) * 60 + 1_666_320_000,
        "open": np.full(n, 100.0),
        "high": np.full(n, 100.5),
        "low": np.full(n, 99.5),
        "close": np.full(n, 100.0),
    })
    params = sim.json.loads((ROOT / "config" / "model_frozen.json").read_text())["parameters"]
    feat = sim.add_features(frame, params)
    assert (feat["regime"] == 0).all()
    assert (feat["signal_at_close"] == 0).all()
    assert (feat["execution_signal"] == 0).all()


def _kernel_call(epoch, op, hi, lo, cl, signal, atr, process_start, global_offset,
                 state=None, final_chunk=False):
    state = state or {
        "side": 0, "entry_epoch": 0, "entry_mid": 0.0, "entry_atr": 0.0,
        "stop_price": 0.0, "target_price": 0.0, "qty": 0.0, "risk_cash": 0.0,
        "entry_cost": 0.0, "entry_index": 0, "equity": 10000.0,
    }
    result = sim._simulate_kernel(
        np.asarray(epoch, dtype=np.int64), np.asarray(op, dtype=np.float64),
        np.asarray(hi, dtype=np.float64), np.asarray(lo, dtype=np.float64),
        np.asarray(cl, dtype=np.float64), np.asarray(signal, dtype=np.int8),
        np.asarray(atr, dtype=np.float64), process_start, global_offset,
        state["side"], state["entry_epoch"], state["entry_mid"], state["entry_atr"],
        state["stop_price"], state["target_price"], state["qty"], state["risk_cash"],
        state["entry_cost"], state["entry_index"], state["equity"],
        0.01, 1.0, 0.0, 0.0, final_chunk,
    )
    keys = ["side", "entry_epoch", "entry_mid", "entry_atr", "stop_price", "target_price",
            "qty", "risk_cash", "entry_cost", "entry_index", "equity"]
    next_state = dict(zip(keys, result[2:13]))
    return result[0], int(result[1]), next_state, int(result[13])


def test_holding_duration_is_stable_across_segment_boundary():
    # Tiny deterministic unit fixture only; this is not fabricated market evidence.
    epoch = np.array([1_666_320_000 + x * 60 for x in range(5)], dtype=np.int64)
    op = np.array([100.0, 100.0, 100.5, 100.5, 100.5])
    hi = np.array([100.5, 100.5, 101.0, 101.0, 101.0])
    lo = np.array([99.5, 99.5, 100.0, 100.0, 100.0])
    cl = np.array([100.0, 100.5, 100.5, 100.5, 101.0])
    signal = np.array([0, 1, 0, 0, 0], dtype=np.int8)
    atr = np.ones(5, dtype=np.float64)
    atr[0] = np.nan
    _, n_first, state, err = _kernel_call(epoch[:2], op[:2], hi[:2], lo[:2], cl[:2], signal[:2], atr[:2], 0, 0)
    assert n_first == 0 and err == 0 and state["side"] == 1
    matrix, n_second, state2, err2 = _kernel_call(epoch, op, hi, lo, cl, signal, atr, 2, 2,
                                                   state=state, final_chunk=True)
    assert err2 == 0 and n_second == 1 and state2["side"] == 0
    assert int(matrix[0, 12]) == 4
    assert int(matrix[0, 13]) == 3  # final bar close


def test_kill_rule_exact_threshold_logic():
    ev, kill = sim.evaluate_kill_rule({"closed_trades": 20, "net_expectancy_R": 0.10, "profit_factor": 1.149})
    assert ev and kill
    ev, kill = sim.evaluate_kill_rule({"closed_trades": 20, "net_expectancy_R": 0.10, "profit_factor": 1.15})
    assert ev and not kill
    ev, kill = sim.evaluate_kill_rule({"closed_trades": 2, "net_expectancy_R": 0.0, "profit_factor": "infinite_no_losses"})
    assert ev and kill
    ev, kill = sim.evaluate_kill_rule({"closed_trades": 0, "net_expectancy_R": None, "profit_factor": None})
    assert not ev and not kill


def test_metadata_network_failure_persists_failed_closed_evidence_without_market_rows(tmp_path, monkeypatch):
    async def fail_metadata(*args, **kwargs):
        raise fetch_history.FetchError("gaierror: Temporary failure in name resolution")

    monkeypatch.setattr(fetch_history, "fetch_active_symbols_pip_size", fail_metadata)
    out_dir = tmp_path / "failed-fetch"
    args = argparse.Namespace(
        start_date="2022-10-21", end_date="2024-10-21", output_dir=str(out_dir),
        timeout=1.0, retries=0, retry_delay=0.0, chunk_days=3,
    )
    with pytest.raises(fetch_history.FetchError, match="Temporary failure in name resolution"):
        asyncio.run(fetch_history.async_main(args))
    failure = json.loads((out_dir / "fetch_run.failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == "FAILED_CLOSED"
    assert failure["market_data_received"] is False
    assert failure["account_token_used"] is False
    assert failure["live_orders_submitted"] is False
    assert not list(out_dir.glob("R_100_*.csv"))


def test_streaming_segmenter_preserves_every_row_across_90_day_boundaries(tmp_path):
    # Deterministic structural fixture only; this is not market data and is never
    # passed to the strategy or used to calculate performance metrics.
    start = 1_666_310_400  # 2022-10-21T00:00:00Z
    epochs = start + np.arange(181, dtype=np.int64) * 86400
    csv_path = tmp_path / "segment_fixture.csv"
    pd.DataFrame({
        "epoch": epochs,
        "open": np.full(len(epochs), 100.0),
        "high": np.full(len(epochs), 101.0),
        "low": np.full(len(epochs), 99.0),
        "close": np.full(len(epochs), 100.0),
    }).to_csv(csv_path, index=False)
    segments = list(sim.iter_90_day_segments(csv_path, int(epochs[0]), int(epochs[-1] + 86400), 60, 1000))
    assert [len(part) for part in segments] == [90, 90, 1]
    joined = pd.concat(segments, ignore_index=True)
    assert joined["epoch"].astype(np.int64).tolist() == epochs.tolist()


def test_no_verified_history_means_no_empirical_metrics_or_ledger(tmp_path):
    missing_csv = tmp_path / "R_100_1m.csv"
    missing_manifest = tmp_path / "R_100_1m.manifest.json"
    missing_verification = tmp_path / "R_100_1m.verification.json"
    ledger = tmp_path / "trade_ledger.jsonl"
    summary = tmp_path / "summary.json"
    args = argparse.Namespace(
        csv=missing_csv, manifest=missing_manifest, verification=missing_verification,
        model=ROOT / "config" / "model_frozen.json", ledger=ledger, summary=summary,
        git_commit="d04564aca0648201feff0326fe9af0fbcee92e94",
        allow_unverified_linear_proxy=True,
    )
    with pytest.raises(sim.SimulationError, match="Required input does not exist"):
        sim.run(args)
    assert not ledger.exists()
    assert not summary.exists()
