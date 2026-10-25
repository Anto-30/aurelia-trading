from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_history  # noqa: E402
import run_msnr_simulator as sim  # noqa: E402
import verify_history  # noqa: E402


def test_frozen_history_window_uses_exact_exclusive_utc_end_date():
    start_day = date.fromisoformat("2022-10-21")
    end_day_exclusive = date.fromisoformat("2024-10-21")
    start_epoch, end_exclusive = fetch_history.utc_window_epochs(start_day, end_day_exclusive)

    assert start_epoch == 1666310400
    assert end_exclusive == 1729468800
    assert datetime.fromtimestamp(start_epoch, timezone.utc).isoformat() == "2022-10-21T00:00:00+00:00"
    assert datetime.fromtimestamp(end_exclusive, timezone.utc).isoformat() == "2024-10-21T00:00:00+00:00"
    assert end_exclusive - start_epoch == 731 * 86400
    assert (end_exclusive - start_epoch) // 60 == 731 * 24 * 60
    assert end_exclusive - 60 == 1729468740

    for invalid_end in (start_day, date.fromisoformat("2022-10-20")):
        with pytest.raises(fetch_history.FetchError, match="exclusive UTC boundary"):
            fetch_history.utc_window_epochs(start_day, invalid_end)


def test_candle_normalizer_rejects_any_out_of_window_row_even_if_expected_rows_are_present():
    start = 1_666_310_400  # 2022-10-21T00:00:00Z
    valid = [
        {"epoch": start, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5},
        {"epoch": start + 60, "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0},
    ]
    for out_of_range_epoch in (start - 60, start + 120):
        response = [*valid, {**valid[-1], "epoch": out_of_range_epoch}]
        with pytest.raises(fetch_history.FetchError, match="outside requested half-open range"):
            fetch_history.normalize_candles(response, start, start + 120, 60)


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


@pytest.mark.parametrize(
    "start_epoch,end_exclusive,granularity",
    [
        (True, 1_666_320_060, 60),
        ("1666320000", 1_666_320_060, 60),
        (1_666_320_000, 1_666_320_060.0, 60),
        (1_666_320_000, 1_666_320_060, True),
        (-60, 0, 60),
        (1_666_320_000, 1_666_320_060, 0),
        (1_666_320_001, 1_666_320_061, 60),
        (1_666_320_000, 1_666_320_901, 60),
    ],
)
def test_candle_normalizer_rejects_invalid_window_and_granularity(start_epoch, end_exclusive, granularity):
    candle = {"epoch": 1_666_320_000, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
    with pytest.raises(fetch_history.FetchError):
        fetch_history.normalize_candles([candle], start_epoch, end_exclusive, granularity)


@pytest.mark.parametrize(
    "start_epoch,end_exclusive,granularity",
    [
        (True, 1_666_320_060, 60),
        ("1666320000", 1_666_320_060, 60),
        (1_666_320_000, 1_666_320_060.0, 60),
        (1_666_320_000, 1_666_320_060, True),
        (-60, 0, 60),
        (1_666_320_000, 1_666_320_060, 0),
        (1_666_320_001, 1_666_320_061, 60),
        (1_666_320_000, 1_666_320_900, 60),
    ],
)
def test_candle_payload_builder_rejects_invalid_window_and_granularity(start_epoch, end_exclusive, granularity):
    with pytest.raises(fetch_history.FetchError):
        fetch_history.build_candle_payload(start_epoch, end_exclusive, granularity)


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


@pytest.mark.parametrize(
    "field,invalid_value",
    [
        ("epoch", True),
        ("epoch", False),
        ("epoch", "1666320000"),
        ("epoch", 1666320000.0),
        ("epoch", -1),
        ("epoch", 10_000_000_000),
        ("open", "100.0"),
        ("high", True),
        ("low", False),
        ("close", "100.5"),
    ],
)
def test_candle_normalizer_rejects_coerced_or_out_of_range_json_values(field, invalid_value):
    start = 1_666_320_000
    candle = {"epoch": start, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
    candle[field] = invalid_value
    with pytest.raises(fetch_history.FetchError):
        fetch_history.normalize_candles([candle], start, start + 60, 60)


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
    assert failure["requested_start_date_utc_inclusive"] == "2022-10-21"
    assert failure["requested_end_date_utc_exclusive"] == "2024-10-21"
    assert "requested_end_date_utc_inclusive" not in failure
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


def test_history_verifier_accepts_v3_exclusive_end_manifest_and_exact_continuity(tmp_path):
    # Synthetic schema fixture only; this is not source market data or strategy evidence.
    start_day = date.fromisoformat("2022-10-21")
    end_day_exclusive = date.fromisoformat("2022-10-22")
    start_epoch, end_exclusive = fetch_history.utc_window_epochs(start_day, end_day_exclusive)
    granularity = 900
    csv_path = tmp_path / "fixture.csv"
    rows = [
        {"epoch": start_epoch + i * granularity, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
        for i in range(96)
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["epoch", "open", "high", "low", "close"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    active_row = {"underlying_symbol": "R_100", "pip_size": 0.01}
    active_response = {"msg_type": "active_symbols", "active_symbols": [active_row]}
    active_path = tmp_path / "R_100_active_symbols_response.json"
    active_raw = json.dumps(active_response, separators=(",", ":")) + "\n"
    active_path.write_text(active_raw, encoding="utf-8")
    csv_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    active_hash = hashlib.sha256(active_path.read_bytes()).hexdigest()
    manifest = {
        "schema": "atos.deriv_history_manifest.v3",
        "status": "FETCHED_AWAITING_INDEPENDENT_VERIFICATION",
        "underlying_symbol": "R_100",
        "timeframe": "15m",
        "granularity_seconds": granularity,
        "start_date_utc_inclusive": start_day.isoformat(),
        "end_date_utc_exclusive": end_day_exclusive.isoformat(),
        "range_end_exclusive_epoch": end_exclusive,
        "endpoint": fetch_history.PUBLIC_WS,
        "authentication": "none",
        "account_token_used": False,
        "active_symbols_response_file": active_path.name,
        "active_symbols_response_sha256": active_hash,
        "active_symbol_metadata_row": active_row,
        "pip_size_price_from_active_symbols": 0.01,
        "row_count": 96,
        "expected_row_count": 96,
        "first_epoch": start_epoch,
        "last_epoch": end_exclusive - granularity,
        "csv_path": str(csv_path),
        "csv_bytes": csv_path.stat().st_size,
        "csv_sha256": csv_hash,
    }
    manifest_path = tmp_path / "fixture.manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output_path = tmp_path / "fixture.verification.json"

    verify_history.verify(csv_path, manifest_path, output_path)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["status"] == "VERIFIED_CONTIGUOUS"
    assert report["row_count"] == 96
    assert report["first_epoch"] == start_epoch
    assert report["last_epoch"] == end_exclusive - granularity
    assert report["checks"]["last_epoch_matches_requested_last_bar"] is True


def test_history_verifier_rejects_legacy_inclusive_end_manifest(tmp_path):
    csv_path = tmp_path / "legacy.csv"
    csv_path.write_text("epoch,open,high,low,close\n", encoding="utf-8")
    manifest_path = tmp_path / "legacy.manifest.json"
    manifest_path.write_text(json.dumps({"schema": "atos.deriv_history_manifest.v2"}), encoding="utf-8")
    output_path = tmp_path / "legacy.verification.json"

    verify_history.verify(csv_path, manifest_path, output_path)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["status"] == "CORRUPTED"
    assert any("manifest.v3" in error for error in report["errors"])


def test_simulator_rejects_legacy_inclusive_end_manifest(tmp_path):
    csv_path = tmp_path / "legacy.csv"
    csv_path.write_text("epoch,open,high,low,close\n", encoding="utf-8")
    manifest_path = tmp_path / "legacy.manifest.json"
    manifest_path.write_text(json.dumps({"schema": "atos.deriv_history_manifest.v2"}), encoding="utf-8")
    verification_path = tmp_path / "legacy.verification.json"
    verification_path.write_text(json.dumps({}), encoding="utf-8")

    with pytest.raises(sim.SimulationError, match="Unsupported or legacy source manifest schema"):
        sim.load_verified_inputs(csv_path, manifest_path, verification_path, ROOT / "config" / "model_frozen.json")


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
