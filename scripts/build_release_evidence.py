#!/usr/bin/env python3
"""Build the nine AURELIA release-evidence JSON files from actual local artifacts.

Unavailable measurements are JSON null and documented in evidence_notes.md. Null means
unknown/not measured, never zero or pass. The script does not submit trades, change
config/LIVE_LOCK.yaml, or grant live authorization. Incomplete output is not certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.atos_validation.audited_ledger import verify_ledger


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def read_json(path: Path | None, label: str, notes: list[str]) -> dict[str, Any] | None:
    if path is None:
        notes.append(f"{label}: no source path supplied; related fields remain null.")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} source is unreadable JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} source must be a JSON object: {path}")
    return value


def nullable_string(value: Any, field: str, notes: list[str]) -> str | None:
    if value is None:
        notes.append(f"{field}: unavailable in source; emitted null.")
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string or null")
    return value.strip()


def nullable_bool(value: Any, field: str, notes: list[str]) -> bool | None:
    if value is None:
        notes.append(f"{field}: unavailable in source; emitted null.")
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a JSON boolean or null")
    return value


def nullable_int(value: Any, field: str, notes: list[str], *, minimum: int = 0) -> int | None:
    if value is None:
        notes.append(f"{field}: unavailable in source; emitted null.")
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum} or null")
    return value


def nullable_float(value: Any, field: str, notes: list[str], *, minimum: float | None = None) -> float | None:
    if value is None:
        notes.append(f"{field}: unavailable in source; emitted null.")
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite JSON number or null")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{field} must be >= {minimum} or null")
    return result


def project(source: dict[str, Any] | None, fields: dict[str, str], notes: list[str], prefix: str) -> dict[str, Any]:
    """Project a source object to an exact key set; values are type checked, never guessed."""
    output: dict[str, Any] = {}
    for field, kind in fields.items():
        value = source.get(field) if source else None
        label = f"{prefix}.{field}"
        cast = {"string": nullable_string, "bool": nullable_bool, "int": nullable_int, "float": nullable_float}[kind]
        output[field] = cast(value, label, notes)
    return output


def read_trade_records(path: Path | None, notes: list[str]) -> list[dict[str, Any]]:
    if path is None:
        notes.append("trade ledger: no JSONL path supplied; trade-derived evidence remains null.")
        return []
    report = verify_ledger(path)
    if not report.get("manifest_verified"):
        raise ValueError(f"ledger manifest not verified for {path}; seal the ledger before use")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            row = json.loads(line)
            if row.get("record_type") == "trade_closed":
                records.append(row)
    notes.append(
        f"trade ledger: hash chain and companion manifest verified; SHA-256={report['ledger_sha256']}; "
        f"decisions={report['decision_record_count']}; closed trades={report['closed_trade_record_count']}."
    )
    return records


def verify_history_manifest(path: Path | None, data_path: Path | None, notes: list[str]) -> dict[str, Any] | None:
    if path is None:
        notes.append("history manifest: not supplied; no dataset hash is asserted.")
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"history manifest is unreadable: {path}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != "atos.deriv_history_manifest.v1":
        raise ValueError("history manifest has an unsupported schema")
    claimed = manifest.get("manifest_sha256")
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if not isinstance(claimed, str) or hashlib.sha256(canonical).hexdigest() != claimed:
        raise ValueError("history manifest SHA-256 mismatch")
    if manifest.get("coverage_complete") is not True:
        raise ValueError("history manifest does not assert complete coverage")
    if data_path is None or not data_path.is_file():
        raise ValueError("--data-path is required to verify the CSV against the history manifest")
    observed = sha256_file(data_path)
    if observed != manifest.get("data_sha256"):
        raise ValueError("history CSV SHA-256 does not match its manifest")
    notes.append(f"history manifest and CSV verified: {data_path}; data SHA-256={observed}.")
    return manifest


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return float(ordered[idx])


def load_ping_values(soak: dict[str, Any] | None, notes: list[str]) -> list[float]:
    if not soak:
        return []
    raw = soak.get("raw_log_path")
    if not isinstance(raw, str) or not raw:
        notes.append("soak raw log: summary lacks raw_log_path; p99 ping RTT cannot be independently derived.")
        return []
    path = Path(raw)
    if not path.is_file():
        notes.append(f"soak raw log: path not found ({path}); p99 ping RTT unavailable.")
        return []
    values: list[float] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid soak JSONL at {path}:{line_no}") from exc
        if row.get("event") == "ping_rtt":
            value = row.get("rtt_ms")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
                raise ValueError(f"invalid ping RTT in {path}:{line_no}")
            values.append(float(value))
    notes.append(f"soak raw log: parsed {len(values)} ping RTT samples; percentile fields are WebSocket round-trip time, not one-way feed latency.")
    return values


def parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 string")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} is not valid ISO-8601") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field} must include timezone")
    return dt.astimezone(timezone.utc)


def calculate_oos(
    trades: list[dict[str, Any]], manifest: dict[str, Any] | None, *, strategy: str | None,
    start_date: str | None, end_date: str | None, freeze_utc: str | None,
    starting_equity: float | None, notes: list[str],
) -> dict[str, Any]:
    result = {key: None for key in (
        "data_artifact_sha256", "oos_start_date", "oos_end_date", "total_trades",
        "net_expectancy_r", "profit_factor", "max_drawdown_percent", "win_rate_percent", "sharpe_ratio")}
    if manifest is None:
        notes.append("prospective OOS: data manifest unverified; dataset-bound OOS fields remain null.")
        return result
    result["data_artifact_sha256"] = manifest.get("data_sha256")
    if not (strategy and start_date and end_date and freeze_utc):
        notes.append("prospective OOS: supply strategy, interval and independently anchored pre-OOS model/config freeze time; metrics remain null.")
        return result
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError("OOS dates must use YYYY-MM-DD") from exc
    freeze = parse_timestamp(freeze_utc, "model freeze timestamp")
    if end <= start:
        raise ValueError("OOS end date must follow OOS start date")
    result["oos_start_date"], result["oos_end_date"] = start.isoformat(), end.isoformat()
    if freeze.date() >= start:
        notes.append("prospective OOS: freeze timestamp is not before OOS start; sealed-OOS metrics remain null.")
        return result
    low = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    high = datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)
    selected = []
    for row in trades:
        if row.get("strategy") == strategy:
            entry = parse_timestamp(row.get("entry_timestamp_utc"), "ledger entry_timestamp_utc")
            if low <= entry < high:
                selected.append(row)
    if not selected:
        result["total_trades"] = 0
        notes.append("prospective OOS: zero qualifying closed trades; total_trades is 0 and performance metrics remain null.")
        return result
    returns = [float(row["r_multiple"]) for row in selected]
    if not all(math.isfinite(value) for value in returns):
        raise ValueError("OOS ledger contains non-finite R multiples")
    result["total_trades"] = len(selected)
    result["net_expectancy_r"] = float(statistics.fmean(returns))
    wins, losses = sum(v for v in returns if v > 0), -sum(v for v in returns if v < 0)
    result["profit_factor"] = wins / losses if losses > 0 else None
    result["win_rate_percent"] = 100.0 * sum(v > 0 for v in returns) / len(returns)
    if losses == 0:
        notes.append("prospective_oos.profit_factor: loss denominator is zero; infinite PF is not serialized, emitted null.")
    if starting_equity is not None:
        if not math.isfinite(starting_equity) or starting_equity <= 0:
            raise ValueError("starting equity must be finite and positive")
        ordered = sorted(selected, key=lambda row: row["entry_timestamp_utc"])
        equity, peak, max_dd = starting_equity, starting_equity, 0.0
        daily_pnl: dict[str, float] = {}
        for row in ordered:
            equity += float(row["net_pnl_cash"])
            peak = max(peak, equity)
            if peak > 0:
                max_dd = max(max_dd, (peak - equity) / peak * 100.0)
            day = parse_timestamp(row["entry_timestamp_utc"], "entry timestamp").date().isoformat()
            daily_pnl[day] = daily_pnl.get(day, 0.0) + float(row["net_pnl_cash"])
        result["max_drawdown_percent"] = max_dd
        if len(daily_pnl) >= 2:
            daily_returns: list[float] = []
            running_equity = starting_equity
            for day, daily_cash_pnl in daily_pnl.items():
                if running_equity <= 0:
                    notes.append(f"prospective_oos.sharpe_ratio: non-positive equity before {day}; emitted null.")
                    daily_returns = []
                    break
                daily_returns.append(daily_cash_pnl / running_equity)
                running_equity += daily_cash_pnl
            if len(daily_returns) >= 2:
                sd = statistics.stdev(daily_returns)
                result["sharpe_ratio"] = statistics.mean(daily_returns) / sd * math.sqrt(365.0) if sd > 0 else None
                if sd == 0:
                    notes.append("prospective_oos.sharpe_ratio: zero variance in observed daily returns; emitted null.")
            elif not daily_returns:
                notes.append("prospective_oos.sharpe_ratio: no valid daily return series; emitted null.")
            else:
                notes.append("prospective_oos.sharpe_ratio: fewer than two valid daily returns; emitted null.")
        else:
            notes.append("prospective_oos.sharpe_ratio: fewer than two UTC trading days; emitted null.")
    else:
        notes.append("prospective_oos.max_drawdown_percent and sharpe_ratio: no measured starting equity supplied; emitted null.")
    notes.append(f"prospective OOS metrics derived from {len(selected)} closed trades for strategy={strategy}; independently verify the model freeze record before calling the window sealed.")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-dir", type=Path, default=Path("evidence"))
    p.add_argument("--lock-path", type=Path, default=Path("config/LIVE_LOCK.yaml"))
    p.add_argument("--history-manifest", type=Path)
    p.add_argument("--data-path", type=Path)
    p.add_argument("--ledger", type=Path)
    p.add_argument("--oos-strategy")
    p.add_argument("--oos-start-date", help="YYYY-MM-DD")
    p.add_argument("--oos-end-date", help="YYYY-MM-DD; exclusive end boundary")
    p.add_argument("--model-freeze-utc", help="timestamp supported by an independently anchored freeze record")
    p.add_argument("--starting-equity", type=float)
    p.add_argument("--broker-lifecycle-json", type=Path)
    p.add_argument("--recovery-json", type=Path)
    p.add_argument("--soak-summary", type=Path)
    p.add_argument("--calibration-json", type=Path)
    p.add_argument("--cost-evidence-json", type=Path)
    p.add_argument("--security-audit-json", type=Path)
    p.add_argument("--deployment-json", type=Path)
    p.add_argument("--wfa-fold-metrics", type=Path)
    p.add_argument("--symbol", default="R_100")
    p.add_argument("--minimum-expectancy-r", type=float, default=0.15)
    p.add_argument("--minimum-profit-factor", type=float, default=1.5)
    p.add_argument("--maximum-drawdown-percent", type=float, default=3.0)
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()

    notes = [
        "STATUS: output is incomplete whenever a required field is null. Null means not measured/verified, never zero or pass.",
        "JSON has no comment syntax; field-level missing-data explanations are stored here to preserve the exact nine JSON schemas.",
        "SHA-256 verifies content relative to the saved digest after independently anchoring it; it cannot prove omitted events were ever logged.",
        "No code path submits an order, edits LIVE_LOCK.yaml, or grants live execution authorization.",
    ]
    try:
        manifest = verify_history_manifest(args.history_manifest, args.data_path, notes)
        trades = read_trade_records(args.ledger, notes)
        if manifest is not None and trades and any(r.get("data_sha256") != manifest.get("data_sha256") for r in trades):
            raise ValueError("one or more ledger trades are not bound to the verified history dataset hash")
        broker_src = read_json(args.broker_lifecycle_json, "broker lifecycle", notes)
        recovery_src = read_json(args.recovery_json, "recovery matrix", notes)
        soak_src = read_json(args.soak_summary, "soak summary", notes)
        calibration_src = read_json(args.calibration_json, "calibration", notes)
        cost_src = read_json(args.cost_evidence_json, "execution cost evidence", notes)
        security_src = read_json(args.security_audit_json, "security audit", notes)
        deployment_src = read_json(args.deployment_json, "deployment", notes)

        broker = project(broker_src, {
            "app_id": "int", "connection_start_utc": "string", "connection_end_utc": "string",
            "total_heartbeats_received": "int", "missed_heartbeats": "int",
            "unplanned_disconnects": "int", "data_gap_seconds": "int",
        }, notes, "broker_lifecycle")
        recovery = project(recovery_src, {
            "simulated_disconnects": "int", "successful_reconnections": "int",
            "failed_reconnections": "int", "average_recovery_time_ms": "float",
            "max_recovery_time_ms": "float", "phantom_orders_generated": "int",
        }, notes, "recovery_matrix")

        soak = {"duration_seconds": None, "total_ticks_processed": None, "average_latency_ms": None,
                "p95_latency_ms": None, "p99_latency_ms": None, "max_latency_ms": None,
                "memory_leak_detected": None}
        if soak_src:
            full = (soak_src.get("full_3600_second_run") is True and soak_src.get("target_duration_seconds") == 3600
                    and isinstance(soak_src.get("actual_elapsed_seconds"), (int, float))
                    and soak_src.get("actual_elapsed_seconds", 0) >= 3600)
            if full:
                soak["duration_seconds"] = 3600
            else:
                notes.append("soak_3600s.duration_seconds: actual run was not verified to meet 3,600 seconds; emitted null.")
            ticks = soak_src.get("tick_count")
            if isinstance(ticks, int) and not isinstance(ticks, bool) and ticks >= 0:
                soak["total_ticks_processed"] = ticks
            else:
                notes.append("soak_3600s.total_ticks_processed: unavailable or invalid; emitted null.")
            for dest, src in (("average_latency_ms", "ping_rtt_mean_ms"),
                              ("p95_latency_ms", "ping_rtt_p95_ms"), ("max_latency_ms", "ping_rtt_max_ms")):
                value = soak_src.get(src)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and value >= 0:
                    soak[dest] = float(value)
                else:
                    notes.append(f"soak_3600s.{dest}: summary measurement unavailable; emitted null.")
            p99 = percentile(load_ping_values(soak_src, notes), .99)
            if p99 is not None:
                soak["p99_latency_ms"] = p99
            else:
                notes.append("soak_3600s.p99_latency_ms: no raw ping samples; emitted null.")
            soak["memory_leak_detected"] = nullable_bool(soak_src.get("memory_leak_detected"), "soak_3600s.memory_leak_detected", notes)
            notes.append("Soak latency fields are WebSocket ping round-trip time, not one-way quote latency and not signal-processing time.")

        calibration = project(calibration_src, {
            "model_type": "string", "number_of_states": "int", "training_iterations_to_converge": "int",
            "in_sample_expectancy_r": "float", "out_of_sample_expectancy_r": "float",
            "performance_degradation_percent": "float",
        }, notes, "calibration")
        if calibration_src and calibration["performance_degradation_percent"] is None:
            ins, outs = calibration["in_sample_expectancy_r"], calibration["out_of_sample_expectancy_r"]
            if ins is not None and outs is not None and abs(ins) > 1e-12:
                calibration["performance_degradation_percent"] = (ins - outs) / abs(ins) * 100.0
                notes.append("calibration.performance_degradation_percent: derived as (IS expectancy - OOS expectancy)/abs(IS expectancy)*100.")
            else:
                notes.append("calibration.performance_degradation_percent: missing or zero IS expectancy; emitted null.")

        closed_for_symbol = [row for row in trades if row.get("symbol") == args.symbol]
        economics = {"symbol": args.symbol if closed_for_symbol else None, "average_spread_pips": None,
                     "average_slippage_bps": None, "total_commission_paid_simulated": None,
                     "total_slippage_cost_simulated": None, "cost_as_percent_of_gross_profit": None}
        if closed_for_symbol:
            spreads = [float(r["spread_pips"]) for r in closed_for_symbol if isinstance(r.get("spread_pips"), (int, float)) and not isinstance(r.get("spread_pips"), bool) and math.isfinite(float(r["spread_pips"]))]
            slips = [float(r["slippage_bps"]) for r in closed_for_symbol if isinstance(r.get("slippage_bps"), (int, float)) and not isinstance(r.get("slippage_bps"), bool) and math.isfinite(float(r["slippage_bps"]))]
            if spreads:
                economics["average_spread_pips"] = statistics.fmean(spreads)
            else:
                notes.append("execution_economics.average_spread_pips: observed values absent; emitted null.")
            if slips:
                economics["average_slippage_bps"] = statistics.fmean(slips)
            else:
                notes.append("execution_economics.average_slippage_bps: observed values absent; emitted null.")
            economics["total_commission_paid_simulated"] = sum(float(r["commission_cost_cash"]) for r in closed_for_symbol)
            economics["total_slippage_cost_simulated"] = sum(float(r["slippage_cost_cash"]) for r in closed_for_symbol)
            gross_profit = sum(max(0.0, float(r["gross_pnl_cash"])) for r in closed_for_symbol)
            total_cost = sum(float(r["total_cost_cash"]) for r in closed_for_symbol)
            if gross_profit > 0:
                economics["cost_as_percent_of_gross_profit"] = 100.0 * total_cost / gross_profit
            else:
                notes.append("execution_economics.cost_as_percent_of_gross_profit: gross-profit denominator is not positive; emitted null.")
        else:
            notes.append(f"execution_economics: no closed ledger records for {args.symbol}; costs remain null.")
        if cost_src:
            required = {"schema", "symbol", "data_sha256", "trade_ledger_sha256", "cost_source_file",
                        "cost_source_sha256", "cost_method", "independent_review_status"}
            missing = sorted(required - set(cost_src))
            if missing:
                raise ValueError("execution cost evidence missing fields: " + ", ".join(missing))
            if cost_src.get("schema") != "aurelia.execution_economics_evidence.v1":
                raise ValueError("unsupported execution-cost evidence schema")
            if cost_src.get("symbol") != args.symbol or manifest is None or cost_src.get("data_sha256") != manifest.get("data_sha256"):
                raise ValueError("execution cost symbol/data hash does not match verified history")
            if args.ledger is None or cost_src.get("trade_ledger_sha256") != sha256_file(args.ledger):
                raise ValueError("execution cost evidence ledger hash does not match verified JSONL ledger")
            if cost_src.get("independent_review_status") not in {"PENDING", "APPROVED", "REJECTED"}:
                raise ValueError("invalid independent_review_status in cost evidence")
            if cost_src.get("independent_review_status") == "REJECTED":
                raise ValueError("cost evidence was rejected by independent review")
            source_hash, source_name = cost_src.get("cost_source_sha256"), cost_src.get("cost_source_file")
            resolved = Path(source_name)
            if not resolved.is_absolute() and args.cost_evidence_json:
                resolved = args.cost_evidence_json.parent / resolved
            if not resolved.is_file():
                notes.append("execution cost evidence points to a missing cost source file; incomplete.")
            elif sha256_file(resolved) != source_hash:
                raise ValueError("execution cost source SHA-256 mismatch")
            notes.append("Cost source hash linkage is not independent proof of quote authenticity or economic realism.")

        security = project(security_src, {
            "read_only_token_auth_success": "bool",
            "trade_attempt_with_read_only_token": "string",
            "secrets_masked_in_logs": "bool",
        }, notes, "security_audit")
        lock_text = args.lock_path.read_text(encoding="utf-8") if args.lock_path.is_file() else None
        if lock_text is None:
            notes.append(f"security/deployment: lock file missing at {args.lock_path}; lock-derived fields are null.")
            security["live_lock_yaml_blob_hash"] = None
            blocked, authorization = None, None
        else:
            security["live_lock_yaml_blob_hash"] = git_blob_sha1(args.lock_path)
            blocked = "LIVE_EXECUTION: BLOCKED" in lock_text
            if "FINAL_EXECUTION_AUTHORIZATION: false" in lock_text:
                authorization = False
            elif "FINAL_EXECUTION_AUTHORIZATION: true" in lock_text:
                authorization = True
            else:
                authorization = None
                notes.append("deployment.final_execution_authorization: no recognized boolean in lock; emitted null.")
        deployment = project(deployment_src, {
            "ci_pipeline_status": "string", "execution_environment": "string",
        }, notes, "deployment")
        deployment["live_execution_blocked"] = blocked
        deployment["final_execution_authorization"] = authorization
        if blocked is False:
            notes.append("CRITICAL: lock does not state LIVE_EXECUTION: BLOCKED; investigate manually. This script still cannot authorize execution.")

        oos = calculate_oos(trades, manifest, strategy=args.oos_strategy, start_date=args.oos_start_date,
                            end_date=args.oos_end_date, freeze_utc=args.model_freeze_utc,
                            starting_equity=args.starting_equity, notes=notes)
        fold_stable: bool | None = None
        if args.wfa_fold_metrics:
            import csv
            with args.wfa_fold_metrics.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            if rows and {"model", "fold", "expectancy_r"}.issubset(rows[0]):
                model = args.oos_strategy or "alpha_beta_hmm"
                values = [float(row["expectancy_r"]) for row in rows if row.get("model") == model and row.get("expectancy_r") not in ("", None)]
                if len(values) >= 2 and all(math.isfinite(value) for value in values):
                    fold_stable = all(value > 0 for value in values)
                    notes.append(f"strategy_eligibility.walk_forward_stable: screen rule is positive expectancy in every available fold for {model}; this does not prove statistical stability.")
                else:
                    notes.append("strategy_eligibility.walk_forward_stable: fewer than two usable folds; emitted null.")
            else:
                raise ValueError("WFA fold metrics CSV must contain model, fold and expectancy_r columns")
        else:
            notes.append("strategy_eligibility.walk_forward_stable: WFA fold metrics not supplied; emitted null.")
        exp, pf, dd = oos.get("net_expectancy_r"), oos.get("profit_factor"), oos.get("max_drawdown_percent")
        eligibility = {
            "meets_minimum_expectancy": None if exp is None else bool(exp > args.minimum_expectancy_r),
            "meets_minimum_profit_factor": None if pf is None else bool(pf > args.minimum_profit_factor),
            "meets_max_drawdown_limit": None if dd is None else bool(dd <= args.maximum_drawdown_percent),
            "walk_forward_stable": fold_stable,
            "eligible_for_live_unlock": False,
        }
        notes.append("strategy_eligibility.eligible_for_live_unlock is fixed false by design: research metrics do not grant capital authority.")

        docs = {
            "broker_lifecycle.json": broker,
            "recovery_matrix.json": recovery,
            "soak_3600s.json": soak,
            "prospective_oos.json": oos,
            "calibration.json": calibration,
            "execution_economics.json": economics,
            "security_audit.json": security,
            "deployment.json": deployment,
            "strategy_eligibility.json": eligibility,
        }
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        destinations = [args.evidence_dir / name for name in docs] + [args.evidence_dir / "evidence_notes.md"]
        existing = [str(path) for path in destinations if path.exists()]
        if existing and not args.overwrite:
            raise FileExistsError("refusing to overwrite evidence; archive and anchor previous hashes, then pass --overwrite: " + ", ".join(existing))
        for name, value in docs.items():
            destination = args.evidence_dir / name
            temporary = destination.with_name(destination.name + ".tmp")
            temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
            temporary.replace(destination)
        notes_path = args.evidence_dir / "evidence_notes.md"
        notes_path.write_text("# Evidence generation notes\n\n" + "\n".join(f"- {item}" for item in notes) + "\n", encoding="utf-8")
        nulls = sum(value is None for doc in docs.values() for value in doc.values())
        print("RELEASE_EVIDENCE=GENERATED_INCOMPLETE" if nulls else "RELEASE_EVIDENCE=GENERATED_CHECK_REVIEW")
        print(f"FILES_WRITTEN={len(docs)}")
        print(f"NULL_FIELDS={nulls}")
        print(f"EVIDENCE_DIR={args.evidence_dir}")
        print("LIVE_EXECUTION=BLOCKED")
        print("FINAL_EXECUTION_AUTHORIZATION=false")
        return 0 if nulls == 0 else 3
    except Exception as exc:
        print("RELEASE_EVIDENCE=FAILED")
        print(f"REASON={type(exc).__name__}: {exc}")
        print("No release authorization was changed.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
