"""Strict, source-aware market-data ingestion for the AURELIA research plane.

This module does not fetch data, infer market volume, repair malformed OHLC,
or authorize trading. It parses broker CSVs and Deriv ticks_history responses
into the repository's canonical StrategyBar contract while preserving an
integrity report. A dataset with any blocking defect is quarantined.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from research.labs.deterministic_intraday_strategies import StrategyBar

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
ORDER_SUBMISSION_PERMITTED = False


class MarketDataIngestionError(ValueError):
    """Raised for unsupported, unbound or malformed market-data input."""


@dataclass(frozen=True)
class IngestionIssue:
    row_number: int | None
    code: str
    detail: str


@dataclass(frozen=True)
class IngestionAudit:
    schema: str
    source_type: str
    symbol: str
    asset_class: str
    granularity_seconds: int
    source_sha256: str
    canonical_data_sha256: str | None
    rows_seen: int
    bars_emitted: int
    tick_count: int
    out_of_order_count: int
    duplicate_timestamp_count: int
    gap_count: int
    maximum_gap_seconds: int
    volume_kind: str
    timestamp_basis: str
    status: str
    issue_codes: tuple[str, ...]
    issues: tuple[IngestionIssue, ...]
    capital_authority_granted: bool = False
    order_submission_permitted: bool = False
    live_execution: str = "BLOCKED"


@dataclass(frozen=True)
class IngestionResult:
    bars: tuple[StrategyBar, ...]
    audit: IngestionAudit
    tick_counts_by_bar: tuple[int, ...]

    @property
    def eligible_for_research(self) -> bool:
        return self.audit.status == "PASS" and bool(self.bars)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_data_hash(
    bars: Sequence[StrategyBar],
    tick_counts: Sequence[int] = (),
) -> str:
    payload = {
        "bars": [
            {
                "timestamp_utc": bar.timestamp_utc,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": bar.volume,
            }
            for bar in bars
        ],
        "tick_counts": list(tick_counts),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return _sha256(raw.encode("utf-8"))


def _validate_scope(symbol: str, asset_class: str, granularity_seconds: int) -> None:
    if not isinstance(symbol, str) or not symbol.strip() or len(symbol.strip()) > 64:
        raise MarketDataIngestionError("MARKET_DATA_SYMBOL_INVALID")
    if asset_class not in {"financial", "synthetic"}:
        raise MarketDataIngestionError("MARKET_DATA_ASSET_CLASS_INVALID")
    if (
        isinstance(granularity_seconds, bool)
        or not isinstance(granularity_seconds, int)
        or granularity_seconds <= 0
    ):
        raise MarketDataIngestionError("MARKET_DATA_GRANULARITY_INVALID")


def _parse_epoch(value: Any) -> datetime:
    if isinstance(value, bool):
        raise MarketDataIngestionError("MARKET_DATA_EPOCH_INVALID")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MarketDataIngestionError("MARKET_DATA_EPOCH_INVALID") from exc
    if not math.isfinite(number) or number <= 0 or not number.is_integer():
        raise MarketDataIngestionError("MARKET_DATA_EPOCH_INVALID")
    try:
        return datetime.fromtimestamp(int(number), tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise MarketDataIngestionError("MARKET_DATA_EPOCH_OUT_OF_RANGE") from exc


def _parse_timestamp(value: Any, source_timezone: str | None) -> tuple[datetime, str]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise MarketDataIngestionError("MARKET_DATA_TIMESTAMP_INVALID") from exc
    else:
        raise MarketDataIngestionError("MARKET_DATA_TIMESTAMP_INVALID")

    if parsed.tzinfo is not None and parsed.utcoffset() is not None:
        return parsed.astimezone(timezone.utc), "EXPLICIT_OFFSET_OR_UTC"

    if not source_timezone:
        raise MarketDataIngestionError("NAIVE_TIMESTAMP_REQUIRES_SOURCE_TIMEZONE")
    try:
        zone = ZoneInfo(source_timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise MarketDataIngestionError("SOURCE_TIMEZONE_NOT_IANA") from exc

    local_zero = parsed.replace(tzinfo=zone, fold=0)
    local_one = parsed.replace(tzinfo=zone, fold=1)
    round_trip = local_zero.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
    if round_trip != parsed:
        raise MarketDataIngestionError("NONEXISTENT_LOCAL_TIMESTAMP_DST")
    if local_zero.utcoffset() != local_one.utcoffset():
        raise MarketDataIngestionError("AMBIGUOUS_LOCAL_TIMESTAMP_DST_REQUIRES_EXPLICIT_OFFSET")
    return local_zero.astimezone(timezone.utc), "IANA_SOURCE_TIMEZONE_CONVERTED"


def _number(value: Any, field: str, *, required: bool = True) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise MarketDataIngestionError(f"{field.upper()}_MISSING")
        return None
    if isinstance(value, bool):
        raise MarketDataIngestionError(f"{field.upper()}_INVALID")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MarketDataIngestionError(f"{field.upper()}_INVALID") from exc
    if not math.isfinite(number):
        raise MarketDataIngestionError(f"{field.upper()}_NONFINITE")
    if required and number <= 0:
        raise MarketDataIngestionError(f"{field.upper()}_MUST_BE_POSITIVE")
    if not required and number < 0:
        raise MarketDataIngestionError(f"{field.upper()}_MUST_NOT_BE_NEGATIVE")
    return number


def _make_bar(
    timestamp: datetime,
    row: dict[str, Any],
    *,
    volume_field: str | None = None,
) -> StrategyBar:
    o = _number(row.get("open"), "open")
    h = _number(row.get("high"), "high")
    low = _number(row.get("low"), "low")
    close = _number(row.get("close"), "close")
    volume = _number(row.get(volume_field), "volume", required=False) if volume_field else None
    assert o is not None and h is not None and low is not None and close is not None
    if h < max(o, low, close):
        raise MarketDataIngestionError("OHLC_HIGH_INCONSISTENT")
    if low > min(o, h, close):
        raise MarketDataIngestionError("OHLC_LOW_INCONSISTENT")
    return StrategyBar(
        timestamp_utc=timestamp.isoformat().replace("+00:00", "Z"),
        open=o, high=h, low=low, close=close, volume=volume,
    )


def _finish(
    *,
    bars: Sequence[StrategyBar],
    tick_counts: Sequence[int],
    rows_seen: int,
    tick_count: int,
    source_raw: bytes,
    source_type: str,
    symbol: str,
    asset_class: str,
    granularity_seconds: int,
    issues: Sequence[IngestionIssue],
    out_of_order_count: int,
    duplicate_count: int,
    volume_kind: str,
    timestamp_basis: str,
) -> IngestionResult:
    ordered = sorted(bars, key=lambda bar: datetime.fromisoformat(bar.timestamp_utc.replace("Z", "+00:00")))
    gaps: list[int] = []
    previous: datetime | None = None
    for bar in ordered:
        stamp = datetime.fromisoformat(bar.timestamp_utc.replace("Z", "+00:00"))
        if previous is not None:
            delta = int((stamp - previous).total_seconds())
            if delta > granularity_seconds:
                gaps.append(delta)
        previous = stamp
    codes = tuple(sorted({issue.code for issue in issues}))
    status = "PASS" if not issues and ordered else "QUARANTINED"
    bars_hash = _canonical_data_hash(ordered, tick_counts) if ordered else None
    audit = IngestionAudit(
        schema="aurelia.market_data_ingestion_audit.v1",
        source_type=source_type,
        symbol=symbol,
        asset_class=asset_class,
        granularity_seconds=granularity_seconds,
        source_sha256=_sha256(source_raw),
        canonical_data_sha256=bars_hash,
        rows_seen=rows_seen,
        bars_emitted=len(ordered),
        tick_count=tick_count,
        out_of_order_count=out_of_order_count,
        duplicate_timestamp_count=duplicate_count,
        gap_count=len(gaps),
        maximum_gap_seconds=max(gaps, default=0),
        volume_kind=volume_kind,
        timestamp_basis=timestamp_basis,
        status=status,
        issue_codes=codes,
        issues=tuple(issues),
    )
    return IngestionResult(
        bars=tuple(ordered) if status == "PASS" else (),
        audit=audit,
        tick_counts_by_bar=tuple(tick_counts) if status == "PASS" else (),
    )


def _normalize_headers(headers: Sequence[str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    aliases = {
        "date": "date",
        "time": "time",
        "datetime": "datetime",
        "date_time": "datetime",
        "timestamp": "datetime",
        "timestamp_utc": "datetime",
        "datetime_utc": "datetime",
        "epoch": "epoch",
        "o": "open",
        "open": "open",
        "h": "high",
        "high": "high",
        "l": "low",
        "low": "low",
        "c": "close",
        "close": "close",
        "v": "volume",
        "volume": "volume",
    }
    for header in headers:
        raw = str(header).strip().lower()
        canonical = aliases.get(raw)
        if canonical is None:
            continue
        if canonical in normalized.values() and canonical not in {"date", "time"}:
            raise MarketDataIngestionError(f"DUPLICATE_CANONICAL_COLUMN:{canonical}")
        normalized[raw] = canonical
    return normalized


def ingest_standard_csv(
    path: str | Path,
    *,
    symbol: str,
    asset_class: str,
    granularity_seconds: int,
    source_timezone: str | None = None,
) -> IngestionResult:
    """Parse standard OHLC CSV without silently coercing/drop-repairing rows.

    An optional volume column is retained as source-reported metadata, but its
    existence alone does not mark it verified trading volume. Missing volume
    remains None; synthetic volume is never fabricated.
    """
    _validate_scope(symbol, asset_class, granularity_seconds)
    file_path = Path(path)
    try:
        raw = file_path.read_bytes()
        text = raw.decode("utf-8-sig")
    except OSError as exc:
        raise MarketDataIngestionError("MARKET_DATA_FILE_READ_FAILED") from exc
    except UnicodeDecodeError as exc:
        raise MarketDataIngestionError("MARKET_DATA_CSV_NOT_UTF8") from exc

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise MarketDataIngestionError("MARKET_DATA_CSV_HEADER_MISSING")
    mapping = _normalize_headers(reader.fieldnames)
    canonical_fields = set(mapping.values())
    if not ({"datetime", "epoch"} & canonical_fields) and not {"date", "time"} <= canonical_fields:
        raise MarketDataIngestionError("MARKET_DATA_TIMESTAMP_COLUMNS_MISSING")
    if not {"open", "high", "low", "close"} <= canonical_fields:
        raise MarketDataIngestionError("MARKET_DATA_OHLC_COLUMNS_MISSING")

    bars: list[StrategyBar] = []
    issues: list[IngestionIssue] = []
    rows_seen = 0
    previous: datetime | None = None
    seen: set[datetime] = set()
    timestamp_basis: set[str] = set()
    out_of_order = 0
    duplicates = 0

    for row_number, raw_row in enumerate(reader, start=2):
        rows_seen += 1
        row = {mapping.get(key.strip().lower(), key.strip().lower()): value for key, value in raw_row.items() if key is not None}
        try:
            if "epoch" in row and str(row["epoch"]).strip():
                stamp, basis = _parse_epoch(row["epoch"]), "UNIX_EPOCH_UTC"
            else:
                if "datetime" in row and str(row["datetime"]).strip():
                    raw_stamp = row["datetime"]
                else:
                    raw_stamp = f"{row.get('date', '')} {row.get('time', '')}".strip()
                stamp, basis = _parse_timestamp(raw_stamp, source_timezone)
            timestamp_basis.add(basis)
            bar = _make_bar(stamp, row, volume_field="volume" if "volume" in row else None)
            if previous is not None and stamp < previous:
                out_of_order += 1
                issues.append(IngestionIssue(row_number, "OUT_OF_ORDER_TIMESTAMP", stamp.isoformat()))
            if stamp in seen:
                duplicates += 1
                issues.append(IngestionIssue(row_number, "DUPLICATE_TIMESTAMP", stamp.isoformat()))
            seen.add(stamp)
            previous = stamp
            bars.append(bar)
        except (MarketDataIngestionError, ValueError, TypeError, OverflowError) as exc:
            code = str(exc) if str(exc) else "ROW_INVALID"
            issues.append(IngestionIssue(row_number, code, "row rejected; source bytes preserved by hash"))

    volume_kind = "SOURCE_REPORTED_UNVERIFIED" if "volume" in canonical_fields else "UNAVAILABLE"
    return _finish(
        bars=bars,
        tick_counts=(),
        rows_seen=rows_seen,
        tick_count=0,
        source_raw=raw,
        source_type="STANDARD_OHLC_CSV",
        symbol=symbol,
        asset_class=asset_class,
        granularity_seconds=granularity_seconds,
        issues=issues,
        out_of_order_count=out_of_order,
        duplicate_count=duplicates,
        volume_kind=volume_kind,
        timestamp_basis=";".join(sorted(timestamp_basis)) if timestamp_basis else "UNKNOWN",
    )


def _tick_rows(payload: Any, *, symbol: str) -> tuple[list[tuple[int, float]], str]:
    """Decode canonical Deriv history response or exported quote records."""
    if isinstance(payload, dict):
        echo = payload.get("echo_req")
        if not isinstance(echo, dict):
            raise MarketDataIngestionError("DERIV_ECHO_REQUEST_MISSING")
        requested_symbol = echo.get("ticks_history")
        if requested_symbol != symbol:
            raise MarketDataIngestionError("DERIV_RESPONSE_SYMBOL_BINDING_MISMATCH")
        if isinstance(payload.get("candles"), list):
            raise MarketDataIngestionError("DERIV_CANDLE_PAYLOAD_NOT_TICKS")
        history = payload.get("history")
        if not isinstance(history, dict):
            raise MarketDataIngestionError("DERIV_TICK_HISTORY_MISSING")
        epochs, prices = history.get("times"), history.get("prices")
        if not isinstance(epochs, list) or not isinstance(prices, list) or len(epochs) != len(prices):
            raise MarketDataIngestionError("DERIV_TICK_HISTORY_ARRAYS_INVALID")
        raw_rows = [{"epoch": epoch, "quote": quote} for epoch, quote in zip(epochs, prices)]
        source_type = "DERIV_TICKS_HISTORY_RESPONSE"
    elif isinstance(payload, list):
        raw_rows = payload
        source_type = "DERIV_TICK_EXPORT_RECORDS"
    else:
        raise MarketDataIngestionError("DERIV_TICK_PAYLOAD_SHAPE_UNSUPPORTED")

    ticks: list[tuple[int, float]] = []
    for index, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            raise MarketDataIngestionError(f"DERIV_TICK_ROW_INVALID:{index}")
        if "epoch" in row:
            epoch = int(_parse_epoch(row["epoch"]).timestamp())
        elif "datetime" in row:
            stamp, _ = _parse_timestamp(row["datetime"], None)
            epoch = int(stamp.timestamp())
        elif "timestamp_utc" in row:
            stamp, _ = _parse_timestamp(row["timestamp_utc"], None)
            epoch = int(stamp.timestamp())
        else:
            raise MarketDataIngestionError(f"DERIV_TICK_TIMESTAMP_MISSING:{index}")
        price = _number(row.get("quote", row.get("price", row.get("close"))), "tick_quote")
        assert price is not None
        ticks.append((epoch, price))
    return ticks, source_type


def ingest_deriv_tick_payload(
    payload: Any,
    *,
    symbol: str,
    asset_class: str,
    granularity_seconds: int = 60,
) -> IngestionResult:
    """Resample ordered Deriv ticks to UTC candles; never invent volume.

    The candle timestamp is the UTC interval start (floor-aligned). Tick counts
    are retained separately as a count proxy, not written to the volume field.
    """
    _validate_scope(symbol, asset_class, granularity_seconds)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ticks, source_type = _tick_rows(payload, symbol=symbol)
    issues: list[IngestionIssue] = []
    previous_epoch: int | None = None
    out_of_order = 0
    for index, (epoch, _price) in enumerate(ticks):
        if previous_epoch is not None and epoch < previous_epoch:
            out_of_order += 1
            issues.append(IngestionIssue(index, "OUT_OF_ORDER_TICK", str(epoch)))
        previous_epoch = epoch

    buckets: dict[int, list[float]] = defaultdict(list)
    for epoch, price in ticks:
        bucket = epoch - (epoch % granularity_seconds)
        buckets[bucket].append(price)

    bars: list[StrategyBar] = []
    counts: list[int] = []
    previous_stamp: datetime | None = None
    for epoch in sorted(buckets):
        prices = buckets[epoch]
        stamp = datetime.fromtimestamp(epoch, tz=timezone.utc)
        if previous_stamp is not None and stamp == previous_stamp:
            issues.append(IngestionIssue(None, "DUPLICATE_RESAMPLED_BAR_TIMESTAMP", str(epoch)))
        previous_stamp = stamp
        bars.append(StrategyBar(
            timestamp_utc=stamp.isoformat().replace("+00:00", "Z"),
            open=prices[0], high=max(prices), low=min(prices), close=prices[-1],
            volume=None,
        ))
        counts.append(len(prices))

    return _finish(
        bars=bars,
        tick_counts=counts,
        rows_seen=len(ticks),
        tick_count=len(ticks),
        source_raw=raw,
        source_type=source_type,
        symbol=symbol,
        asset_class=asset_class,
        granularity_seconds=granularity_seconds,
        issues=issues,
        out_of_order_count=out_of_order,
        duplicate_count=0,
        volume_kind="UNAVAILABLE_TICK_COUNT_PROXY_SEPARATE",
        timestamp_basis="UNIX_EPOCH_OR_EXPLICIT_UTC",
    )


def ingest_deriv_json_file(
    path: str | Path,
    *,
    symbol: str,
    asset_class: str,
    granularity_seconds: int = 60,
) -> IngestionResult:
    """Parse JSON file containing Deriv history response or exported tick rows."""
    file_path = Path(path)
    try:
        raw = file_path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarketDataIngestionError("DERIV_JSON_FILE_READ_OR_DECODE_FAILED") from exc

    # Keep the exact file bytes as source provenance by routing through the
    # payload parser, then replacing its source hash with the on-disk hash.
    result = ingest_deriv_tick_payload(
        payload,
        symbol=symbol,
        asset_class=asset_class,
        granularity_seconds=granularity_seconds,
    )
    audit = IngestionAudit(
        **{
            **asdict(result.audit),
            "source_sha256": _sha256(raw),
        }
    )
    return IngestionResult(result.bars, audit, result.tick_counts_by_bar)


def ingest_deriv_candle_payload(
    payload: dict[str, Any],
    *,
    symbol: str,
    asset_class: str,
    granularity_seconds: int,
) -> IngestionResult:
    """Parse Deriv ticks_history candles response without manufacturing volume."""
    _validate_scope(symbol, asset_class, granularity_seconds)
    if not isinstance(payload, dict) or not isinstance(payload.get("echo_req"), dict):
        raise MarketDataIngestionError("DERIV_ECHO_REQUEST_MISSING")
    if payload["echo_req"].get("ticks_history") != symbol:
        raise MarketDataIngestionError("DERIV_RESPONSE_SYMBOL_BINDING_MISMATCH")
    candles = payload.get("candles")
    if not isinstance(candles, list):
        raise MarketDataIngestionError("DERIV_CANDLE_ARRAY_MISSING")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    bars: list[StrategyBar] = []
    issues: list[IngestionIssue] = []
    seen: set[datetime] = set()
    previous: datetime | None = None
    out_of_order = 0
    duplicates = 0
    for index, candle in enumerate(candles):
        try:
            if not isinstance(candle, dict):
                raise MarketDataIngestionError("DERIV_CANDLE_ROW_INVALID")
            stamp = _parse_epoch(candle.get("epoch"))
            bar = _make_bar(stamp, candle)
            if previous is not None and stamp < previous:
                out_of_order += 1
                issues.append(IngestionIssue(index, "OUT_OF_ORDER_TIMESTAMP", stamp.isoformat()))
            if stamp in seen:
                duplicates += 1
                issues.append(IngestionIssue(index, "DUPLICATE_TIMESTAMP", stamp.isoformat()))
            seen.add(stamp)
            previous = stamp
            bars.append(bar)
        except (MarketDataIngestionError, ValueError, TypeError, OverflowError) as exc:
            issues.append(IngestionIssue(index, str(exc), "Deriv candle row rejected"))
    return _finish(
        bars=bars,
        tick_counts=(),
        rows_seen=len(candles),
        tick_count=0,
        source_raw=raw,
        source_type="DERIV_CANDLES_HISTORY_RESPONSE",
        symbol=symbol,
        asset_class=asset_class,
        granularity_seconds=granularity_seconds,
        issues=issues,
        out_of_order_count=out_of_order,
        duplicate_count=duplicates,
        volume_kind="UNAVAILABLE_DERIV_CANDLE_PAYLOAD_HAS_NO_VOLUME",
        timestamp_basis="UNIX_EPOCH_UTC",
    )
