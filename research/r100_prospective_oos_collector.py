from __future__ import annotations

"""Prospective R_100 research collector for AURELIA.

Uses only Deriv public market-data/proposal surfaces. It never authorizes,
submits, or reconciles a capital-moving transaction.
"""

import asyncio
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from runtime.adapters.deriv_ws import DerivWebSocketTransport
from runtime.strategy.autonomous_signal_engine import AutonomousSignalHunter

PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
SYMBOL = "R_100"
CURRENCY = "USD"
STRATEGY_ID = "R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0"
STRATEGY_VERSION = "0.2.0"
REGIME = "ALL_MARKET"
COLLECTION_SECONDS = int(os.getenv("AURELIA_R100_COLLECTION_SECONDS", "540"))
HORIZON_TICKS = int(os.getenv("AURELIA_R100_HORIZON_TICKS", "10"))
STATE_PATH = Path(os.getenv("AURELIA_R100_STATE_PATH", ".research_state/aurelia_r100_state.json"))
MIN_TRADE_PROBABILITY = 0.55
MAX_TRADE_PROBABILITY = 0.75

@dataclass(frozen=True)
class PendingSignal:
    signal_id: str
    signal_timestamp_utc: str
    entry_quote: float
    direction: str
    probability: float
    score: float
    age_ticks: int = 0

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def initial_state() -> dict[str, Any]:
    started = utc_now()
    return {
        "schema": "aurelia.r100.prospective_oos.v1",
        "manifest": {
            "experiment_id": f"R100-PROSPECTIVE-{started.strftime('%Y%m%dT%H%M%SZ')}",
            "hypothesis_id": "H-R100-TICK-MOMENTUM-001",
            "objective": "Test whether the frozen normalized tick-return-shock signal has positive prospective forward expectancy on R_100.",
            "dataset_policy": "public Deriv R_100 ticks collected prospectively; no historical backfill; no retuning after collection begins",
            "strategy_id": STRATEGY_ID,
            "strategy_version": STRATEGY_VERSION,
            "strategy_parameters": {
                "window": 64,
                "min_observations": 20,
                "threshold": 1.5,
                "cooldown_seconds": 30.0,
                "horizon_ticks": HORIZON_TICKS,
            },
            "search_space": {
                "window": [64],
                "min_observations": [20],
                "threshold": [1.5],
                "cooldown_seconds": [30.0],
                "horizon_ticks": [HORIZON_TICKS],
            },
            "trial_count": 1,
            "search_degrees_of_freedom": 0,
            "oos_reuse_count": 0,
            "selection_rule": "single predeclared frozen strategy; no OOS retuning",
            "regime_policy": "single predeclared ALL_MARKET cell; no data-mined regime segmentation in this campaign",
            "started_at_utc": iso(started),
            "oos_start_at_utc": iso(started + timedelta(hours=24)),
            "campaign_end_at_utc": iso(started + timedelta(days=7)),
            "sealed": False,
        },
        "observations": [],
        "pending": [],
        "quote_observations": [],
        "last_run_started_at_utc": None,
        "last_run_completed_at_utc": None,
        "last_price": None,
    }

def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        return initial_state()
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema") != "aurelia.r100.prospective_oos.v1":
        raise ValueError("R100_STATE_SCHEMA_MISMATCH")
    manifest = state.get("manifest") or {}
    if manifest.get("strategy_id") != STRATEGY_ID:
        raise ValueError("R100_STRATEGY_MISMATCH")
    if manifest.get("strategy_version") != STRATEGY_VERSION:
        raise ValueError("R100_STRATEGY_VERSION_MISMATCH")
    if manifest.get("sealed"):
        raise ValueError("R100_ARCHIVE_ALREADY_SEALED")
    return state

def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    temp.replace(path)

def build_signal_id(timestamp_utc: str, quote: float, direction: str) -> str:
    return "r100-signal:" + canonical_hash(
        {"timestamp_utc": timestamp_utc, "quote": quote, "direction": direction}
    )[:24]

