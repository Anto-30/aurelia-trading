#!/usr/bin/env python3
"""Fail-closed exact 1-minute OHLC reconciliation for MT5 and Deriv API CSVs.

Input columns: API requires epoch,open,high,low,close. MT5 accepts those same
columns or Date,Time,Open,High,Low,Close. Naive MT5 times require the documented
IANA server timezone. A pass covers only the supplied interval; it does not
validate another historical period or contract economics.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FIELDS = ("open", "high", "low", "close")
UTC = timezone.utc

class ReconcileError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message); self.code = code; self.details = details or {}

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def get_epoch(raw: dict[str, str], headers: dict[str, str], path: Path, row_num: int, tz_name: str | None) -> int:
    if "epoch" in headers:
        val = raw[headers["epoch"]].strip()
        try:
            d = Decimal(val)
            if not d.is_finite() or d != d.to_integral_value(): raise ValueError
            return int(d)
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ReconcileError("INVALID_EPOCH", f"{path.name} row {row_num}: invalid epoch {val!r}.") from e
    if "date" not in headers or "time" not in headers:
        raise ReconcileError("MISSING_TIME_COLUMNS", f"{path.name}: require epoch or Date+Time columns.")
    value = f"{raw[headers['date']].strip()} {raw[headers['time']].strip()}"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        dt = None
        for fmt in ("%Y.%m.%d %H:%M:%S.%f", "%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M"):
            try: dt = datetime.strptime(value, fmt); break
            except ValueError: pass
        if dt is None: raise ReconcileError("INVALID_DATETIME", f"{path.name} row {row_num}: unsupported Date+Time {value!r}.")
    if dt.tzinfo is not None and dt.utcoffset() is not None:
        return int(dt.astimezone(UTC).timestamp())
    if not tz_name: raise ReconcileError("TIMEZONE_REQUIRED", "MT5 Date+Time is naive; provide its documented IANA server timezone with --mt5-timezone.")
    try: zone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as e: raise ReconcileError("INVALID_TIMEZONE", f"Unknown IANA timezone {tz_name!r}.") from e
    a0, a1 = dt.replace(tzinfo=zone, fold=0), dt.replace(tzinfo=zone, fold=1)
    v0 = a0.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == dt
    v1 = a1.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == dt
    if not v0 and not v1: raise ReconcileError("NONEXISTENT_LOCAL_TIME", f"{path.name} row {row_num}: local time {dt} does not exist in {tz_name}.")
    if v0 and v1 and a0.utcoffset() != a1.utcoffset(): raise ReconcileError("AMBIGUOUS_LOCAL_TIME", f"{path.name} row {row_num}: local time {dt} is ambiguous in {tz_name}; offset evidence is required.")
    return int((a0 if v0 else a1).astimezone(UTC).timestamp())

def load(path: Path, tz_name: str | None) -> list[dict[str, Any]]:
    if not path.is_file(): raise ReconcileError("INPUT_FILE_MISSING", f"Input file not found: {path}")
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames: raise ReconcileError("MISSING_HEADER", f"{path.name}: missing CSV header.")
            headers = {}
            for col in reader.fieldnames:
                key = col.strip().lstrip("\ufeff").lower().replace(" ", "_")
                if key in headers: raise ReconcileError("DUPLICATE_COLUMNS", f"{path.name}: duplicate column {key!r}.")
                headers[key] = col
            if not all(k in headers for k in FIELDS): raise ReconcileError("MISSING_OHLC_COLUMNS", f"{path.name}: requires open/high/low/close.")
            if "epoch" not in headers and not ("date" in headers and "time" in headers): raise ReconcileError("MISSING_TIME_COLUMNS", f"{path.name}: require epoch or Date+Time.")
            rows, seen, previous = [], set(), None
            for n, raw in enumerate(reader, 2):
                if not raw or all(v is None or not v.strip() for v in raw.values()): raise ReconcileError("BLANK_ROW", f"{path.name} row {n}: blank row is prohibited.")
                epoch = get_epoch(raw, headers, path, n, tz_name)
                if epoch in seen: raise ReconcileError("DUPLICATE_EPOCH", f"{path.name} row {n}: duplicate epoch {epoch}.")
                if previous is not None and epoch <= previous: raise ReconcileError("NON_MONOTONIC_EPOCHS", f"{path.name} row {n}: epochs are not strictly ascending.")
                seen.add(epoch); previous = epoch
                row = {"epoch": epoch}
                for key in FIELDS:
                    try: val = Decimal(raw[headers[key]].strip())
                    except (InvalidOperation, ValueError, AttributeError) as e: raise ReconcileError("INVALID_PRICE", f"{path.name} row {n}: invalid {key} price.") from e
                    if not val.is_finite() or val <= 0: raise ReconcileError("INVALID_PRICE", f"{path.name} row {n}: {key} must be finite and positive.")
                    row[key] = val
                o,h,l,c = (row[k] for k in FIELDS)
                if h < max(o,c) or l > min(o,c) or h < l: raise ReconcileError("OHLC_INVARIANT", f"{path.name} row {n}, epoch {epoch}: invalid OHLC.")
                rows.append(row)
            if not rows: raise ReconcileError("EMPTY_DATA", f"{path.name}: no candle records.")
            return rows
    except OSError as e: raise ReconcileError("FILE_ERROR", f"Cannot read {path}: {e}") from e

def compare(api: list[dict[str, Any]], mt5: list[dict[str, Any]], start: int, end: int) -> dict[str, Any]:
    if start < 0 or end <= start or start % 60 or end % 60: raise ReconcileError("INVALID_WINDOW", "Requested [start,end) must be positive and minute-aligned UTC epochs.")
    expected = list(range(start, end, 60))
    for label, rows in (("API", api), ("MT5", mt5)):
        epochs = [r["epoch"] for r in rows]
        if epochs != expected:
            missing = sorted(set(expected)-set(epochs)); extra = sorted(set(epochs)-set(expected))
            code = "API_EPOCH_SET_MISMATCH" if label == "API" else "EPOCH_SET_MISMATCH"
            raise ReconcileError(code, f"{label} dataset does not exactly cover the requested window.", {"expected_rows":len(expected),"actual_rows":len(rows),"missing_count":len(missing),"extra_count":len(extra),"missing_epochs_sample":missing[:20],"extra_epochs_sample":extra[:20]})
    diffs=[]
    for a,m in zip(api, mt5, strict=True):
        for field in FIELDS:
            if a[field] != m[field]:
                diffs.append({"epoch":a["epoch"],"field":field,"api_value":format(a[field],"f"),"mt5_value":format(m[field],"f")})
                if len(diffs)>=100: break
        if len(diffs)>=100: break
    if diffs: raise ReconcileError("OHLC_MISMATCH", "OHLC values differ; tolerance is exactly zero.", {"mismatches_sample":diffs,"mismatch_count_lower_bound":len(diffs),"price_tolerance":"0.0"})
    return {"status":"PASS_EXACT_OHLC_EQUIVALENCE","expected_rows":len(expected),"matched_rows":len(expected),"first_epoch":expected[0],"last_epoch":expected[-1],"missing_candles":0,"extra_candles":0,"ohlc_mismatches":0,"price_tolerance":"0.0","does_not_authorize_full_history":True,"scope":"only the supplied 1-minute OHLC window"}

def main(argv: list[str] | None = None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api",required=True,type=Path); ap.add_argument("--mt5",required=True,type=Path)
    ap.add_argument("--api-symbol",required=True); ap.add_argument("--mt5-symbol",required=True)
    ap.add_argument("--start-epoch",required=True,type=int); ap.add_argument("--end-epoch-exclusive",required=True,type=int)
    ap.add_argument("--mt5-timezone",default=None,help="Documented IANA timezone for naive MT5 Date+Time; never guessed.")
    ap.add_argument("--output",required=True,type=Path); args=ap.parse_args(argv)
    if args.output.exists(): print(json.dumps({"status":"BLOCKED_OUTPUT_EXISTS","reason_code":"OUTPUT_EXISTS"})); return 2
    if not args.api_symbol.strip() or not args.mt5_symbol.strip(): print(json.dumps({"status":"BLOCKED_INPUT_VALIDATION","reason_code":"SYMBOL_REQUIRED"})); return 2
    report={"schema":"aurelia.mt5_api_candle_equivalence.v1","api_symbol":args.api_symbol,"mt5_symbol":args.mt5_symbol,"style":"candles","granularity_seconds":60,"start_epoch_inclusive":args.start_epoch,"end_epoch_exclusive":args.end_epoch_exclusive,"mt5_timezone":args.mt5_timezone,"api_file":str(args.api),"mt5_file":str(args.mt5),"price_tolerance":"0.0","credentials_used":False,"live_orders_submitted":False,"warning":"A pass covers only this sample and does not establish historical-source provenance for 2022-2024."}
    code=0
    try:
        report["api_sha256"]=digest(args.api); report["mt5_sha256"]=digest(args.mt5)
        report.update(compare(load(args.api,None),load(args.mt5,args.mt5_timezone),args.start_epoch,args.end_epoch_exclusive))
    except ReconcileError as e:
        report.update({"status":"BLOCKED_OHLC_MISMATCH" if e.code=="OHLC_MISMATCH" else "BLOCKED_COVERAGE_MISMATCH" if e.code in ("EPOCH_SET_MISMATCH","API_EPOCH_SET_MISMATCH") else "BLOCKED_INPUT_VALIDATION","reason_code":e.code,"message":str(e),"details":e.details}); code=1
    except Exception as e:
        report.update({"status":"BLOCKED_UNEXPECTED_ERROR","reason_code":"UNEXPECTED_ERROR","message":f"{type(e).__name__}: {e}"}); code=2
    report["generated_utc"]=datetime.now(UTC).isoformat()
    try:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x",encoding="utf-8") as f: json.dump(report,f,indent=2,sort_keys=True); f.write("\n")
    except OSError as e: print(json.dumps({"status":"BLOCKED_REPORT_WRITE","reason_code":"REPORT_WRITE_FAILED","message":str(e)})); return 2
    print(json.dumps(report,indent=2,sort_keys=True)); return code

if __name__=="__main__": sys.exit(main())
