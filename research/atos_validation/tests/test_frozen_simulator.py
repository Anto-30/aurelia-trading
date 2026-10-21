from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from research.atos_validation.audited_ledger import verify_ledger
from research.atos_validation.deriv_data import persist_history
from scripts.run_frozen_simulator import (
    calculate_signal, load_data, load_simulation_config, prepare_entry, resolve_exit,
    run_simulation, ActiveTrade,
)
from research.labs.deterministic_intraday_strategies import StrategyCandidate


def config_doc(status="EXPLORATORY_UNVERIFIED"):
    return {
        "schema": "aurelia.msnr_simulation_config.v1",
        "symbol": "R_100",
        "granularity_seconds": 60,
        "fold_id": "historical_exploratory",
        "strategy": {
            "lookback_bars": 20, "tick_size": 0.1, "min_sweep_ticks": 1.0,
            "stop_buffer_ticks": 1.0, "max_reclaim_bars": 3,
            "require_volume_pop": False, "volume_pop_multiplier": 1.5,
            "allowed_regimes": ["TRENDING_LOW_VOL", "RANGING_LOW_VOL"], "version": "msnr-v1",
        },
        "regime_filter": {
            "lookback_bars": 20, "trend_efficiency_min": 0.35,
            "high_volatility_pct": 0.75, "version": "regime-v1",
        },
        "hmm": {
            "training_bars": 100, "refit_every_bars": 20, "feature_window": 14,
            "filter_kind": "gaussian", "min_confidence": 0.6, "max_entropy": 0.85,
            "random_state": 17, "alpha": 0.05, "beta": 1.0,
        },
        "execution": {
            "spread_price_units_round_trip": 0.2,
            "slippage_price_units_per_side": 0.05,
            "commission_cash_per_unit_round_trip": 0.0,
            "cash_per_price_unit_per_unit": 1.0,
            "position_size_units": 1.0,
            "max_holding_bars": 20,
            "same_bar_stop_target_policy": "stop_first",
        },
        "provenance": {"status": status},
    }


def make_history(start=1666310400, bars=80, granularity=60):
    rows = []
    price = 100.0
    for i in range(bars):
        # Oscillating deterministic closes give finite log-return and OHLC fields.
        close = price + (0.2 if i % 2 == 0 else -0.1)
        rows.append({
            "epoch": start + i * granularity,
            "open": price,
            "high": max(price, close) + 0.15,
            "low": min(price, close) - 0.15,
            "close": close,
        })
        price = close
    return pd.DataFrame(rows)


