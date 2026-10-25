#!/usr/bin/env python3
"""Exact timestamp and OHLC reconciliation for a supplied MT5 export."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

FIELDS = ("epoch", "open", "high", "low", "close")
OHLC_FIELDS = ("open", "high", "low", "close")
EXPECTED_ROWS = 1440
GRANULARITY_SECONDS = 60


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_integer(value: str, field: str) -> int:
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"INVALID_INTEGER:{field}") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"NON_INTEGER:{field}")
    return int(number)


def parse_decimal(value: str, field: str) -> Decimal:
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"INVALID_DECIMAL:{field}") from exc
    if not number.is_finite():
        raise ValueError(f"NONFINITE_DECIMAL:{field}")
    return number


def load_bars(path: Path, label: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}_FILE_MISSING:{path}")
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{label}_CSV_HEADER_MISSING")
        missing = sorted(set(FIELDS) - set(reader.fieldnames))
        if missing:
            raise ValueError(f"{label}_CSV_REQUIRED_COLUMNS_MISSING:{','.join(missing)}")
        for line_number, row in enumerate(reader, start=2):
            normalized = {field: str(row[field]).strip() for field in FIELDS}
            if any(value == "" for value in normalized.values()):
                raise ValueError(f"{label}_CSV_EMPTY_FIELD:line={line_number}")
            normalized["epoch"] = str(parse_integer(normalized["epoch"], "epoch"))
            for field in OHLC_FIELDS:
                parse_decimal(normalized[field], field)
            rows.append(normalized)

    epochs = [int(row["epoch"]) for row in rows]
    counts = Counter(epochs)
    duplicates = sorted(epoch for epoch, count in counts.items() if count > 1)
    return rows, {
        "row_count": len(rows),
        "duplicate_epoch_count": len(duplicates),
        "duplicate_epoch_sample": duplicates[:20],
        "first_epoch": min(epochs) if epochs else None,
        "last_epoch": max(epochs) if epochs else None,
    }


def reconcile(api_csv: Path, mt5_csv: Path, mt5_symbol: str,
              manifest_path: Path, raw_jsonl_path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "BLOCKED",
        "gate": "MT5_API_EQUIVALENCE",
        "created_at_utc": utc_now(),
        "api_csv_path": str(api_csv),
        "mt5_csv_path": str(mt5_csv),
        "mt5_symbol_documented": mt5_symbol,
        "required_matched_candles": EXPECTED_ROWS,
        "required_granularity_seconds": GRANULARITY_SECONDS,
        "numeric_tolerance": "0.0",
        "discrepancies": [],
    }

    try:
        if not manifest_path.is_file():
            raise FileNotFoundError(f"API_MANIFEST_MISSING:{manifest_path}")
        if not raw_jsonl_path.is_file():
            raise FileNotFoundError(f"RAW_API_JSONL_MISSING:{raw_jsonl_path}")
        if not api_csv.is_file():
            raise FileNotFoundError(f"API_CSV_MISSING:{api_csv}")
        if not mt5_csv.is_file():
            raise FileNotFoundError(f"MT5_EXPORT_MISSING:{mt5_csv}")

        report["api_csv_sha256"] = sha256_file(api_csv)
        report["mt5_csv_sha256"] = sha256_file(mt5_csv)
        report["api_raw_jsonl_sha256"] = sha256_file(raw_jsonl_path)
        report["api_manifest_sha256"] = sha256_file(manifest_path)

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report["api_manifest_status"] = manifest.get("status")
        report["api_manifest_continuity"] = manifest.get("continuity_status")
        report["api_manifest_recorded_csv_sha256"] = manifest.get("verified_csv_sha256")
        report["api_manifest_recorded_raw_sha256"] = manifest.get("raw_jsonl_sha256")

        if manifest.get("status") != "VERIFIED" or manifest.get("continuity_status") != "VERIFIED":
            raise ValueError("API_DATASET_NOT_VERIFIED_BY_MANIFEST")
        if manifest.get("verified_csv_sha256") != report["api_csv_sha256"]:
            raise ValueError("API_CSV_SHA256_DOES_NOT_MATCH_MANIFEST")
        if manifest.get("raw_jsonl_sha256") != report["api_raw_jsonl_sha256"]:
            raise ValueError("RAW_JSONL_SHA256_DOES_NOT_MATCH_MANIFEST")
        if manifest.get("symbol") != "R_100" or int(manifest.get("granularity_s", -1)) != 60:
            raise ValueError("API_MANIFEST_SYMBOL_OR_GRANULARITY_MISMATCH")

        api_rows, api_summary = load_bars(api_csv, "API")
        mt5_rows, mt5_summary = load_bars(mt5_csv, "MT5")
        report["api_csv_summary"] = api_summary
        report["mt5_csv_summary"] = mt5_summary

        if api_summary["duplicate_epoch_count"]:
            report["discrepancies"].append({
                "code": "DUPLICATE_API_EPOCHS",
                "count": api_summary["duplicate_epoch_count"],
                "sample_epochs": api_summary["duplicate_epoch_sample"],
            })
        if mt5_summary["duplicate_epoch_count"]:
            report["discrepancies"].append({
                "code": "DUPLICATE_MT5_EPOCHS",
                "count": mt5_summary["duplicate_epoch_count"],
                "sample_epochs": mt5_summary["duplicate_epoch_sample"],
            })
        if len(mt5_rows) != EXPECTED_ROWS:
            report["discrepancies"].append({
                "code": "MT5_ROW_COUNT_MISMATCH",
                "expected": EXPECTED_ROWS,
                "actual": len(mt5_rows),
            })

        api_by_epoch = {int(row["epoch"]): row for row in api_rows}
        mt5_by_epoch = {int(row["epoch"]): row for row in mt5_rows}
        mt5_epochs = sorted(mt5_by_epoch)
        if not mt5_epochs:
            report["discrepancies"].append({"code": "MT5_DATA_EMPTY"})
            return report

        window_start = mt5_epochs[0]
        window_end = mt5_epochs[-1]
        expected_window_epochs = list(range(window_start, window_end + 1, GRANULARITY_SECONDS))
        report["comparison_window"] = {
            "start_epoch_inclusive": window_start,
            "start_utc": datetime.fromtimestamp(window_start, timezone.utc).isoformat(),
            "end_epoch_inclusive": window_end,
            "end_utc": datetime.fromtimestamp(window_end, timezone.utc).isoformat(),
            "expected_window_rows_from_bounds": len(expected_window_epochs),
            "mt5_rows_within_window": len(mt5_epochs),
        }

        if mt5_epochs != expected_window_epochs:
            epoch_set = set(mt5_epochs)
            expected_set = set(expected_window_epochs)
            report["discrepancies"].append({
                "code": "MT5_TIMESTAMP_CONTINUITY_MISMATCH",
                "missing_epochs": len(expected_set - epoch_set),
                "missing_epoch_sample": sorted(expected_set - epoch_set)[:20],
                "unexpected_epochs": len(epoch_set - expected_set),
                "unexpected_epoch_sample": sorted(epoch_set - expected_set)[:20],
            })
        if len(expected_window_epochs) != EXPECTED_ROWS:
            report["discrepancies"].append({
                "code": "MT5_WINDOW_NOT_EXACTLY_1440_MINUTES",
                "expected": EXPECTED_ROWS,
                "actual_from_bounds": len(expected_window_epochs),
            })

        api_window_epochs = sorted(
            epoch for epoch in api_by_epoch if window_start <= epoch <= window_end
        )
        api_window_set = set(api_window_epochs)
        mt5_epoch_set = set(mt5_epochs)
        missing_in_api = sorted(mt5_epoch_set - api_window_set)
        extra_in_api = sorted(api_window_set - mt5_epoch_set)
        missing_in_mt5 = sorted(api_window_set - mt5_epoch_set)
        extra_in_mt5 = sorted(mt5_epoch_set - api_window_set)

        if missing_in_api:
            report["discrepancies"].append({
                "code": "MT5_EPOCH_MISSING_FROM_API_WINDOW",
                "count": len(missing_in_api),
                "sample_epochs": missing_in_api[:20],
            })
        if missing_in_mt5:
            report["discrepancies"].append({
                "code": "API_EPOCH_MISSING_FROM_MT5",
                "count": len(missing_in_mt5),
                "sample_epochs": missing_in_mt5[:20],
            })
        if extra_in_api:
            report["discrepancies"].append({
                "code": "EXTRA_API_EPOCHS_IN_COMPARISON_WINDOW",
                "count": len(extra_in_api),
                "sample_epochs": extra_in_api[:20],
            })
        if extra_in_mt5:
            report["discrepancies"].append({
                "code": "EXTRA_MT5_EPOCHS_IN_COMPARISON_WINDOW",
                "count": len(extra_in_mt5),
                "sample_epochs": extra_in_mt5[:20],
            })

        common = sorted(api_window_set & mt5_epoch_set)
        report["matched_timestamp_count"] = len(common)
        ohlc_mismatches: list[dict[str, Any]] = []
        for epoch in common:
            api_bar = api_by_epoch[epoch]
            mt5_bar = mt5_by_epoch[epoch]
            for field in OHLC_FIELDS:
                api_value = parse_decimal(api_bar[field], field)
                mt5_value = parse_decimal(mt5_bar[field], field)
                if api_value != mt5_value:
                    ohlc_mismatches.append({
                        "epoch": epoch,
                        "field": field,
                        "api_value": str(api_value),
                        "mt5_value": str(mt5_value),
                        "absolute_difference": str(abs(api_value - mt5_value)),
                    })
                    if len(ohlc_mismatches) >= 100:
                        break
            if len(ohlc_mismatches) >= 100:
                break

        if ohlc_mismatches:
            report["discrepancies"].append({
                "code": "OHLC_EXACT_EQUALITY_FAILED",
                "tolerance": "0.0",
                "mismatch_sample_limit": 100,
                "mismatch_sample": ohlc_mismatches,
            })

        if not report["discrepancies"] and len(common) == EXPECTED_ROWS:
            report["status"] = "VERIFIED"
            report["matched_candles"] = len(common)
            report["numeric_tolerance"] = "0.0"
            report["equivalence_claim_scope"] = "Only this 1,440-candle window and the supplied, documented MT5 symbol"
            print("RECONCILIATION_RESULT=VERIFIED")
            print("MATCHED_CANDLES=" + str(len(common)))
            print("OHLC_TOLERANCE=0.0")
        else:
            report["status"] = "FAILED"
            print("RECONCILIATION_RESULT=FAILED")
            print("DISCREPANCY_COUNT=" + str(len(report["discrepancies"])))

    except Exception as exc:
        report["status"] = "BLOCKED"
        report["discrepancies"].append({
            "code": type(exc).__name__,
            "reason": str(exc)[:1000],
        })
        print("RECONCILIATION_RESULT=BLOCKED")
        print("BLOCK_REASON=" + str(exc)[:1000])

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-csv", type=Path,
                        default=Path("data/r100_historical_2022-2024/R_100_60s_verified.csv"))
    parser.add_argument("--api-manifest", type=Path,
                        default=Path("data/r100_historical_2022-2024/verification_manifest.json"))
    parser.add_argument("--raw-jsonl", type=Path,
                        default=Path("data/r100_historical_2022-2024/r100_candles_raw.jsonl"))
    parser.add_argument("--mt5-csv", type=Path, default=Path("mt5_bars.csv"))
    parser.add_argument("--mt5-symbol", required=True,
                        help="Documented symbol name shown by the MT5 terminal; not assumed equivalent")
    parser.add_argument("--output", type=Path, default=Path("data/mt5_api_equivalence.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = reconcile(args.api_csv, args.mt5_csv, args.mt5_symbol,
                       args.api_manifest, args.raw_jsonl)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("REPORT_PATH=" + str(args.output))
    print("REPORT_SHA256=" + sha256_file(args.output))
    return 0 if report["status"] == "VERIFIED" else 2


if __name__ == "__main__":
    sys.exit(main())