def observe_tick(
    *,
    hunter: AutonomousSignalHunter,
    state: dict[str, Any],
    quote: float,
    received_at: datetime,
) -> None:
    pending = state["pending"]
    settled: list[dict[str, Any]] = []

    for item in pending:
        item["age_ticks"] = int(item["age_ticks"]) + 1

    for item in list(pending):
        if int(item["age_ticks"]) < HORIZON_TICKS:
            continue
        entry = float(item["entry_quote"])
        exit_quote = float(quote)
        raw_return = (exit_quote - entry) / entry
        outcome = int(
            (item["direction"] == "CALL" and raw_return > 0)
            or (item["direction"] == "PUT" and raw_return < 0)
        )
        settled.append({
            "schema": "aurelia.r100.forward_observation.v1",
            "signal_id": item["signal_id"],
            "strategy_id": STRATEGY_ID,
            "strategy_version": STRATEGY_VERSION,
            "symbol": SYMBOL,
            "regime": REGIME,
            "signal_timestamp_utc": item["signal_timestamp_utc"],
            "entry_quote": entry,
            "exit_quote": exit_quote,
            "exit_timestamp_utc": iso(received_at),
            "direction": item["direction"],
            "probability": float(item["probability"]),
            "score": float(item["score"]),
            "horizon_ticks": HORIZON_TICKS,
            "raw_return": raw_return,
            "outcome": outcome,
        })
        pending.remove(item)

    state["observations"].extend(settled)

    candidate = hunter.observe(
        symbol=SYMBOL,
        quote=float(quote),
        received_at=received_at,
    )
    if candidate is None:
        state["last_price"] = float(quote)
        return

    if not MIN_TRADE_PROBABILITY <= candidate.probability <= MAX_TRADE_PROBABILITY:
        raise ValueError("R100_PROBABILITY_POLICY_VIOLATION")
    if candidate.probability_status != "UNCALIBRATED_RESEARCH_ONLY":
        raise ValueError("R100_RESEARCH_PROBABILITY_STATUS_CHANGED")

    state["pending"].append(PendingSignal(
        signal_id=build_signal_id(iso(received_at), float(quote), candidate.direction),
        signal_timestamp_utc=iso(received_at),
        entry_quote=float(quote),
        direction=candidate.direction,
        probability=float(candidate.probability),
        score=float(candidate.score),
    ).__dict__)
    state["last_price"] = float(quote)

