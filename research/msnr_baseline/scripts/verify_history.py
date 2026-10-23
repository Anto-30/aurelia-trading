#!/usr/bin/env python3
"""Independently verify source manifest, SHA-256, OHLC integrity and continuity."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, sys
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any

REQUIRED = ("epoch", "open", "high", "low", "close")

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def utc_epoch(day: date) -> int:
    return int(datetime.combine(day, dtime.min, tzinfo=timezone.utc).timestamp())

def verify(csv_path: Path, manifest_path: Path, output: Path) -> int:
    report: dict[str, Any] = {
        "schema": "atos.deriv_history_verification.v2",
        "csv_path": str(csv_path.resolve()), "manifest_path": str(manifest_path.resolve()),
        "status": "CORRUPTED", "checks": {}, "errors": [],
        "simulator_eligible_under_strict_continuity": False,
    }
    try:
        if not csv_path.is_file() or not manifest_path.is_file():
            raise ValueError("CSV and manifest must both exist as regular files.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "atos.deriv_history_manifest.v2":
            raise ValueError("Unexpected manifest schema; expected atos.deriv_history_manifest.v2.")
        if manifest.get("underlying_symbol") != "R_100":
            raise ValueError("Manifest underlying_symbol must equal R_100.")
        if manifest.get("endpoint") != "wss://api.derivws.com/trading/v1/options/ws/public":
            raise ValueError("Manifest endpoint is not the mandated current public WebSocket endpoint.")
        if manifest.get("authentication") != "none" or manifest.get("account_token_used") is not False:
            raise ValueError("Manifest must prove unauthenticated public data acquisition.")
        response_name = manifest.get("active_symbols_response_file")
        response_hash = manifest.get("active_symbols_response_sha256")
        if response_name != "R_100_active_symbols_response.json" or not isinstance(response_hash, str) or len(response_hash) != 64:
            raise ValueError("Manifest lacks the captured active_symbols response evidence/hash.")
        response_path = manifest_path.parent / response_name
        if not response_path.is_file() or sha256_file(response_path) != response_hash:
            raise ValueError("Captured active_symbols response is missing or its SHA-256 differs from manifest.")
        active_response = json.loads(response_path.read_text(encoding="utf-8"))
        if not isinstance(active_response, dict) or active_response.get("msg_type") != "active_symbols":
            raise ValueError("Captured public source response is not a current active_symbols message.")
        active_rows = active_response.get("active_symbols") if isinstance(active_response, dict) else None
        if not isinstance(active_rows, list):
            raise ValueError("Captured active_symbols evidence has no active_symbols array.")
        matched_rows = [r for r in active_rows if isinstance(r, dict) and r.get("underlying_symbol") == "R_100"]
        if len(matched_rows) != 1 or matched_rows[0] != manifest.get("active_symbol_metadata_row"):
            raise ValueError("Manifest R_100 active-symbol row does not match captured public response.")
        try:
            captured_pip_size = float(matched_rows[0]["pip_size"])
            manifest_pip_size = float(manifest["pip_size_price_from_active_symbols"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("active_symbols.pip_size price-unit evidence is missing or invalid.") from exc
        if not math.isfinite(captured_pip_size) or captured_pip_size <= 0 or captured_pip_size != manifest_pip_size:
            raise ValueError("Captured active_symbols.pip_size price unit does not match manifest.")
        granularity = int(manifest["granularity_seconds"])
        if granularity not in (60, 900):
            raise ValueError("Unsupported interval; only 60s and 900s datasets are in scope.")
        actual_hash = sha256_file(csv_path)
        report["csv_sha256"] = actual_hash
        report["manifest_csv_sha256"] = manifest.get("csv_sha256")
        report["checks"]["csv_sha256_matches_manifest"] = actual_hash == manifest.get("csv_sha256")
        report["checks"]["manifest_declared_endpoint_current"] = True
        if not report["checks"]["csv_sha256_matches_manifest"]:
            raise ValueError("CSV SHA-256 differs from manifest; data file or evidence was modified.")
        start_epoch = utc_epoch(date.fromisoformat(manifest["start_date_utc_inclusive"]))
        end_exclusive = int(manifest["range_end_exclusive_epoch"])
        declared_end_exclusive = utc_epoch(date.fromisoformat(manifest["end_date_utc_inclusive"]) + timedelta(days=1))
        if end_exclusive != declared_end_exclusive:
            raise ValueError("Manifest range_end_exclusive_epoch disagrees with inclusive UTC end date.")
        expected_rows = (end_exclusive - start_epoch) // granularity
        previous: int | None = None
        count = 0
        duplicates = 0
        nonincreasing = 0
        gaps_over_threshold = 0
        nonstandard_diffs = 0
        max_diff = 0
        ohlc_ok = True
        first_epoch = None
        last_epoch = None
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or any(c not in reader.fieldnames for c in REQUIRED):
                raise ValueError(f"CSV missing required columns {REQUIRED}; got {reader.fieldnames}")
            for line_no, row in enumerate(reader, start=2):
                try:
                    epoch_float = float(row["epoch"])
                    epoch = int(epoch_float)
                    op, hi, lo, cl = (float(row[k]) for k in ("open", "high", "low", "close"))
                except (TypeError, ValueError, KeyError, OverflowError) as exc:
                    raise ValueError(f"Invalid numeric value at CSV line {line_no}.") from exc
                if not math.isfinite(epoch_float) or epoch_float != epoch or not all(math.isfinite(v) and v > 0 for v in (op, hi, lo, cl)):
                    raise ValueError(f"Non-finite/non-positive price or invalid timestamp at line {line_no}.")
                if hi < max(op, cl) or lo > min(op, cl) or hi < lo:
                    ohlc_ok = False
                if epoch % granularity != 0:
                    raise ValueError(f"Epoch is not aligned to interval at CSV line {line_no}: {epoch}.")
                if epoch < start_epoch or epoch >= end_exclusive:
                    raise ValueError(f"Timestamp outside requested range at CSV line {line_no}: {epoch}.")
                if first_epoch is None: first_epoch = epoch
                last_epoch = epoch
                if previous is not None:
                    diff = epoch - previous
                    if diff <= 0: nonincreasing += 1
                    if diff == 0: duplicates += 1
                    if diff != granularity: nonstandard_diffs += 1
                    # Treat a gap as missing time beyond the expected bar interval;
                    # the user's threshold is >120 seconds of excess time, regardless
                    # of whether the expected candle spacing is 60s or 900s.
                    if diff > granularity + 120: gaps_over_threshold += 1
                    max_diff = max(max_diff, diff)
                previous = epoch
                count += 1
        report.update({"row_count": count, "expected_row_count": expected_rows,
                       "first_epoch": first_epoch, "last_epoch": last_epoch,
                       "first_utc": datetime.fromtimestamp(first_epoch, timezone.utc).isoformat() if first_epoch is not None else None,
                       "last_utc": datetime.fromtimestamp(last_epoch, timezone.utc).isoformat() if last_epoch is not None else None,
                       "gap_summary": {"expected_interval_seconds": granularity,
                                       "nonstandard_interval_count": nonstandard_diffs,
                                       "gaps_exceeding_120_seconds_beyond_expected_interval": gaps_over_threshold,
                                       "largest_observed_interval_seconds": max_diff}})
        report["checks"].update({
            "ohlc_consistent": ohlc_ok,
            "row_count_matches_requested_interval": count == expected_rows,
            "first_epoch_matches_requested_start": first_epoch == start_epoch,
            "last_epoch_matches_requested_last_bar": last_epoch == end_exclusive - granularity,
            "strictly_increasing_no_duplicates": nonincreasing == 0 and duplicates == 0,
            "exact_sequential_continuity": nonstandard_diffs == 0,
            "no_gap_exceeding_120_seconds_beyond_expected_interval": gaps_over_threshold == 0,
        })
        checks = report["checks"]
        fatal_checks = ("ohlc_consistent", "row_count_matches_requested_interval", "first_epoch_matches_requested_start",
                        "last_epoch_matches_requested_last_bar", "strictly_increasing_no_duplicates", "exact_sequential_continuity")
        if not all(checks[k] for k in fatal_checks):
            report["status"] = "INCOMPLETE_OR_CORRUPTED"
            report["errors"].append("One or more strict integrity/continuity checks failed; no interpolation or forward-fill is allowed.")
        else:
            report["status"] = "VERIFIED_CONTIGUOUS"
            report["simulator_eligible_under_strict_continuity"] = True
        report["source_note"] = "Endpoint/provenance is asserted by manifest, not cryptographically signed by Deriv; inspect request evidence and current official schema independently."
        report["manifest_sha256"] = sha256_file(manifest_path)
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"VERIFICATION STATUS: {report['status']}")
    return 0 if report["status"] == "VERIFIED_CONTIGUOUS" else 2

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try: return verify(args.csv, args.manifest, args.output)
    except OSError as exc:
        print(f"VERIFY FAILED CLOSED: {exc}", file=sys.stderr); return 2

if __name__ == "__main__": raise SystemExit(main())
