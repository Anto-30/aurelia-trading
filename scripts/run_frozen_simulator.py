#!/usr/bin/env python3
"""Causal, research-only replay of AURELIA's registered MSNR liquidity-sweep strategy.

The strategy definition is the existing
research.labs.deterministic_intraday_strategies.detect_msnr_liquidity_sweep entrypoint.
This program never submits an order. Instrument tick size, cash-per-price-unit, size and
costs are required configuration inputs because R_100 spot candles do not establish a
tradeable Deriv contract's payoff or actual execution economics.

Every decision uses only the closed-bar prefix. Entries occur at the next candle open.
Stops/targets are tested against subsequent OHLC ranges; when a candle crosses both,
the pessimistic stop-first policy is used. OHLC cannot establish the exact intrabar order,
so this remains bar-based research, not execution-quality evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.atos_validation.audited_ledger import AuditedLedgerWriter
from research.atos_validation.deriv_data import DATA_COLUMNS
from research.atos_validation.regime_validation import RegimeDetector
from research.labs.deterministic_intraday_strategies import (
    MSNRConfig, RegimeConfig, StrategyBar, StrategyCandidate,
    detect_msnr_liquidity_sweep,
)
from scripts.verify_deriv_history_manifest import verify_history

STRATEGY_ID = "MSNR_LIQUIDITY_SWEEP"
CONFIG_SCHEMA = "aurelia.msnr_simulation_config.v1"
SHA256_LEN = 64


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_bundle_sha256() -> str:
    """Digest the exact simulator and critical signal/HMM/audit source files."""
    paths = (
        ROOT / "scripts/run_frozen_simulator.py",
        ROOT / "research/labs/deterministic_intraday_strategies.py",
        ROOT / "research/atos_validation/regime_validation.py",
        ROOT / "research/atos_validation/audited_ledger.py",
        ROOT / "scripts/verify_deriv_history_manifest.py",
    )
    manifest = {
        path.relative_to(ROOT).as_posix(): sha256_file(path)
        for path in paths
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def finite_number(value: Any, name: str, *, minimum: float | None = None, strict: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and (result <= minimum if strict else result < minimum):
        operator = ">" if strict else ">="
        raise ValueError(f"{name} must be {operator} {minimum}")
    return result


def aware_utc(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be timezone-aware ISO-8601")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be timezone-aware ISO-8601") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return stamp.astimezone(timezone.utc)


def _require_keys(doc: dict[str, Any], keys: set[str], label: str) -> None:
    missing = sorted(keys - set(doc))
    if missing:
        raise ValueError(f"{label} missing required keys: {missing}")


def load_simulation_config(path: str | Path, *, allow_unverified_scenario: bool = False) -> tuple[dict[str, Any], str, dict[str, str | None]]:
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(
            f"MSNR simulation config missing: {config_path}. Supply instrument tick size, "
            "cash conversion/size, and explicit spread/slippage/commission inputs with provenance; "
            "the simulator will not guess them."
        )
    raw = config_path.read_bytes()
    config_hash = hashlib.sha256(raw).hexdigest()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("simulation config must be UTF-8 JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != CONFIG_SCHEMA:
        raise ValueError(f"simulation config schema must be {CONFIG_SCHEMA}")

    _require_keys(doc, {"symbol", "granularity_seconds", "fold_id", "strategy", "regime_filter", "hmm", "execution", "provenance"}, "config")
    if doc["symbol"] != "R_100":
        raise ValueError("this simulator is currently scoped to R_100 only")
    if doc["granularity_seconds"] != 60:
        raise ValueError("MSNR R_100 replay requires 60-second (1m) candles in this implementation")
    if not isinstance(doc["fold_id"], str) or not doc["fold_id"].strip():
        raise ValueError("fold_id must be a non-empty string")

    strategy = doc["strategy"]
    regime = doc["regime_filter"]
    hmm = doc["hmm"]
    execution = doc["execution"]
    provenance = doc["provenance"]
    for value, label in ((strategy, "strategy"), (regime, "regime_filter"), (hmm, "hmm"),
                         (execution, "execution"), (provenance, "provenance")):
        if not isinstance(value, dict):
            raise ValueError(f"{label} must be a JSON object")
    _require_keys(strategy, {"lookback_bars", "tick_size", "min_sweep_ticks", "stop_buffer_ticks",
                             "max_reclaim_bars", "require_volume_pop", "volume_pop_multiplier",
                             "allowed_regimes", "version"}, "strategy")
    _require_keys(regime, {"lookback_bars", "trend_efficiency_min", "high_volatility_pct", "version"}, "regime_filter")
    _require_keys(hmm, {"training_bars", "refit_every_bars", "feature_window", "filter_kind",
                        "min_confidence", "max_entropy", "random_state", "alpha", "beta"}, "hmm")
    _require_keys(execution, {"spread_price_units_round_trip", "slippage_price_units_per_side",
                              "commission_cash_per_unit_round_trip", "cash_per_price_unit_per_unit",
                              "position_size_units", "max_holding_bars", "same_bar_stop_target_policy"}, "execution")
    _require_keys(provenance, {"status"}, "provenance")

    # Validate all parameters here, before opening an output ledger.
    if isinstance(strategy["lookback_bars"], bool) or not isinstance(strategy["lookback_bars"], int) or strategy["lookback_bars"] < 3:
        raise ValueError("strategy.lookback_bars must be an integer >= 3")
    finite_number(strategy["tick_size"], "strategy.tick_size", minimum=0.0, strict=True)
    finite_number(strategy["min_sweep_ticks"], "strategy.min_sweep_ticks", minimum=0.0, strict=True)
    finite_number(strategy["stop_buffer_ticks"], "strategy.stop_buffer_ticks", minimum=0.0)
    if isinstance(strategy["max_reclaim_bars"], bool) or not isinstance(strategy["max_reclaim_bars"], int) or strategy["max_reclaim_bars"] < 1:
        raise ValueError("strategy.max_reclaim_bars must be an integer >= 1")
    if not isinstance(strategy["require_volume_pop"], bool):
        raise ValueError("strategy.require_volume_pop must be boolean")
    finite_number(strategy["volume_pop_multiplier"], "strategy.volume_pop_multiplier", minimum=0.0, strict=True)
    if not isinstance(strategy["allowed_regimes"], list) or not strategy["allowed_regimes"]:
        raise ValueError("strategy.allowed_regimes must be a non-empty list")
    if strategy["require_volume_pop"]:
        raise ValueError("Deriv synthetic-index historical candles have no verified exchange volume; do not enable volume-pop gating on this CSV")
    if isinstance(regime["lookback_bars"], bool) or not isinstance(regime["lookback_bars"], int) or regime["lookback_bars"] < 2:
        raise ValueError("regime_filter.lookback_bars must be an integer >= 2")
    finite_number(regime["trend_efficiency_min"], "regime_filter.trend_efficiency_min", minimum=0.0)
    if float(regime["trend_efficiency_min"]) > 1:
        raise ValueError("regime_filter.trend_efficiency_min must be <= 1")
    finite_number(regime["high_volatility_pct"], "regime_filter.high_volatility_pct", minimum=0.0, strict=True)

    for key, minimum in (("training_bars", 100), ("refit_every_bars", 1), ("feature_window", 2)):
        if isinstance(hmm[key], bool) or not isinstance(hmm[key], int) or hmm[key] < minimum:
            raise ValueError(f"hmm.{key} must be an integer >= {minimum}")
    if hmm["filter_kind"] not in {"gaussian", "alpha_beta"}:
        raise ValueError("hmm.filter_kind must be gaussian or alpha_beta")
    finite_number(hmm["min_confidence"], "hmm.min_confidence", minimum=0.0, strict=True)
    if float(hmm["min_confidence"]) > 1:
        raise ValueError("hmm.min_confidence must be <= 1")
    finite_number(hmm["max_entropy"], "hmm.max_entropy", minimum=0.0, strict=True)
    if float(hmm["max_entropy"]) > 1:
        raise ValueError("hmm.max_entropy must be <= 1")
    if isinstance(hmm["random_state"], bool) or not isinstance(hmm["random_state"], int):
        raise ValueError("hmm.random_state must be an integer")
    finite_number(hmm["alpha"], "hmm.alpha", minimum=0.0, strict=True)
    if float(hmm["alpha"]) > 1.0 / 3.0:
        raise ValueError("hmm.alpha must be <= 1/3")
    finite_number(hmm["beta"], "hmm.beta", minimum=0.0, strict=True)
    if float(hmm["beta"]) > 2.0:
        raise ValueError("hmm.beta must be <= 2")

    for key in ("spread_price_units_round_trip", "slippage_price_units_per_side", "commission_cash_per_unit_round_trip"):
        finite_number(execution[key], f"execution.{key}", minimum=0.0)
    finite_number(execution["cash_per_price_unit_per_unit"], "execution.cash_per_price_unit_per_unit", minimum=0.0, strict=True)
    finite_number(execution["position_size_units"], "execution.position_size_units", minimum=0.0, strict=True)
    if isinstance(execution["max_holding_bars"], bool) or not isinstance(execution["max_holding_bars"], int) or execution["max_holding_bars"] < 1:
        raise ValueError("execution.max_holding_bars must be an integer >= 1")
    if execution["same_bar_stop_target_policy"] != "stop_first":
        raise ValueError("same_bar_stop_target_policy must be stop_first (pessimistic fill ordering)")

    status = provenance["status"]
    if status not in {"VERIFIED", "EXPLORATORY_UNVERIFIED"}:
        raise ValueError("provenance.status must be VERIFIED or EXPLORATORY_UNVERIFIED")
    source_hashes: dict[str, str | None] = {"cost_source_sha256": None, "instrument_source_sha256": None}
    if status == "EXPLORATORY_UNVERIFIED" and not allow_unverified_scenario:
        raise ValueError("cost/instrument inputs are unverified; rerun with --allow-unverified-scenario to label results exploratory")
    if status == "VERIFIED":
        _require_keys(provenance, {"instrument_source_file", "instrument_source_sha256",
                                   "cost_source_file", "cost_source_sha256", "observed_at_utc"}, "verified provenance")
        aware_utc(provenance["observed_at_utc"], "provenance.observed_at_utc")
        for field, hash_key in (("instrument_source_file", "instrument_source_sha256"),
                                ("cost_source_file", "cost_source_sha256")):
            source = Path(str(provenance[field]))
            if not source.is_absolute():
                source = config_path.parent / source
            if not source.is_file():
                raise FileNotFoundError(f"verified provenance source is missing: {source}")
            actual = sha256_file(source)
            expected = provenance[hash_key]
            if not isinstance(expected, str) or actual != expected:
                raise ValueError(f"{field} SHA-256 mismatch: expected a digest anchored in config")
            source_hashes[hash_key] = actual
    else:
        source_hashes["cost_source_sha256"] = provenance.get("cost_source_sha256")
        source_hashes["instrument_source_sha256"] = provenance.get("instrument_source_sha256")
        for key, digest in source_hashes.items():
            if digest is not None and (not isinstance(digest, str) or len(digest) != SHA256_LEN or any(c not in "0123456789abcdef" for c in digest)):
                raise ValueError(f"{key} must be null or a lowercase SHA-256")
    return doc, config_hash, source_hashes


def load_data(data_path: str | Path, *, expected_symbol: str = "R_100", expected_granularity: int = 60) -> tuple[pd.DataFrame, dict[str, Any], str]:
    """Load CSV only after verifying its companion manifest, data hash and exact coverage."""
    path = Path(data_path)
    report = verify_history(path)
    if report.get("verified") is not True or report.get("symbol") != expected_symbol:
        raise ValueError("historical CSV/manifest failed verification or symbol mismatch")
    if report.get("granularity_seconds") != expected_granularity:
        raise ValueError("historical CSV granularity does not match simulator config")
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frame = pd.read_csv(path)
    missing = set(DATA_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"historical CSV missing required columns: {sorted(missing)}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    frame["epoch"] = pd.to_numeric(frame["epoch"], errors="raise").astype("int64")
    frame = frame.sort_values("epoch").reset_index(drop=True)
    if frame["epoch"].duplicated().any() or frame.empty:
        raise ValueError("historical CSV is empty or has duplicate epochs")
    if not frame["epoch"].diff().dropna().eq(expected_granularity).all():
        raise ValueError("historical CSV contains timestamp gaps; exact continuous coverage is required (stricter than 99%)")
    if not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("historical timestamps are not increasing")
    if not frame["timestamp"].dt.tz:
        raise ValueError("historical timestamps must be timezone-aware")
    for col in ("open", "high", "low", "close"):
        frame[col] = pd.to_numeric(frame[col], errors="raise")
        if not np.isfinite(frame[col].to_numpy(dtype=float)).all() or (frame[col] <= 0).any():
            raise ValueError(f"invalid OHLC field: {col}")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("OHLC high inconsistency")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("OHLC low inconsistency")
    return frame, manifest, report["data_sha256"]


def _to_strategy_bar(row: pd.Series) -> StrategyBar:
    volume_raw = row["volume"]
    volume = None if pd.isna(volume_raw) else float(volume_raw)
    return StrategyBar(
        timestamp_utc=pd.Timestamp(row["timestamp"]).isoformat(),
        open=float(row["open"]), high=float(row["high"]), low=float(row["low"]),
        close=float(row["close"]), volume=volume, session_id=None,
    )


def calculate_signal(
    history: pd.DataFrame,
    *,
    msnr_config: MSNRConfig,
    regime_config: RegimeConfig,
) -> StrategyCandidate | None:
    """Evaluate MSNR using only the already-closed history prefix; no current bar argument exists."""
    if history.empty:
        return None
    needed = max(msnr_config.lookback_bars + msnr_config.max_reclaim_bars + 2, regime_config.lookback_bars + 2)
    prefix = history.tail(needed)
    bars = [_to_strategy_bar(row) for _, row in prefix.iterrows()]
    return detect_msnr_liquidity_sweep(
        bars, config=msnr_config, regime_config=regime_config,
        volume_source_verified=False,
    )


class CausalHMMRegimeTracker:
    """Causal Gaussian/Alpha-Beta HMM state: refits exclude the current signal candle."""
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.detector: RegimeDetector | None = None
        self.last_fit_signal_index: int | None = None
        self.last_fit_attempt_index: int | None = None

    def state_for_closed_history(self, history: pd.DataFrame) -> str:
        # Retain the absolute position for refit cadence, but only materialize the
        # rolling training window. Converting every prior close on every bar makes
        # a 24-month 1m replay O(N^2) and operationally unusable.
        signal_index = len(history) - 1
        required_closes = self.config["training_bars"] + self.config["feature_window"] + 1
        closes = history["close"].iloc[-required_closes:].to_numpy(dtype=float)
        if len(closes) < required_closes:
            return "UNDEFINED"
        should_refit = (
            self.detector is None
            or self.last_fit_signal_index is None
            or signal_index - self.last_fit_signal_index >= self.config["refit_every_bars"]
        )
        current_features = RegimeDetector.features(closes, window=self.config["feature_window"])
        current_feature = current_features[-1]
        if should_refit and (
            self.last_fit_attempt_index is None
            or signal_index - self.last_fit_attempt_index >= self.config["refit_every_bars"]
        ):
            # The training close array deliberately excludes the just-closed signal candle.
            training_closes = closes[:-1][-(
                self.config["training_bars"] + self.config["feature_window"]
            ):]
            training_features = RegimeDetector.features(training_closes, window=self.config["feature_window"])
            self.last_fit_attempt_index = signal_index
            if len(training_features) < 100:
                self.detector = None
                return "UNDEFINED"
            detector = RegimeDetector(
                n_states=3,
                min_confidence=self.config["min_confidence"],
                max_entropy=self.config["max_entropy"],
                random_state=self.config["random_state"],
                filter_kind=self.config["filter_kind"],
                alpha=self.config["alpha"],
                beta=self.config["beta"],
            )
            try:
                detector.fit(training_features)
                # Reconstruct the causal posterior through the training prefix under
                # this model, then apply the current signal candle's feature once.
                for train_row in training_features:
                    detector.update(train_row)
                prediction = detector.update(current_feature)
            except (ValueError, RuntimeError, np.linalg.LinAlgError, FloatingPointError):
                self.detector = None
                return "UNDEFINED"
            self.detector = detector
            self.last_fit_signal_index = signal_index
            return prediction.regime if prediction.valid else "UNDEFINED"

        if self.detector is None:
            return "UNDEFINED"
        prediction = self.detector.update(current_feature)
        return prediction.regime if prediction.valid else "UNDEFINED"


@dataclass
class ActiveTrade:
    decision_event_id: str
    direction: str
    entry_index: int
    entry_epoch: int
    raw_entry_price: float
    entry_fill_price: float
    stop_reference_price: float
    target_reference_price: float
    hmm_regime_state: str
    size_units: float


def _fill_price(reference_price: float, direction: str, *, is_entry: bool, spread_half: float, slippage: float) -> float:
    # A buy pays ask-side friction; a sell pays bid-side friction. Same friction is
    # charged on exit in the opposite direction. These are scenario values, not ticks.
    buy = (direction == "LONG" and is_entry) or (direction == "SHORT" and not is_entry)
    return reference_price + spread_half + slippage if buy else reference_price - spread_half - slippage


def _cash_price_cost(price_units: float, *, cash_per_price_unit: float, size: float) -> float:
    return price_units * cash_per_price_unit * size


def prepare_entry(
    candidate: StrategyCandidate,
    current_candle: pd.Series,
    *,
    execution: dict[str, Any],
) -> dict[str, float] | None:
    """Price the next candle open plus entry-side costs; reject gaps that invalidate geometry."""
    direction = candidate.direction
    raw_entry = float(current_candle["open"])
    spread = float(execution["spread_price_units_round_trip"])
    half_spread, slip = spread / 2.0, float(execution["slippage_price_units_per_side"])
    fill = _fill_price(raw_entry, direction, is_entry=True, spread_half=half_spread, slippage=slip)
    stop = float(candidate.stop_reference_price)
    target = candidate.target_reference_price
    if fill <= 0 or target is None:
        return None
    stop_fill = _fill_price(stop, direction, is_entry=False, spread_half=half_spread, slippage=slip)
    target_fill = _fill_price(float(target), direction, is_entry=False, spread_half=half_spread, slippage=slip)
    if direction == "LONG":
        if not (stop_fill < fill < target_fill):
            return None
    else:
        if not (target_fill < fill < stop_fill):
            return None
    risk_cash = abs(fill - stop_fill) * float(execution["cash_per_price_unit_per_unit"]) * float(execution["position_size_units"])
    risk_cash += float(execution["commission_cash_per_unit_round_trip"]) * float(execution["position_size_units"])
    if not math.isfinite(risk_cash) or risk_cash <= 0:
        return None
    return {
        "raw_entry_price": raw_entry, "entry_fill_price": fill,
        "stop_fill_price": stop_fill, "target_fill_price": target_fill,
        "initial_risk_cash": risk_cash,
    }


def resolve_exit(
    trade: ActiveTrade,
    candle: pd.Series,
    *,
    candle_index: int,
    execution: dict[str, Any],
) -> tuple[float, str] | None:
    """Return raw market exit reference price and reason using pessimistic OHLC rules."""
    o, h, l, c = map(float, (candle["open"], candle["high"], candle["low"], candle["close"]))
    stop, target = trade.stop_reference_price, trade.target_reference_price
    if trade.direction == "LONG":
        stop_hit = l <= stop
        target_hit = h >= target
        if stop_hit:  # stop-first also resolves same-bar stop/target ambiguity
            return (o if o < stop else stop, "STOP_GAP" if o < stop else ("STOP_AND_TARGET_SAME_BAR_STOP_FIRST" if target_hit else "STOP_HIT"))
        if target_hit:
            return target, "TARGET_HIT"
    else:
        stop_hit = h >= stop
        target_hit = l <= target
        if stop_hit:
            return (o if o > stop else stop, "STOP_GAP" if o > stop else ("STOP_AND_TARGET_SAME_BAR_STOP_FIRST" if target_hit else "STOP_HIT"))
        if target_hit:
            return target, "TARGET_HIT"
    held_bars = candle_index - trade.entry_index + 1
    if held_bars >= int(execution["max_holding_bars"]):
        return c, "MAX_HOLD_CLOSE"
    return None


def close_active_trade(
    writer: AuditedLedgerWriter,
    trade: ActiveTrade,
    *,
    raw_exit_price: float,
    exit_reason: str,
    candle_epoch: int,
    granularity_seconds: int,
    execution: dict[str, Any],
    provenance: dict[str, str | None],
    cost_status: str,
) -> None:
    spread = float(execution["spread_price_units_round_trip"])
    half_spread = spread / 2.0
    slip = float(execution["slippage_price_units_per_side"])
    unit_cash = float(execution["cash_per_price_unit_per_unit"])
    size = trade.size_units
    exit_fill = _fill_price(raw_exit_price, trade.direction, is_entry=False, spread_half=half_spread, slippage=slip)
    entry_spread_cash = _cash_price_cost(half_spread, cash_per_price_unit=unit_cash, size=size)
    exit_spread_cash = entry_spread_cash
    entry_slippage_cash = _cash_price_cost(slip, cash_per_price_unit=unit_cash, size=size)
    exit_slippage_cash = entry_slippage_cash
    spread_cost = entry_spread_cash + exit_spread_cash
    slippage_cost = entry_slippage_cash + exit_slippage_cash
    commission_cost = float(execution["commission_cash_per_unit_round_trip"]) * size
    sign = 1.0 if trade.direction == "LONG" else -1.0
    gross_pnl = sign * (raw_exit_price - trade.raw_entry_price) * unit_cash * size
    exit_timestamp = pd.Timestamp(candle_epoch, unit="s", tz="UTC") + pd.Timedelta(seconds=granularity_seconds)
    writer.record_trade(
        decision_event_id=trade.decision_event_id,
        entry_epoch=trade.entry_epoch,
        exit_timestamp=exit_timestamp.to_pydatetime(),
        entry_price=trade.entry_fill_price,
        exit_price=exit_fill,
        initial_risk_cash=max(
            abs(trade.entry_fill_price - _fill_price(trade.stop_reference_price, trade.direction,
                                                     is_entry=False, spread_half=half_spread, slippage=slip))
            * unit_cash * size + commission_cost,
            1e-12,
        ),
        gross_pnl_cash=gross_pnl,
        spread_cost_cash=spread_cost,
        slippage_cost_cash=slippage_cost,
        commission_cost_cash=commission_cost,
        entry_reference_price=trade.raw_entry_price,
        exit_reference_price=raw_exit_price,
        entry_spread_cost_cash=entry_spread_cash,
        exit_spread_cost_cash=exit_spread_cash,
        entry_slippage_cost_cash=entry_slippage_cash,
        exit_slippage_cost_cash=exit_slippage_cash,
        stop_reference_price=trade.stop_reference_price,
        target_reference_price=trade.target_reference_price,
        exit_reason=exit_reason,
        cost_profile_status=cost_status,
        cost_source_sha256=provenance.get("cost_source_sha256"),
        instrument_source_sha256=provenance.get("instrument_source_sha256"),
    )


def run_simulation(
    data_path: str | Path,
    ledger_path: str | Path,
    config_path: str | Path,
    *,
    allow_unverified_scenario: bool = False,
) -> dict[str, Any]:
    # Refuse an existing ledger before parsing config or touching input data.
    # This preserves immutable-output semantics even when later inputs are invalid.
    output_path = Path(ledger_path)
    if output_path.exists() or output_path.with_suffix(output_path.suffix + ".manifest.json").exists():
        raise FileExistsError("refusing to overwrite an existing JSONL ledger or manifest")

    config, config_hash, source_hashes = load_simulation_config(
        config_path, allow_unverified_scenario=allow_unverified_scenario
    )
    frame, manifest, data_hash = load_data(
        data_path, expected_symbol=config["symbol"],
        expected_granularity=config["granularity_seconds"],
    )
    status = config["provenance"]["status"]
    code_hash = code_bundle_sha256()
    strategy_cfg = config["strategy"]
    regime_cfg = config["regime_filter"]
    hmm_cfg = config["hmm"]
    execution = config["execution"]
    msnr = MSNRConfig(
        lookback_bars=strategy_cfg["lookback_bars"],
        tick_size=float(strategy_cfg["tick_size"]),
        min_sweep_ticks=float(strategy_cfg["min_sweep_ticks"]),
        stop_buffer_ticks=float(strategy_cfg["stop_buffer_ticks"]),
        max_reclaim_bars=strategy_cfg["max_reclaim_bars"],
        require_volume_pop=strategy_cfg["require_volume_pop"],
        volume_pop_multiplier=float(strategy_cfg["volume_pop_multiplier"]),
        allowed_regimes=tuple(strategy_cfg["allowed_regimes"]),
        version=strategy_cfg["version"],
    )
    regime = RegimeConfig(
        lookback_bars=regime_cfg["lookback_bars"],
        trend_efficiency_min=float(regime_cfg["trend_efficiency_min"]),
        high_volatility_pct=float(regime_cfg["high_volatility_pct"]),
        version=str(regime_cfg["version"]),
    )
    hmm = CausalHMMRegimeTracker(hmm_cfg)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    active: ActiveTrade | None = None
    trade_count = 0
    decision_count = 0
    last_signal_epoch: int | None = None
    with AuditedLedgerWriter(
        output_path, symbol=config["symbol"], data_sha256=data_hash,
        granularity_seconds=config["granularity_seconds"],
        strategy_code_sha256=code_hash,
    ) as writer:
        for i in range(1, len(frame)):
            # Decision at close of candle i-1; current candle i is not passed to
            # either signal or HMM calculations. Only its open is read after decision.
            history = frame.iloc[:i]
            signal_epoch = int(history.iloc[-1]["epoch"])
            last_signal_epoch = signal_epoch
            regime_state = hmm.state_for_closed_history(history)
            decision: dict[str, Any] | None = None

            if active is not None:
                writer.record_decision(
                    signal_bar_epoch=signal_epoch, strategy=STRATEGY_ID,
                    model_config_sha256=config_hash, fold_id=config["fold_id"],
                    action="NO_TRADE", reason_codes=["POSITION_OPEN_AT_SIGNAL_CLOSE"],
                    hmm_regime_state=regime_state, accepted=False,
                )
                decision_count += 1
            else:
                candidate = calculate_signal(history, msnr_config=msnr, regime_config=regime)
                if candidate is None:
                    writer.record_decision(
                        signal_bar_epoch=signal_epoch, strategy=STRATEGY_ID,
                        model_config_sha256=config_hash, fold_id=config["fold_id"],
                        action="NO_TRADE", reason_codes=["NO_MSNR_SETUP"],
                        hmm_regime_state=regime_state, accepted=False,
                    )
                    decision_count += 1
                elif regime_state == "UNDEFINED":
                    writer.record_decision(
                        signal_bar_epoch=signal_epoch, strategy=STRATEGY_ID,
                        model_config_sha256=config_hash, fold_id=config["fold_id"],
                        action="ENTER_LONG" if candidate.direction == "LONG" else "ENTER_SHORT",
                        reason_codes=["CAUSAL_HMM_REGIME_UNDEFINED", *candidate.evidence_codes],
                        hmm_regime_state="UNDEFINED", accepted=False,
                    )
                    decision_count += 1
                else:
                    # The signal decision is committed at candle N-1 using no candle-N
                    # price. The scheduled entry is then evaluated at candle N open.
                    # If the open invalidates stop/target geometry, write a separate
                    # cancellation event at N rather than rewriting the old decision.
                    event_id = writer.record_decision(
                        signal_bar_epoch=signal_epoch, strategy=STRATEGY_ID,
                        model_config_sha256=config_hash, fold_id=config["fold_id"],
                        action="ENTER_LONG" if candidate.direction == "LONG" else "ENTER_SHORT",
                        reason_codes=list(candidate.evidence_codes),
                        hmm_regime_state=regime_state, accepted=True,
                    )
                    decision_count += 1
                    prepared = prepare_entry(candidate, frame.iloc[i], execution=execution)
                    if prepared is None:
                        writer.cancel_decision(
                            decision_event_id=event_id,
                            cancellation_epoch=int(frame.iloc[i]["epoch"]),
                            reason_codes=["ENTRY_GAP_INVALIDATES_STOP_TARGET_GEOMETRY"],
                        )
                    else:
                        active = ActiveTrade(
                            decision_event_id=event_id, direction=candidate.direction, entry_index=i,
                            entry_epoch=int(frame.iloc[i]["epoch"]), raw_entry_price=prepared["raw_entry_price"],
                            entry_fill_price=prepared["entry_fill_price"],
                            stop_reference_price=float(candidate.stop_reference_price),
                            target_reference_price=float(candidate.target_reference_price),
                            hmm_regime_state=regime_state,
                            size_units=float(execution["position_size_units"]),
                        )

            # Exits are evaluated against the current candle's range only after the
            # decision and potential entry at that candle's open have been fixed.
            if active is not None:
                exit_result = resolve_exit(active, frame.iloc[i], candle_index=i, execution=execution)
                if exit_result is not None:
                    raw_exit_price, exit_reason = exit_result
                    close_active_trade(
                        writer, active, raw_exit_price=raw_exit_price, exit_reason=exit_reason,
                        candle_epoch=int(frame.iloc[i]["epoch"]),
                        granularity_seconds=config["granularity_seconds"], execution=execution,
                        provenance=source_hashes, cost_status=status,
                    )
                    trade_count += 1
                    active = None

        if active is not None:
            last = frame.iloc[-1]
            close_active_trade(
                writer, active, raw_exit_price=float(last["close"]),
                exit_reason="DATA_END_FORCED_CLOSE",
                candle_epoch=int(last["epoch"]),
                granularity_seconds=config["granularity_seconds"], execution=execution,
                provenance=source_hashes, cost_status=status,
            )
            trade_count += 1
            active = None
        manifest_out = writer.close()

    from research.atos_validation.audited_ledger import verify_ledger
    audit = verify_ledger(output_path)
    return {
        "symbol": config["symbol"], "granularity_seconds": config["granularity_seconds"],
        "data_sha256": data_hash, "history_manifest_sha256": manifest["manifest_sha256"],
        "config_sha256": config_hash, "strategy_code_sha256": code_hash,
        "ledger_sha256": audit["ledger_sha256"],
        "ledger_manifest_sha256": sha256_file(output_path.with_suffix(output_path.suffix + ".manifest.json")),
        "decision_count": decision_count, "trade_count": trade_count,
        "coverage_complete": manifest["coverage_complete"], "bars": len(frame),
        "cost_profile_status": status, "ledger_verified": audit["integrity_verified"],
        "capital_authority": False, "live_execution": "BLOCKED",
        "final_execution_authorization": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, required=True, help="CSV with verified companion .manifest.json")
    parser.add_argument("--ledger", type=Path, required=True, help="new JSONL output path; existing files are refused")
    parser.add_argument("--config", type=Path, required=True, help="explicit MSNR, instrument and execution-cost JSON")
    parser.add_argument("--allow-unverified-scenario", action="store_true",
                        help="allow unverified instrument/cost assumptions, explicitly labelled exploratory")
    args = parser.parse_args()
    try:
        report = run_simulation(
            args.data_path, args.ledger, args.config,
            allow_unverified_scenario=args.allow_unverified_scenario,
        )
    except Exception as exc:
        print("FROZEN_SIMULATOR=BLOCKED")
        print(f"REASON={type(exc).__name__}: {exc}")
        print("LEDGER_GENERATED=false")
        print("LIVE_EXECUTION=BLOCKED")
        print("FINAL_EXECUTION_AUTHORIZATION=false")
        return 2
    print("FROZEN_SIMULATOR=COMPLETED")
    for key, value in report.items():
        print(f"{key.upper()}={value}")
    print("PERFORMANCE_QUALIFICATION_CLAIMED=false")
    print("ORDERS_SUBMITTED=0")
    print("LIVE_EXECUTION=BLOCKED")
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