class FrozenSimulatorTests(unittest.TestCase):
    def test_data_loader_requires_companion_manifest_and_exact_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "R_100_1m.csv"
            rows = make_history(bars=4)
            frame = rows.assign(
                timestamp=pd.to_datetime(rows["epoch"], unit="s", utc=True),
                volume=np.nan,
            )[["timestamp", "epoch", "open", "high", "low", "close", "volume"]]
            persist_history(frame, path, symbol="R_100", granularity=60,
                            start_epoch=int(rows.epoch.iloc[0]), end_epoch=int(rows.epoch.iloc[-1]))
            loaded, manifest, digest = load_data(path)
            self.assertEqual(len(loaded), 4)
            self.assertEqual(digest, manifest["data_sha256"])
            # A changed CSV byte cannot be accepted against the original manifest.
            path.write_text(path.read_text() + "\n")
            with self.assertRaises(ValueError):
                load_data(path)

    def test_config_requires_explicit_opt_in_for_unverified_scenario(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "scenario.json"
            path.write_text(json.dumps(config_doc()))
            with self.assertRaisesRegex(ValueError, "allow-unverified-scenario"):
                load_simulation_config(path)
            loaded, digest, _ = load_simulation_config(path, allow_unverified_scenario=True)
            self.assertEqual(loaded["schema"], "aurelia.msnr_simulation_config.v1")
            self.assertEqual(len(digest), 64)

    def test_missing_instrument_cost_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(FileNotFoundError, "will not guess"):
                load_simulation_config(Path(td) / "missing.json", allow_unverified_scenario=True)

    def test_signal_api_cannot_receive_current_candle(self):
        import inspect
        params = list(inspect.signature(calculate_signal).parameters)
        self.assertEqual(params, ["history", "msnr_config", "regime_config"])
        self.assertNotIn("current_candle", params)

    def test_entry_fill_applies_costs_and_rejects_gap_invalid_geometry(self):
        candidate = StrategyCandidate(
            strategy_id="MSNR_LIQUIDITY_SWEEP", version="test", direction="LONG",
            signal_timestamp_utc="2022-10-21T00:00:00Z",
            entry_timing="NEXT_BAR_OPEN_AFTER_SIGNAL",
            stop_reference_price=99.0, target_reference_price=103.0,
            target_mode="OPPOSING_REFERENCE_RANGE_EDGE", regime="RANGING_LOW_VOL",
            evidence_codes=("TEST_SIGNAL",),
        )
        execution = config_doc()["execution"]
        candle = pd.Series({"open": 101.0})
        result = prepare_entry(candidate, candle, execution=execution)
        self.assertAlmostEqual(result["entry_fill_price"], 101.15)
        self.assertAlmostEqual(result["stop_fill_price"], 98.85)
        gapped = prepare_entry(candidate, pd.Series({"open": 104.0}), execution=execution)
        self.assertIsNone(gapped)

    def test_same_candle_stop_target_conflict_uses_pessimistic_stop_first(self):
        trade = ActiveTrade(
            decision_event_id="abc", direction="LONG", entry_index=3,
            entry_epoch=1666310580, raw_entry_price=100.0, entry_fill_price=100.15,
            stop_reference_price=99.0, target_reference_price=101.0,
            hmm_regime_state="TREND", size_units=1.0, initial_risk_cash=10.0,
        )
        candle = pd.Series({"open": 100.0, "high": 102.0, "low": 98.0, "close": 100.2})
        result = resolve_exit(trade, candle, candle_index=3, execution=config_doc()["execution"])
        self.assertEqual(result, (99.0, "STOP_AND_TARGET_SAME_BAR_STOP_FIRST"))

    def test_end_to_end_short_history_yields_verified_zero_trade_ledger_not_fake_trades(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csv_path = root / "R_100_1m.csv"
            rows = make_history(bars=40)
            frame = rows.assign(
                timestamp=pd.to_datetime(rows["epoch"], unit="s", utc=True),
                volume=np.nan,
            )[["timestamp", "epoch", "open", "high", "low", "close", "volume"]]
            persist_history(frame, csv_path, symbol="R_100", granularity=60,
                            start_epoch=int(rows.epoch.iloc[0]), end_epoch=int(rows.epoch.iloc[-1]))
            config_path = root / "scenario.json"
            config_path.write_text(json.dumps(config_doc()))
            output = root / "evidence" / "trade_ledger.jsonl"
            report = run_simulation(csv_path, output, config_path, allow_unverified_scenario=True)
            audit = verify_ledger(output)
            self.assertTrue(audit["integrity_verified"])
            self.assertTrue(audit["manifest_verified"])
            self.assertEqual(report["trade_count"], 0)
            self.assertGreater(report["decision_count"], 0)
            self.assertEqual(report["cost_profile_status"], "EXPLORATORY_UNVERIFIED")
            self.assertEqual(report["live_execution"], "BLOCKED")
            self.assertEqual(report["final_execution_authorization"], False)

    def test_refuses_to_overwrite_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ledger = root / "ledger.jsonl"
            ledger.write_text("not an empty artifact")
            with self.assertRaises(FileExistsError):
                run_simulation(root / "missing.csv", ledger, root / "missing-config.json",
                               allow_unverified_scenario=True)


if __name__ == "__main__":
    unittest.main()
