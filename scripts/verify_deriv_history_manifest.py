#!/usr/bin/env python3
"""Verify a Deriv candle CSV and its companion SHA-256 coverage manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def canonical_sha256(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_history(csv_path: str | Path, manifest_path: str | Path | None = None) -> dict:
    csv_file = Path(csv_path)
    manifest_file = Path(manifest_path) if manifest_path else csv_file.with_suffix(csv_file.suffix + ".manifest.json")
    if not csv_file.is_file() or not manifest_file.is_file():
        raise ValueError("CSV or companion manifest is missing")
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("manifest is unreadable JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != "atos.deriv_history_manifest.v1":
        raise ValueError("unsupported or malformed manifest schema")
    stated_hash = manifest.get("manifest_sha256")
    unsigned_manifest = {key: val for key, val in manifest.items() if key != "manifest_sha256"}
    if not isinstance(stated_hash, str) or canonical_sha256(unsigned_manifest) != stated_hash:
        raise ValueError("manifest SHA-256 mismatch")
    csv_hash = hashlib.sha256(csv_file.read_bytes()).hexdigest()
    if csv_hash != manifest.get("data_sha256"):
        raise ValueError("CSV SHA-256 mismatch")

    required = {"timestamp", "epoch", "open", "high", "low", "close", "volume"}
    try:
        frame = pd.read_csv(csv_file)
    except Exception as exc:
        raise ValueError("CSV cannot be parsed") from exc
    if not required.issubset(frame.columns):
        raise ValueError(f"CSV missing columns: {sorted(required - set(frame.columns))}")
    if frame.empty:
        raise ValueError("CSV is empty")
    granularity = manifest.get("granularity_seconds")
    start, end = manifest.get("requested_start_epoch"), manifest.get("requested_end_epoch")
    if granularity not in (60, 900) or not isinstance(start, int) or not isinstance(end, int) or start >= end:
        raise ValueError("manifest time range or candle granularity is invalid")
    if start % granularity or end % granularity:
        raise ValueError("manifest timestamps are not aligned to candle boundaries")
    expected = list(range(start, end + 1, granularity))
    epochs = pd.to_numeric(frame["epoch"], errors="raise").astype("int64")
    if epochs.duplicated().any():
        raise ValueError("CSV has duplicate candle epochs")
    if epochs.tolist() != expected:
        raise ValueError("CSV does not exactly cover manifest time range")
    if len(frame) != manifest.get("bar_count"):
        raise ValueError("CSV bar_count differs from manifest")
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    timestamp_epochs = (timestamps.astype("int64") // 1_000_000_000).astype("int64")
    if not timestamp_epochs.equals(epochs.reset_index(drop=True)):
        raise ValueError("timestamp and epoch columns disagree")
    prices = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("OHLC values must be finite positive numbers")
    ohlc = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="raise")
    if (ohlc["high"] < ohlc[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("OHLC high constraint failed")
    if (ohlc["low"] > ohlc[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("OHLC low constraint failed")
    if manifest.get("coverage_complete") is not True or manifest.get("missing_intervals") != 0 or manifest.get("duplicate_timestamps") != 0:
        raise ValueError("manifest does not certify gap-free, duplicate-free coverage")
    if manifest.get("volume_semantics") != "unavailable_not_fabricated" or frame["volume"].notna().any():
        raise ValueError("volume is expected to remain missing, not fabricated")
    if manifest.get("first_returned_epoch") != start or manifest.get("last_returned_epoch") != end:
        raise ValueError("manifest returned boundaries do not match the request")
    return {
        "schema": "atos.deriv_history_verification.v1",
        "verified": True,
        "symbol": manifest.get("symbol"),
        "granularity_seconds": granularity,
        "bar_count": len(frame),
        "coverage_complete": True,
        "data_sha256": csv_hash,
        "manifest_sha256": stated_hash,
        "source_commit": manifest.get("source_commit"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        report = verify_history(args.csv, args.manifest)
    except Exception as exc:
        print("DERIV_HISTORY_MANIFEST=INVALID")
        print(f"REASON={type(exc).__name__}: {exc}")
        return 2
    print("DERIV_HISTORY_MANIFEST=VERIFIED")
    print(f"SYMBOL={report['symbol']}")
    print(f"BAR_COUNT={report['bar_count']}")
    print(f"DATA_SHA256={report['data_sha256']}")
    print(f"MANIFEST_SHA256={report['manifest_sha256']}")
    print("COVERAGE_COMPLETE=true")
    print("VOLUME_FABRICATED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