def probability_metrics(observations: list[dict[str, Any]]) -> dict[str, Any]:
    probabilities = [float(x["probability"]) for x in observations]
    outcomes = [int(x["outcome"]) for x in observations]
    if not probabilities:
        return {
            "sample_count": 0,
            "brier_score": None,
            "log_loss": None,
            "reliability_buckets": [],
            "drift_detected": False,
            "calibration_status": "NOT_RUN",
        }
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / len(probabilities)
    log_loss = 0.0
    for p, y in zip(probabilities, outcomes):
        clipped = min(1.0 - 1e-12, max(1e-12, p))
        log_loss += -(y * math.log(clipped) + (1 - y) * math.log(1 - clipped))
    log_loss /= len(probabilities)

    edges = [0.55, 0.60, 0.65, 0.70, 0.75 + 1e-12]
    buckets = []
    for lo, hi in zip(edges, edges[1:]):
        rows = [(p, y) for p, y in zip(probabilities, outcomes) if lo <= p < hi]
        if rows:
            buckets.append({
                "lower": lo,
                "upper": hi,
                "count": len(rows),
                "mean_probability": sum(p for p, _ in rows) / len(rows),
                "realized_rate": sum(y for _, y in rows) / len(rows),
            })

    midpoint = max(1, len(probabilities) // 2)
    baseline = sum(probabilities[:midpoint]) / midpoint
    recent_rows = probabilities[midpoint:]
    recent = sum(recent_rows) / max(1, len(recent_rows))
    drift_detected = abs(baseline - recent) > 0.05
    status = (
        "VALIDATED_RESEARCH"
        if len(probabilities) >= 100 and len(buckets) >= 3 and not drift_detected
        else "PROVISIONAL"
    )
    return {
        "sample_count": len(probabilities),
        "brier_score": brier,
        "log_loss": log_loss,
        "reliability_buckets": buckets,
        "drift_detected": drift_detected,
        "calibration_status": status,
    }

def evaluation(state: dict[str, Any]) -> dict[str, Any]:
    manifest = state["manifest"]
    oos_start = datetime.fromisoformat(manifest["oos_start_at_utc"].replace("Z", "+00:00"))
    rows = state["observations"]
    is_rows = [
        row for row in rows
        if datetime.fromisoformat(row["signal_timestamp_utc"].replace("Z", "+00:00")) < oos_start
    ]
    oos_rows = [
        row for row in rows
        if datetime.fromisoformat(row["signal_timestamp_utc"].replace("Z", "+00:00")) >= oos_start
    ]
    oos_returns = [float(x["raw_return"]) for x in oos_rows]
    mean_oos = sum(oos_returns) / len(oos_returns) if oos_returns else None
    win_rate = sum(int(x["outcome"]) for x in oos_rows) / len(oos_rows) if oos_rows else None
    calibration = probability_metrics(oos_rows)
    min_cell_trades = len(oos_rows)

    if min_cell_trades < 100:
        qualification_status = "INSUFFICIENT_SAMPLE"
    elif mean_oos is None or mean_oos <= 0:
        qualification_status = "OOS_FAILED"
    elif calibration["calibration_status"] != "VALIDATED_RESEARCH":
        qualification_status = "CALIBRATION_INCOMPLETE"
    else:
        qualification_status = "RESEARCH_QUALIFIED"

    campaign_complete = utc_now() >= datetime.fromisoformat(
        manifest["campaign_end_at_utc"].replace("Z", "+00:00")
    )
    state["manifest"]["sealed"] = bool(campaign_complete)
    archive_hash = canonical_hash({
        "manifest": state["manifest"],
        "observations": rows,
        "quote_observations": state["quote_observations"],
    })
    return {
        "schema": "aurelia.r100.prospective_oos.report.v1",
        "experiment_id": manifest["experiment_id"],
        "strategy_id": STRATEGY_ID,
        "strategy_version": STRATEGY_VERSION,
        "symbol": SYMBOL,
        "regime": REGIME,
        "observations_total": len(rows),
        "in_sample_observations": len(is_rows),
        "oos_observations": len(oos_rows),
        "min_trades_per_strategy_symbol_regime": min_cell_trades,
        "oos_mean_forward_return": mean_oos,
        "oos_win_rate": win_rate,
        "probability": calibration,
        "multiple_testing": {
            "trial_count": manifest["trial_count"],
            "search_degrees_of_freedom": manifest["search_degrees_of_freedom"],
            "oos_reuse_count": manifest["oos_reuse_count"],
            "status": "ACCOUNTED",
        },
        "execution_economics": {
            "status": "UNDETERMINED_PRODUCTION",
            "proposal_quote_observations": len(state["quote_observations"]),
            "reason": "Public proposal quotes observe broker pricing mechanics but do not prove fill, realized slippage, fees or net live expectancy.",
        },
        "qualification_status": qualification_status,
        "strategy_live_eligible": False,
        "execution_authorized": False,
        "capital_authority": False,
        "live_execution": False,
        "archive_hash": archive_hash,
        "campaign_complete": campaign_complete,
        "retuning_after_seal": False,
    }

async def collect_once(state: dict[str, Any]) -> None:
    start = utc_now()
    state["last_run_started_at_utc"] = iso(start)

    transport = DerivWebSocketTransport(PUBLIC_WS_URL, timeout_seconds=10.0)
    hunter = AutonomousSignalHunter(
        window=64,
        min_observations=20,
        threshold=1.5,
        cooldown_seconds=30.0,
    )
    await transport.connect()
    stream = transport.subscribe("ticks:R_100", {"ticks": SYMBOL})
    iterator = stream.__aiter__()
    deadline = asyncio.get_running_loop().time() + COLLECTION_SECONDS
    try:
        while asyncio.get_running_loop().time() < deadline:
            remaining = deadline - asyncio.get_running_loop().time()
            try:
                message = await asyncio.wait_for(iterator.__anext__(), timeout=max(1.0, remaining))
            except asyncio.TimeoutError:
                break
            tick = message.get("tick") or {}
            try:
                quote = float(tick["quote"])
                epoch = int(tick["epoch"])
            except (KeyError, TypeError, ValueError):
                continue
            received_at = datetime.fromtimestamp(epoch, tz=timezone.utc)
            prior_pending = len(state["pending"])
            observe_tick(
                hunter=hunter,
                state=state,
                quote=quote,
                received_at=received_at,
            )
            if len(state["pending"]) > prior_pending:
                new_signal = state["pending"][-1]
                try:
                    proposal = await transport.request({
                        "proposal": 1,
                        "amount": 1.0,
                        "basis": "stake",
                        "contract_type": new_signal["direction"],
                        "currency": CURRENCY,
                        "duration": HORIZON_TICKS,
                        "duration_unit": "t",
                        "underlying_symbol": SYMBOL,
                    })
                    proposal_payload = proposal.get("proposal") or {}
                    state["quote_observations"].append({
                        "signal_id": new_signal["signal_id"],
                        "captured_at_utc": iso(received_at),
                        "ask_price": proposal_payload.get("ask_price"),
                        "payout": proposal_payload.get("payout"),
                        "proposal_id": proposal_payload.get("id"),
                        "quote_status": "OBSERVED",
                    })
                except Exception as exc:
                    state["quote_observations"].append({
                        "signal_id": new_signal["signal_id"],
                        "captured_at_utc": iso(received_at),
                        "quote_status": "UNAVAILABLE",
                        "error_type": type(exc).__name__,
                    })
    finally:
        await transport.close()
    state["last_run_completed_at_utc"] = iso(utc_now())

async def main() -> int:
    state = load_state(STATE_PATH)
    await collect_once(state)
    report = evaluation(state)
    save_state(STATE_PATH, state)
    report_path = STATE_PATH.with_name("aurelia_r100_report.json")
    report_path.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps({
        "R100_PROSPECTIVE_COLLECTION": "PASS",
        "OBSERVATIONS_TOTAL": report["observations_total"],
        "OOS_OBSERVATIONS": report["oos_observations"],
        "OOS_WIN_RATE": report["oos_win_rate"],
        "QUALIFICATION_STATUS": report["qualification_status"],
        "EXECUTION_ECONOMICS": report["execution_economics"]["status"],
        "EXECUTION_AUTHORIZED": False,
        "CAPITAL_AUTHORITY": False,
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
