"""Paginated, read-only retrieval of Deriv XAUUSD M15 history.

Writes raw CSV plus a provenance/quality sidecar. No account auth or trading
methods are used. Time gaps are retained and labelled; no repairs are applied.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.labs.deriv_public_data import DerivPublicDataClient

OUTPUT = Path("artifacts/t4f-369-xauusd-m15")
REQUESTED_COUNT = 5000
GRANULARITY_SECONDS = 900
MAX_PAGES = 12
EXACT_CODES = {"FRXXAUUSD", "XAUUSD"}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def discover_xauusd_symbol(client: DerivPublicDataClient) -> tuple[str | None, list[dict]]:
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
    return selected, symbols


def fetch_history_pages(client: DerivPublicDataClient, symbol: str):
    newest_first = []
    requested_remaining = REQUESTED_COUNT
    end: int | str = "latest"
    page_hashes = []
    exhausted = False

    for page_number in range(1, MAX_PAGES + 1):
        try:
            batch = client.fetch_candles(
                symbol=symbol,
                granularity_seconds=GRANULARITY_SECONDS,
                count=min(5000, requested_remaining),
                end=end,
            )
        except RuntimeError as exc:
            if "DERIV_CANDLE_RESPONSE_EMPTY_OR_INVALID" in str(exc):
                exhausted = True
                break
            raise

        if batch.frame.empty:
            exhausted = True
            break
        if not batch.frame.index.is_monotonic_increasing or batch.frame.index.has_duplicates:
            raise RuntimeError("DERIV_PAGE_TIMESTAMP_ORDER_OR_UNIQUENESS_FAILED")

        newest_first.append(batch)
        page_hashes.append(batch.raw_response_sha256)
        requested_remaining -= len(batch.frame)
        if requested_remaining <= 0:
            break

        oldest_epoch = int(batch.frame.index[0].timestamp())
        next_end = oldest_epoch - 1
        if next_end <= 0 or (isinstance(end, int) and next_end >= end):
            raise RuntimeError("DERIV_HISTORY_PAGINATION_DID_NOT_MOVE_BACKWARD")
        end = next_end

    if not newest_first:
        raise RuntimeError("DERIV_XAUUSD_HISTORY_NOT_RETURNED")

    chronological_batches = list(reversed(newest_first))
    combined = pd.concat([batch.frame for batch in chronological_batches], axis=0)
    if combined.index.has_duplicates:
        raise RuntimeError("DERIV_PAGINATED_HISTORY_OVERLAP_DETECTED")
    if not combined.index.is_monotonic_increasing:
        raise RuntimeError("DERIV_PAGINATED_HISTORY_ORDER_INVALID")

    # The newest page was requested first; its server clock is the freshest.
    latest_batch = newest_first[0]
    combined_hash = hashlib.sha256("".join(page_hashes).encode("ascii")).hexdigest()
    return combined, latest_batch, page_hashes, combined_hash, exhausted


def extract_symbol_schedule(markets: list[dict], symbol: str) -> list[dict]:
    found = []
    for market in markets:
        for submarket in market.get("submarkets", []) or []:
            for item in submarket.get("symbols", []) or []:
                if str(item.get("symbol") or "").lower() == symbol.lower():
                    found.append({
                        "market": market.get("name"),
                        "submarket": submarket.get("name"),
                        "name": item.get("name"),
                        "symbol": item.get("symbol"),
                        "times": item.get("times"),
                        "trading_days": item.get("trading_days"),
                        "events": item.get("events"),
                    })
    return found


def retrieve_session_calendar(client: DerivPublicDataClient, symbol: str,
                              first: pd.Timestamp, last: pd.Timestamp) -> dict:
    dates = pd.date_range(first.date(), last.date(), freq="D")
    records = []
    failures = []
    for session_date in dates:
        date_text = session_date.strftime("%Y-%m-%d")
        try:
            response = client.trading_times(date_text)
            matches = extract_symbol_schedule(response["markets"], symbol)
            records.append({
                "date": date_text,
                "status": "SYMBOL_SCHEDULE_FOUND" if matches else "SYMBOL_SCHEDULE_NOT_FOUND",
                "schedule": matches,
            })
        except Exception as exc:
            failures.append({"date": date_text, "error": type(exc).__name__ + ":" + str(exc)})
            records.append({
                "date": date_text,
                "status": "QUERY_FAILED",
                "schedule": [],
            })
    return {
        "schema": "t4f.deriv.trading_times_calendar.v1",
        "symbol": symbol,
        "requested_dates": len(dates),
        "dates_with_schedule": sum(item["status"] == "SYMBOL_SCHEDULE_FOUND" for item in records),
        "dates_without_schedule": sum(item["status"] == "SYMBOL_SCHEDULE_NOT_FOUND" for item in records),
        "dates_failed": len(failures),
        "status": "COMPLETE" if not failures and all(item["schedule"] for item in records
                                                     if pd.Timestamp(item["date"]).dayofweek < 5) else "INCOMPLETE",
        "calendar_timezone": "PROVIDER_SPEC_NOT_YET_NORMALIZED_TO_UTC",
        "records": records,
        "failures": failures,
        "use_limit": "Schedule evidence only; gap classification requires review of returned trading days, open/close times and dated events.",
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    client = DerivPublicDataClient(timeout_seconds=30)
    selected, symbols = discover_xauusd_symbol(client)

    if selected is None:
        matches = [
            {
                "symbol": item.get("symbol"),
                "underlying_symbol": item.get("underlying_symbol"),
                "display_name": item.get("display_name"),
            }
            for item in symbols
            if "gold" in str(item.get("display_name", "")).lower()
            or "xau" in str(item.get("symbol", "")).lower()
            or "xau" in str(item.get("underlying_symbol", "")).lower()
        ]
        write_json(OUTPUT / "symbol-discovery.json", {
            "status": "XAUUSD_SYMBOL_NOT_FOUND",
            "active_symbol_count": len(symbols),
            "candidate_gold_symbols": matches,
            "action": "No substitute instrument selected.",
        })
        print(json.dumps({
            "status": "XAUUSD_SYMBOL_NOT_FOUND",
            "active_symbol_count": len(symbols),
            "candidate_count": len(matches),
        }, sort_keys=True))
        return 0

    frame, latest_batch, page_hashes, combined_raw_hash, exhausted = fetch_history_pages(client, selected)
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

    deltas_seconds = frame.index.to_series().diff().dt.total_seconds().dropna().to_numpy(dtype="float64")
    non_15m_intervals = int(np.count_nonzero(deltas_seconds != GRANULARITY_SECONDS))
    sub_interval_gaps = int(np.count_nonzero(
        (deltas_seconds > 0) & (deltas_seconds < GRANULARITY_SECONDS)
    ))
    unadjusted_missing_slots = int(sum(
        max(0, int(delta // GRANULARITY_SECONDS) - 1)
        for delta in deltas_seconds if delta > GRANULARITY_SECONDS
    ))
    exact_continuity = bool(np.all(deltas_seconds == GRANULARITY_SECONDS)) if len(deltas_seconds) else True

    session_calendar = retrieve_session_calendar(client, selected, frame.index[0], frame.index[-1])
    calendar_path = OUTPUT / "trading_times_calendar.json"
    write_json(calendar_path, session_calendar)
    calendar_hash = hashlib.sha256(
        calendar_path.read_bytes()
    ).hexdigest()

    bar_start_epochs = np.array([int(stamp.timestamp()) for stamp in frame.index], dtype="int64")
    is_closed = bar_start_epochs + GRANULARITY_SECONDS <= latest_batch.server_time_epoch
    utc_grid_aligned = (bar_start_epochs % GRANULARITY_SECONDS) == 0

    output_frame = frame.copy()
    output_frame.insert(0, "timestamp_utc", output_frame.index.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    output_frame["is_closed_at_server_time"] = is_closed
    output_frame["bar_start_utc_grid_aligned"] = utc_grid_aligned
    csv_bytes = output_frame.to_csv(
        index=False, lineterminator="\n", float_format="%.17g"
    ).encode("utf-8")
    normalized_hash = hashlib.sha256(csv_bytes).hexdigest()
    csv_path = OUTPUT / "xauusd_m15_history.csv"
    csv_path.write_bytes(csv_bytes)

    status = "RAW_CANDLES_RETRIEVED" if len(frame) >= REQUESTED_COUNT else "PARTIAL_RAW_CANDLES_RETRIEVED"
    metadata = {
        "status": status,
        "strategy_validation_status": "NOT_VALIDATED",
        "symbol": selected,
        "granularity_seconds": GRANULARITY_SECONDS,
        "requested_count": REQUESTED_COUNT,
        "returned_count": int(len(frame)),
        "pages_retrieved": len(page_hashes),
        "history_exhausted_before_requested_count": bool(exhausted and len(frame) < REQUESTED_COUNT),
        "first_candle_utc": frame.index[0].isoformat(),
        "last_candle_utc": frame.index[-1].isoformat(),
        "retrieved_at_utc": latest_batch.retrieved_at_utc,
        "server_time_epoch": latest_batch.server_time_epoch,
        "last_bar_closed": bool(is_closed[-1]),
        "closed_bar_count": int(is_closed.sum()),
        "unclosed_bar_count": int((~is_closed).sum()),
        "utc_grid_aligned_count": int(utc_grid_aligned.sum()),
        "utc_grid_unaligned_count": int((~utc_grid_aligned).sum()),
        "raw_page_response_sha256": page_hashes,
        "combined_raw_page_hashes_sha256": combined_raw_hash,
        "normalized_csv_sha256": normalized_hash,
        "duplicate_timestamps": int(frame.index.duplicated(keep=False).sum()),
        "timestamps_monotonic_increasing": bool(frame.index.is_monotonic_increasing),
        "non_15m_intervals": non_15m_intervals,
        "sub_15m_intervals": sub_interval_gaps,
        "unadjusted_missing_15m_slots": unadjusted_missing_slots,
        "exact_15m_continuity": exact_continuity,
        "continuity_status": (
            "NO_GAPS_IN_RETURNED_WINDOW" if exact_continuity
            else "GAPS_REQUIRE_INSTRUMENT_SESSION_CALENDAR_REVIEW"
        ),
        "ohlc_validation": "PASS",
        "session_calendar_validation": "SCHEDULE_RETRIEVED_REQUIRES_GAP_RECONCILIATION",
        "session_calendar_status": session_calendar["status"],
        "session_calendar_dates_requested": session_calendar["requested_dates"],
        "session_calendar_dates_with_schedule": session_calendar["dates_with_schedule"],
        "session_calendar_dates_failed": session_calendar["dates_failed"],
        "session_calendar_sha256": calendar_hash,
        "session_calendar_path": str(calendar_path),
        "forward_fill_or_repair": False,
        "source_endpoint": latest_batch.endpoint,
        "authentication": latest_batch.authentication,
        "capital_authority_granted": False,
        "order_submission_permitted": False,
        "dataset_path": str(csv_path),
        "dataset_use": "RAW_RESEARCH_ONLY_PENDING_SESSION_CALENDAR_AND_FULL_DATA_QUALITY_VALIDATION",
    }
    write_json(OUTPUT / "metadata.json", metadata)
    print(json.dumps({
        "status": status,
        "symbol": selected,
        "requested_count": REQUESTED_COUNT,
        "returned_count": len(frame),
        "pages_retrieved": len(page_hashes),
        "closed_bar_count": metadata["closed_bar_count"],
        "last_bar_closed": metadata["last_bar_closed"],
        "utc_grid_unaligned_count": metadata["utc_grid_unaligned_count"],
        "non_15m_intervals": non_15m_intervals,
        "unadjusted_missing_15m_slots": unadjusted_missing_slots,
        "continuity_status": metadata["continuity_status"],
        "combined_raw_page_hashes_sha256": combined_raw_hash,
        "normalized_csv_sha256": normalized_hash,
        "dataset_path": str(csv_path),
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
