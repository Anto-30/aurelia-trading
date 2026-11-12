from __future__ import annotations

"""Import a Deriv MT5 tick export into auditable UTC M1/M15 research bars.

This tool does not authenticate, connect to a broker, trade, or certify that
MT5 prices are equivalent to Deriv Options/Multipliers prices. The operator
must explicitly confirm the exact Market Watch symbol mapping and source
timezone. Gaps are never interpolated.
"""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_START = 1666310400       # 2022-10-21T00:00:00Z
DEFAULT_END = 1729468800         # 2024-10-21T00:00:00Z
TIME_FORMATS = (
    "%Y.%m.%d %H:%M:%S.%f",
    "%Y.%m.%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _parse_timestamp(
    row: dict[str, str],
    timezone_name: str | None,
    previous_utc: datetime | None = None,
) -> tuple[datetime, bool]:
    value = (row.get("time") or "").strip()
    date_part = (row.get("date") or "").strip()
    time_part = (row.get("time") or "").strip()
    if date_part and time_part and not re.search(r"\d{4}[-.]\d{2}[-.]\d{2}", value):
        value = date_part + " " + time_part

    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        for fmt in TIME_FORMATS:
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        raise ValueError("MT5_TIMESTAMP_INVALID")
    if parsed.tzinfo is None:
        if not timezone_name:
            raise ValueError("SOURCE_TIMEZONE_REQUIRED_FOR_NAIVE_MT5_TIMESTAMPS")
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("SOURCE_TIMEZONE_UNKNOWN") from exc
        first = parsed.replace(tzinfo=zone, fold=0)
        second = parsed.replace(tzinfo=zone, fold=1)
        first_round_trip = (
            first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        )
        second_round_trip = (
            second.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        )
        valid_candidates = [
            candidate
            for candidate, round_trip in (
                (first, first_round_trip),
                (second, second_round_trip),
            )
            if round_trip == parsed
        ]
        if not valid_candidates:
            raise ValueError("SOURCE_TIMEZONE_NONEXISTENT_LOCAL_TIME")
        if (
            len(valid_candidates) > 1
            and valid_candidates[0].utcoffset() != valid_candidates[1].utcoffset()
        ):
            if previous_utc is None:
                raise ValueError("SOURCE_TIMEZONE_AMBIGUOUS_LOCAL_TIME_UNRESOLVED")
            previous_utc = previous_utc.astimezone(timezone.utc)
            monotonic_candidates = [
                candidate for candidate in valid_candidates
                if candidate.astimezone(timezone.utc) >= previous_utc
            ]
            if not monotonic_candidates:
                raise ValueError("SOURCE_TIMEZONE_AMBIGUOUS_LOCAL_TIME_ORDER_UNRESOLVED")
            parsed = min(
                monotonic_candidates,
                key=lambda candidate: candidate.astimezone(timezone.utc),
            )
            resolved_ambiguous = True
        else:
            parsed = valid_candidates[0]
            resolved_ambiguous = False
    else:
        resolved_ambiguous = False
    return parsed.astimezone(timezone.utc), resolved_ambiguous


def _read_rows(path: Path) -> tuple[list[dict[str, str]], str]:
    raw = path.read_bytes()
    if not raw:
        raise ValueError("MT5_EXPORT_EMPTY")
    text = raw.decode("utf-8-sig")
    for delimiter in (",", ";", "\t"):
        reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
        headers = {
            str(name or "").strip().lower()
            for name in (reader.fieldnames or [])
        }
        has_time = "time" in headers or {"date", "time"}.issubset(headers)
        if has_time and "bid" in headers and "ask" in headers:
            rows = []
            for row in reader:
                rows.append({
                    str(key or "").strip().lower(): str(value or "").strip()
                    for key, value in row.items()
                })
            return rows, delimiter
    raise ValueError("MT5_TICK_EXPORT_HEADERS_UNSUPPORTED")


def _decimal(value: str, code: str) -> Decimal:
    try:
        result = Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(code) from exc
    if not result.is_finite() or result <= 0:
        raise ValueError(code)
    return result


