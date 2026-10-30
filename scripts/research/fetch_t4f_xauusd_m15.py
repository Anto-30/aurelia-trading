"""Retrieve an exact Deriv XAUUSD 15-minute public history sample.

This script never authenticates an account or submits transactions. It writes a
raw-research CSV plus a provenance/quality sidecar. Session gaps are reported,
not filled or silently approved.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.labs.deriv_public_data import DerivPublicDataClient

OUTPUT = Path("artifacts/t4f-369-xauusd-m15")
COUNT = 5000
GRANULARITY_SECONDS = 900
EXACT_CODES = {"FRXXAUUSD", "XAUUSD"}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    client = DerivPublicDataClient(timeout_seconds=30)
    symbols = client.active_symbols()

    matches = []
    for item in symbols:
        symbol = str(item.get("symbol") or "").strip()
        underlying = str(item.get("underlying_symbol") or "").strip()
        if symbol.upper() in EXACT_CODES or underlying.upper() in EXACT_CODES:
            matches.append({
                "symbol": symbol,
                "underlying_symbol": underlying,
                "display_name": item.get("display_name"),
                "market": item.get("market"),
                "market_display_name": item.get("market_display_name"),
                "exchange_is_open": item.get("exchange_is_open"),
            })

    exact_codes = sorted({
        code
        for item in matches
        for code in (item["symbol"], item["underlying_symbol"])
        if code and code.upper() in EXACT_CODES
    })
    selected = "frxXAUUSD" if "frxXAUUSD" in exact_codes else (
        "XAUUSD" if "XAUUSD" in exact_codes else None
    )
    if selected is None:
        write_json(OUTPUT / "symbol-discovery.json", {
            "status": "XAUUSD_SYMBOL_NOT_FOUND",
            "active_symbol_count": len(symbols),
            "exact_matches": matches,
            "candidate_gold_symbols": [
                {
                    "symbol": item.get("symbol"),
                    "underlying_symbol": item.get("underlying_symbol"),
                    "display_name": item.get("display_name"),
                }
                for item in symbols
                if "gold" in str(item.get("display_name", "")).lower()
                or "xau" in str(item.get("symbol", "")).lower()
            ],
            "action": "No substitute instrument selected.",
        })
        print(json.dumps({
            "status": "XAUUSD_SYMBOL_NOT_FOUND",
            "active_symbol_count": len(symbols),
            "candidate_count": len(matches),
        }, sort_keys=True))
        return 0

    batch = client.fetch_candles(
        symbol=selected,
        granularity_seconds=GRANULARITY_SECONDS,
        count=COUNT,
    )
    frame = batch.frame.copy()
    if frame.empty:
        raise RuntimeError("XAUUSD_CANDLE_HISTORY_EMPTY")

    numeric = frame.loc[:, ["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    values = numeric.to_numpy(dtype="float64")
    if not np.isfinite(values).all():
        raise RuntimeError("XAUUSD_CANDLES_CONTAIN_NONFINITE_OHLC")
    o = numeric["open"].to_numpy(dtype="float64")
    h = numeric["high"].to_numpy(dtype="float64")
    lo = numeric["low"].to_numpy(dtype="float64")
    cl = numeric["close"].to_numpy(dtype="float64")
    if np.any(values <= 0):
        raise RuntimeError("XAUUSD_CANDLES_CONTAIN_NONPOSITIVE_OHLC")
    if np.any(h < np.maximum.reduce([o, cl, lo])) or np.any(lo > np.minimum.reduce([o, cl, h])):
        raise RuntimeError("XAUUSD_OHLC_RELATIONSHIP_INVALID")
    if not frame.index.is_monotonic_increasing:
        raise RuntimeError("XAUUSD_CANDLES_NOT_CHRONOLOGICALLY_ORDERED")
    if frame.index.has_duplicates:
        raise RuntimeError("XAUUSD_CANDLES_HAVE_DUPLICATE_TIMESTAMPS")

    deltas = np.diff(frame.index.asi8) if len(frame) > 1 else np.array([], dtype="int64")
    expected_ns = GRANULARITY_SECONDS * 1_000_000_000
    missing_bars = int(sum(max(0, int(delta // expected_ns) - 1) for delta in deltas if delta > expected_ns))
    exact_continuity = bool(np.all(deltas == expected_ns)) if len(deltas) else True

    bar_end_epochs = frame.index.asi8 // 1_000_000_000 + GRANULARITY_SECONDS
    is_closed = bar_end_epochs <= batch.server_time_epoch
    output_frame = frame.copy()
    output_frame.insert(0, "timestamp_utc", output_frame.index.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    output_frame["is_closed_at_server_time"] = is_closed
    csv_bytes = output_frame.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")
    normalized_hash = hashlib.sha256(csv_bytes).hexdigest()
    csv_path = OUTPUT / "xauusd_m15_5000.csv"
    csv_path.write_bytes(csv_bytes)

    metadata = {
        "status": "RAW_CANDLES_RETRIEVED",
        "strategy_validation_status": "NOT_VALIDATED",
        "symbol": batch.symbol,
        "granularity_seconds": batch.granularity_seconds,
        "requested_count": COUNT,
        "returned_count": int(len(frame)),
        "first_candle_utc": frame.index[0].isoformat(),
        "last_candle_utc": frame.index[-1].isoformat(),
        "retrieved_at_utc": batch.retrieved_at_utc,
        "server_time_epoch": batch.server_time_epoch,
        "last_bar_closed": batch.last_bar_closed,
        "closed_bar_count": int(is_closed.sum()),
        "unclosed_bar_count": int((~is_closed).sum()),
        "raw_response_sha256": batch.raw_response_sha256,
        "normalized_csv_sha256": normalized_hash,
        "duplicate_timestamps": int(frame.index.duplicated(keep=False).sum()),
        "timestamps_monotonic_increasing": bool(frame.index.is_monotonic_increasing),
        "missing_expected_bars_between_rows": missing_bars,
        "exact_15m_continuity": exact_continuity,
        "continuity_status": "NO_GAPS_IN_RETURNED_WINDOW" if exact_continuity else "GAPS_REQUIRE_SESSION_CALENDAR_REVIEW",
        "ohlc_validation": "PASS",
        "session_calendar_validation": "NOT_PERFORMED",
        "forward_fill_or_repair": False,
        "source_endpoint": batch.endpoint,
        "authentication": batch.authentication,
        "capital_authority_granted": False,
        "order_submission_permitted": False,
        "dataset_path": str(csv_path),
        "dataset_use": "RAW_RESEARCH_ONLY_PENDING_SESSION_CALENDAR_AND_FULL_DATA_QUALITY_VALIDATION",
    }
    write_json(OUTPUT / "metadata.json", metadata)
    print(json.dumps({
        "status": metadata["status"],
        "symbol": batch.symbol,
        "returned_count": len(frame),
        "closed_bar_count": metadata["closed_bar_count"],
        "last_bar_closed": batch.last_bar_closed,
        "missing_expected_bars": missing_bars,
        "continuity_status": metadata["continuity_status"],
        "raw_response_sha256": batch.raw_response_sha256,
        "normalized_csv_sha256": normalized_hash,
        "dataset_path": str(csv_path),
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
