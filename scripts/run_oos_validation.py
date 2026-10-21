#!/usr/bin/env python3
"""Capture verified Deriv candles and score a supplied, cost-evidenced OOS trade ledger.

This is research-only. Public market-data requests require an app ID, not an account
token. The script never authorizes an account and has no buy/sell/order code. It will
not invent strategy trades or costs: without a four-model trade ledger AND a hash-
bound cost-evidence file, it records data capture and exits with OOS_METRICS=NOT_COMPUTED.
The repository's final OOS protocol reserves the newest 3 calendar months; shorter
windows are exploratory and cannot satisfy that final-OOS gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from research.atos_validation.deriv_data import DerivHistoryClient, persist_history
from research.atos_validation.four_model_backtest import (
    evaluate,
    evaluate_fold_metrics,
    load_trade_ledger,
)
from scripts.verify_deriv_history_manifest import verify_history

COST_SCHEMA = "aurelia.execution_economics_evidence.v1"


def resolve_oos_start(end_epoch: int, granularity: int, *, oos_days: int | None = None,
                     oos_months: int = 3) -> tuple[int, int | None, bool]:
    """Return an aligned start, calendar-month count, and final-OOS eligibility.

    Explicit day windows are exploratory. Final OOS uses calendar months rather
    than approximating three calendar months as a fixed 90-day duration.
    """
    if granularity not in (60, 900):
        raise ValueError("granularity must be 60 or 900 seconds")
    if oos_days is not None:
        if not 1 <= oos_days <= 365:
            raise ValueError("oos_days must be in 1..365")
        return end_epoch - oos_days * 86400, None, False
    if not 1 <= oos_months <= 12:
        raise ValueError("oos_months must be in 1..12")
    end_stamp = pd.Timestamp(end_epoch, unit="s", tz="UTC")
    start_stamp = end_stamp - pd.DateOffset(months=oos_months)
    start = int(start_stamp.timestamp())
    start -= start % granularity
    return start, oos_months, oos_months >= 3


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=5,
        )
        value = result.stdout.strip()
        return value if len(value) == 40 else "LOCAL_UNPINNED"
    except Exception:
        return os.getenv("GITHUB_SHA", "").strip() or "LOCAL_UNPINNED"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        n = float(value)
        return n if math.isfinite(n) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _load_cost_evidence(path: Path, *, symbol: str, start_epoch: int, end_epoch: int,
                        data_sha256: str, ledger_sha256: str) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cost-evidence file is unreadable JSON") from exc
    required = {
        "schema", "symbol", "oos_start_epoch", "oos_end_epoch", "data_sha256",
        "trade_ledger_sha256", "cost_basis", "cost_source_file",
        "cost_source_sha256", "cost_method", "independent_review_status",
    }
    if not isinstance(doc, dict) or not required.issubset(doc):
        raise ValueError(f"cost evidence missing fields: {sorted(required - set(doc if isinstance(doc, dict) else {}))}")
    if doc["schema"] != COST_SCHEMA:
        raise ValueError("unsupported cost-evidence schema")
    expected = {
        "symbol": symbol,
        "oos_start_epoch": start_epoch,
        "oos_end_epoch": end_epoch,
        "data_sha256": data_sha256,
        "trade_ledger_sha256": ledger_sha256,
    }
    for key, value in expected.items():
        if doc.get(key) != value:
            raise ValueError(f"cost evidence {key} does not match this OOS run")
    if doc["cost_basis"] not in {"verified_deriv_quote_snapshot", "preregistered_conservative_scenario"}:
        raise ValueError("cost_basis must identify verified quotes or a preregistered conservative scenario")
    if not isinstance(doc["cost_method"], str) or not doc["cost_method"].strip():
        raise ValueError("cost_method must explain how per-trade cost_r was derived")
    if doc["independent_review_status"] not in {"PENDING", "APPROVED", "REJECTED"}:
        raise ValueError("independent_review_status must be PENDING, APPROVED, or REJECTED")
    source_ref = Path(str(doc["cost_source_file"]))
    if not source_ref.is_absolute():
        source_ref = path.parent / source_ref
    if not source_ref.is_file():
        raise ValueError("referenced cost source file is missing")
    actual_source_hash = _sha256(source_ref)
    if actual_source_hash != doc["cost_source_sha256"]:
        raise ValueError("cost source SHA-256 mismatch")
    # This verifies linkage/integrity, not the economic realism or authenticity of
    # the source. That still requires independent review of the source material.
    return {
        **doc,
        "cost_source_path_resolved": str(source_ref),
        "cost_source_sha256_verified": actual_source_hash,
        "cost_source_authenticity_independently_verified": False,
    }


def _metric_report(ledger_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trades = load_trade_ledger(ledger_path)
    aggregate = evaluate(ledger_path)
    fold_metrics = evaluate_fold_metrics(ledger_path)
    summaries: list[dict[str, Any]] = []
    for model in aggregate["model"].tolist():
        model_trades = trades.loc[trades["strategy"] == model].sort_values("timestamp")
        net = model_trades["net_r"].to_numpy(dtype=float)
        n = int(len(net))
        mean = float(np.mean(net))
        se = float(np.std(net, ddof=1) / math.sqrt(n)) if n >= 2 else None
        row = aggregate.loc[aggregate["model"] == model].iloc[0].to_dict()
        summaries.append({
            **row,
            "n_trades": n,
            "expectancy_95_ci_low_iid": mean - 1.96 * se if se is not None else None,
            "expectancy_95_ci_high_iid": mean + 1.96 * se if se is not None else None,
            "ci_note": "IID-normal descriptive interval; not adjusted for dependence, overlap, or multiple testing",
        })
    folds: list[dict[str, Any]] = fold_metrics.to_dict(orient="records")
    return _json_safe(summaries), _json_safe(folds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-id", default=os.getenv("DERIV_APP_ID"),
                        help="numeric Deriv app ID; market-data-only, no account token")
    parser.add_argument("--symbol", default="R_100")
    window = parser.add_mutually_exclusive_group()
    window.add_argument("--oos-days", type=int, default=None,
                        help="fixed-day exploratory window; does not satisfy the calendar-month final-OOS protocol")
    window.add_argument("--oos-months", type=int, default=3,
                        help="calendar-month window; final OOS requires at least 3 calendar months")
    parser.add_argument("--granularity", type=int, choices=(60, 900), default=60)
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/oos"))
    parser.add_argument("--trades-csv", type=Path,
                        help="audited ledger from the frozen strategy simulator, with four matched models")
    parser.add_argument("--cost-evidence", type=Path,
                        help="JSON evidence file binding cost source hash, dataset hash, and ledger hash")
    args = parser.parse_args()

    if not args.app_id or not str(args.app_id).isdigit():
        print("OOS_CAPTURE=FAILED")
        print("REASON=Set DERIV_APP_ID or pass --app-id; do not provide an account token.")
        return 2
    if args.oos_days is not None and not 1 <= args.oos_days <= 365:
        print("OOS_CAPTURE=FAILED")
        print("REASON=--oos-days must be in 1..365")
        return 2
    if args.oos_days is None and not 1 <= args.oos_months <= 12:
        print("OOS_CAPTURE=FAILED")
        print("REASON=--oos-months must be in 1..12")
        return 2
    if not args.symbol or len(args.symbol) > 30 or not args.symbol.replace("_", "").isalnum():
        print("OOS_CAPTURE=FAILED")
        print("REASON=invalid symbol")
        return 2
    if (args.trades_csv is None) != (args.cost_evidence is None):
        print("OOS_METRICS=NOT_COMPUTED")
        print("REASON=--trades-csv and --cost-evidence must be supplied together")
        return 2

    commit = _git_commit()
    os.environ.setdefault("GITHUB_SHA", commit)
    now = int(time.time())
    # Stop at the most recent fully closed candle boundary.
    end_epoch = (now // args.granularity) * args.granularity - args.granularity
    start_epoch, calendar_months, final_oos_protocol_satisfied = resolve_oos_start(
        end_epoch, args.granularity, oos_days=args.oos_days, oos_months=args.oos_months,
    )
    oos_days_actual = (end_epoch - start_epoch) / 86400.0
    args.out_dir.mkdir(parents=True, exist_ok=True)
    window_label = f"{calendar_months}months" if calendar_months is not None else f"{args.oos_days}days"
    csv_path = args.out_dir / f"{args.symbol}_{args.granularity}s_oos_{window_label}.csv"
    manifest_path = csv_path.with_suffix(csv_path.suffix + ".manifest.json")
    run_path = args.out_dir / "oos_validation_report.json"

    print("DERIV_OOS_CAPTURE=STARTED")
    print(f"SYMBOL={args.symbol}")
    print(f"GRANULARITY_SECONDS={args.granularity}")
    print(f"OOS_DAYS_ACTUAL={oos_days_actual:.3f}")
    if calendar_months is not None:
        print(f"OOS_CALENDAR_MONTHS={calendar_months}")
    else:
        print("OOS_WINDOW_TYPE=EXPLORATORY_FIXED_DAYS")
    print(f"START_UTC={datetime.fromtimestamp(start_epoch, timezone.utc).isoformat()}")
    print(f"END_UTC={datetime.fromtimestamp(end_epoch, timezone.utc).isoformat()}")
    print(f"CODE_COMMIT={commit}")
    print("ACCOUNT_AUTHENTICATION=NOT_USED_PUBLIC_MARKET_DATA_ONLY")
    print("ORDERS_SUBMITTED=0")

    try:
        client = DerivHistoryClient(app_id=str(args.app_id))
        bars = client.backfill(
            args.symbol, start_epoch, end_epoch,
            granularity=args.granularity, bars_per_request=4500,
        )
        manifest = persist_history(
            bars, csv_path, symbol=args.symbol, granularity=args.granularity,
            start_epoch=start_epoch, end_epoch=end_epoch,
        )
        verified = verify_history(csv_path, manifest_path)
        if not verified.get("verified"):
            raise ValueError("history manifest verification failed")
    except Exception as exc:
        report = {
            "schema": "aurelia.oos_run.v1", "status": "CAPTURE_FAILED",
            "code_commit": commit, "reason": f"{type(exc).__name__}: {exc}",
            "orders_submitted": 0, "live_authorization": False,
        }
        run_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("DERIV_OOS_CAPTURE=FAILED")
        print(f"REASON={type(exc).__name__}: {exc}")
        return 2

    report: dict[str, Any] = {
        "schema": "aurelia.oos_run.v1",
        "status": "DATA_CAPTURE_VERIFIED_METRICS_NOT_COMPUTED",
        "symbol": args.symbol,
        "granularity_seconds": args.granularity,
        "oos_days_actual": oos_days_actual,
        "oos_calendar_months": calendar_months,
        "oos_start_epoch": start_epoch,
        "oos_end_epoch": end_epoch,
        "oos_start_utc": datetime.fromtimestamp(start_epoch, timezone.utc).isoformat(),
        "oos_end_utc": datetime.fromtimestamp(end_epoch, timezone.utc).isoformat(),
        "bar_count": verified["bar_count"],
        "data_sha256": verified["data_sha256"],
        "manifest_sha256": verified["manifest_sha256"],
        "code_commit": commit,
        "history_csv": str(csv_path),
        "history_manifest": str(manifest_path),
        "strategy_metrics": None,
        "fold_metrics": None,
        "final_three_month_oos_protocol_satisfied": final_oos_protocol_satisfied,
        "cost_source_authenticity_independently_verified": False,
        "final_execution_authorization": False,
        "live_execution": "BLOCKED",
        "orders_submitted": 0,
    }

    print("DERIV_OOS_CAPTURE=VERIFIED")
    print(f"BAR_COUNT={verified['bar_count']}")
    print(f"DATA_SHA256={verified['data_sha256']}")
    print(f"MANIFEST_SHA256={verified['manifest_sha256']}")
    print(f"DATA_PATH={csv_path}")
    print(f"MANIFEST_PATH={manifest_path}")
    if not final_oos_protocol_satisfied:
        print("FINAL_OOS_PROTOCOL=NOT_SATISFIED_EXPLORATORY_DAY_WINDOW_OR_SHORTER_THAN_3_CALENDAR_MONTHS")
    else:
        print("FINAL_OOS_PROTOCOL=CALENDAR_MONTH_WINDOW_ELIGIBLE_PENDING_PROOF_OF_PRECOMMITMENT")

    if args.trades_csv is None or args.cost_evidence is None:
        report["reason"] = (
            "No audited four-model trade ledger and hash-bound cost evidence supplied. "
            "This repository's evaluator does not generate trades; no expectancy, PF, or drawdown is claimed."
        )
        run_path.write_text(json.dumps(_json_safe(report), indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print("OOS_METRICS=NOT_COMPUTED")
        print("REASON=Missing frozen strategy trade ledger and cost evidence; no metrics were fabricated.")
        print("FINAL_EXECUTION_AUTHORIZATION=false")
        print(f"REPORT_PATH={run_path}")
        return 3

    ledger_path = args.trades_csv.resolve()
    cost_path = args.cost_evidence.resolve()
    if not ledger_path.is_file():
        print("OOS_METRICS=NOT_COMPUTED")
        print("REASON=trade ledger file not found")
        return 3
    try:
        ledger = load_trade_ledger(ledger_path)
        stamps = pd.to_datetime(ledger["timestamp"], utc=True, errors="raise")
        if ((stamps.astype("int64") // 1_000_000_000 < start_epoch) |
            (stamps.astype("int64") // 1_000_000_000 > end_epoch)).any():
            raise ValueError("trade timestamps fall outside this sealed OOS interval")
        ledger_hash = _sha256(ledger_path)
        cost_doc = _load_cost_evidence(
            cost_path, symbol=args.symbol, start_epoch=start_epoch, end_epoch=end_epoch,
            data_sha256=verified["data_sha256"], ledger_sha256=ledger_hash,
        )
        model_metrics, fold_metrics = _metric_report(ledger_path)
    except Exception as exc:
        report["status"] = "DATA_CAPTURE_VERIFIED_METRICS_REJECTED"
        report["reason"] = f"{type(exc).__name__}: {exc}"
        run_path.write_text(json.dumps(_json_safe(report), indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print("OOS_METRICS=REJECTED")
        print(f"REASON={type(exc).__name__}: {exc}")
        return 3

    report.update({
        "status": "METRICS_COMPUTED_PENDING_INDEPENDENT_REVIEW",
        "trade_ledger_sha256": ledger_hash,
        "cost_evidence": {
            "cost_basis": cost_doc["cost_basis"],
            "cost_method": cost_doc["cost_method"],
            "cost_source_sha256_verified": cost_doc["cost_source_sha256_verified"],
            "independent_review_status": cost_doc["independent_review_status"],
            "authenticity_independently_verified": False,
        },
        "strategy_metrics": model_metrics,
        "fold_metrics": fold_metrics,
        "final_three_month_oos_protocol_satisfied": final_oos_protocol_satisfied,
        "oos_status": "PENDING_INDEPENDENT_REVIEW",
        "final_execution_authorization": False,
        "live_execution": "BLOCKED",
    })
    run_path.write_text(json.dumps(_json_safe(report), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("OOS_METRICS=COMPUTED_FROM_SUPPLIED_AUDITED_LEDGER")
    print(f"TRADE_LEDGER_SHA256={ledger_hash}")
    for row in model_metrics:
        print(
            f"MODEL={row['model']} N={row['n_trades']} "
            f"NET_EXPECTANCY_R={row['expectancy_r']} PF={row['profit_factor']} "
            f"MAX_DRAWDOWN_R={row['max_drawdown_r']} "
            f"CI95_IID=[{row['expectancy_95_ci_low_iid']},{row['expectancy_95_ci_high_iid']}]"
        )
    print(f"COST_BASIS={cost_doc['cost_basis']}")
    print(f"COST_SOURCE_SHA256={cost_doc['cost_source_sha256_verified']}")
    print(f"INDEPENDENT_REVIEW_STATUS={cost_doc['independent_review_status']}")
    print("COST_SOURCE_AUTHENTICITY_INDEPENDENTLY_VERIFIED=false")
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    print(f"REPORT_PATH={run_path}")
    # Computed metrics are not a release authorization or an independent audit.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