def _bar_rows(ticks: list[dict[str, Any]], seconds: int) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for tick in ticks:
        bucket = (tick["epoch"] // seconds) * seconds
        grouped.setdefault(bucket, []).append(tick)
    result = []
    for epoch in sorted(grouped):
        items = grouped[epoch]
        bids = [item["bid"] for item in items]
        spreads = [item["ask"] - item["bid"] for item in items]
        result.append({
            "epoch": epoch,
            "timestamp_utc": datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
            "open": float(bids[0]),
            "high": float(max(bids)),
            "low": float(min(bids)),
            "close": float(bids[-1]),
            "tick_count": len(items),
            "mean_spread": float(sum(spreads) / Decimal(len(spreads))),
            "max_spread": float(max(spreads)),
        })
    return result


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> str:
    fields = [
        "epoch", "timestamp_utc", "open", "high", "low", "close",
        "tick_count", "mean_spread", "max_spread",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return sha256_bytes(path.read_bytes())


def import_mt5_ticks(
    *,
    input_path: Path,
    output_dir: Path,
    source_symbol: str,
    canonical_symbol: str = "R_100",
    source_timezone: str | None,
    mapping_confirmed: bool,
    start_epoch: int = DEFAULT_START,
    end_epoch: int = DEFAULT_END,
) -> dict[str, Any]:
    if not input_path.is_file():
        raise ValueError("MT5_EXPORT_FILE_NOT_FOUND")
    if not re.fullmatch(r"[A-Za-z0-9_. -]{2,64}", source_symbol):
        raise ValueError("SOURCE_SYMBOL_INVALID")
    if not re.fullmatch(r"[A-Z0-9_]{2,30}", canonical_symbol):
        raise ValueError("CANONICAL_SYMBOL_INVALID")
    if type(start_epoch) is not int or type(end_epoch) is not int or end_epoch <= start_epoch:
        raise ValueError("HISTORICAL_WINDOW_INVALID")
    if start_epoch % 60 or end_epoch % 60:
        raise ValueError("HISTORICAL_WINDOW_MUST_ALIGN_TO_MINUTE")
    if source_timezone:
        try:
            ZoneInfo(source_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("SOURCE_TIMEZONE_UNKNOWN") from exc

    raw = input_path.read_bytes()
    rows, delimiter = _read_rows(input_path)
    ticks: list[dict[str, Any]] = []
    out_of_order = 0
    out_of_range_rows = 0
    previous_utc: datetime | None = None
    ambiguous_local_times_resolved = 0
    for row_number, row in enumerate(rows, start=2):
        prior_utc = previous_utc
        timestamp, ambiguous_resolved = _parse_timestamp(
            row, source_timezone, previous_utc=prior_utc
        )
        if prior_utc is not None and timestamp < prior_utc:
            out_of_order += 1
        previous_utc = timestamp
        if ambiguous_resolved:
            ambiguous_local_times_resolved += 1
        epoch_ms = int(round(timestamp.timestamp() * 1000))
        epoch = epoch_ms // 1000
        bid = _decimal(row.get("bid", ""), "MT5_BID_INVALID")
        ask = _decimal(row.get("ask", ""), "MT5_ASK_INVALID")
        if ask < bid:
            raise ValueError("MT5_ASK_BELOW_BID")
        if start_epoch <= epoch < end_epoch:
            ticks.append({
                "epoch": epoch,
                "epoch_ms": epoch_ms,
                "bid": bid,
                "ask": ask,
                "source_row": row_number,
            })
        else:
            out_of_range_rows += 1
    if not ticks:
        raise ValueError("NO_TICKS_IN_REQUESTED_WINDOW")
    ticks.sort(key=lambda item: (item["epoch_ms"], item["source_row"]))

    m1 = _bar_rows(ticks, 60)
    m15 = _bar_rows(ticks, 900)
    expected_m1 = list(range(start_epoch, end_epoch, 60))
    expected_m15 = list(range(start_epoch, end_epoch, 900))
    observed_m1 = {row["epoch"] for row in m1}
    observed_m15 = {row["epoch"] for row in m15}
    missing_m1 = [epoch for epoch in expected_m1 if epoch not in observed_m1]
    missing_m15 = [epoch for epoch in expected_m15 if epoch not in observed_m15]
    same_timestamp_tick_excess = len(ticks) - len({tick["epoch_ms"] for tick in ticks})
    output_dir.mkdir(parents=True, exist_ok=True)
    m1_sha = _write_csv(output_dir / "R100_M1.csv", m1)
    m15_sha = _write_csv(output_dir / "R100_M15.csv", m15)
    mapping_ok = mapping_confirmed is True
    coverage_ok = not missing_m1 and not missing_m15
    ordering_ok = out_of_order == 0
    status = (
        "RESEARCH_IMPORT_READY"
        if mapping_ok and coverage_ok and ordering_ok
        else "BLOCKED_IMPORT_QUALITY_OR_MAPPING"
    )
    manifest = {
        "schema": "aurelia.deriv_mt5_tick_import.v1",
        "status": status,
        "source_platform": "Deriv MT5",
        "source_product_family": "MT5_EXPORT_UNVERIFIED_PRODUCT",
        "price_basis": "BID",
        "spread_basis": "ASK_MINUS_BID",
        "source_symbol": source_symbol,
        "canonical_symbol": canonical_symbol,
        "symbol_mapping_operator_confirmed": mapping_ok,
        "source_timezone": source_timezone,
        "source_timezone_required_for_naive_timestamps": True,
        "source_sha256": sha256_bytes(raw),
        "source_delimiter": repr(delimiter),
        "imported_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_start_epoch": start_epoch,
        "requested_end_epoch": end_epoch,
        "actual_first_epoch": min(tick["epoch"] for tick in ticks),
        "actual_last_epoch": max(tick["epoch"] for tick in ticks),
        "tick_count": len(ticks),
        "m1_bar_count": len(m1),
        "m15_bar_count": len(m15),
        "m1_sha256": m1_sha,
        "m15_sha256": m15_sha,
        "m1_gap_count": len(missing_m1),
        "m1_first_missing_epochs": missing_m1[:20],
        "m15_gap_count": len(missing_m15),
        "m15_first_missing_epochs": missing_m15[:20],
        "out_of_order_count": out_of_order,
        "ambiguous_local_times_resolved_by_monotonic_sequence": ambiguous_local_times_resolved,
        "same_timestamp_tick_excess_count": same_timestamp_tick_excess,
        "rows_outside_requested_window_excluded": out_of_range_rows,
        "gap_interpolation_performed": False,
        "feed_equivalence_to_deriv_options_verified": False,
        "strategy_validation_eligible": False,
        "account_credentials_used": False,
        "broker_transactions": False,
        "order_submission_permitted": False,
        "capital_authority_granted": False,
        "blockers": [
            name for name, passed in (
                ("SYMBOL_MAPPING_NOT_OPERATOR_CONFIRMED", mapping_ok),
                ("M1_OR_M15_GAPS_PRESENT", coverage_ok),
                ("SOURCE_TICKS_OUT_OF_ORDER", ordering_ok),
            ) if not passed
        ],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    manifest["manifest_sha256"] = sha256_bytes(manifest_path.read_bytes())
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-symbol", required=True)
    parser.add_argument("--canonical-symbol", default="R_100")
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument("--confirm-symbol-mapping", action="store_true")
    parser.add_argument("--start-epoch", type=int, default=DEFAULT_START)
    parser.add_argument("--end-epoch", type=int, default=DEFAULT_END)
    args = parser.parse_args()
    result = import_mt5_ticks(
        input_path=args.input,
        output_dir=args.output_dir,
        source_symbol=args.source_symbol,
        canonical_symbol=args.canonical_symbol,
        source_timezone=args.source_timezone,
        mapping_confirmed=args.confirm_symbol_mapping,
        start_epoch=args.start_epoch,
        end_epoch=args.end_epoch,
    )
    print(json.dumps({
        "status": result["status"],
        "source_symbol": result["source_symbol"],
        "canonical_symbol": result["canonical_symbol"],
        "symbol_mapping_operator_confirmed": result["symbol_mapping_operator_confirmed"],
        "tick_count": result["tick_count"],
        "m1_bar_count": result["m1_bar_count"],
        "m15_bar_count": result["m15_bar_count"],
        "m1_gap_count": result["m1_gap_count"],
        "m15_gap_count": result["m15_gap_count"],
        "out_of_order_count": result["out_of_order_count"],
        "feed_equivalence_to_deriv_options_verified": False,
        "strategy_validation_eligible": False,
        "order_submission_permitted": False,
        "blockers": result["blockers"],
    }, sort_keys=True))
    return 0 if result["status"] == "RESEARCH_IMPORT_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
