"""Validate and freeze R_100 1m OHLC into immutable 1m/15m snapshots.

A successful manifest seals files actually present on disk. This module never
fabricates missing data, treats absent fields as zero, or mutates the source
file. Timestamp role must be declared because many market APIs timestamp the
start rather than the close of a candle.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False

REQUIRED_COLUMNS = ("datetime", "open", "high", "low", "close")
PRICE_COLUMNS = ("open", "high", "low", "close")
MANIFEST_NAME = "r100_dual_resolution_manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_aware_datetime(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"INVALID_TIMESTAMP:{value!r}") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"TIMESTAMP_MUST_INCLUDE_TIMEZONE:{value!r}")
    return result.astimezone(timezone.utc)


def _normalise_row(row: dict[str, str], *, timestamp_role: str, row_number: int) -> dict[str, Any]:
    missing = [column for column in REQUIRED_COLUMNS if column not in row or row[column] is None]
    if missing:
        raise ValueError(f"MISSING_REQUIRED_COLUMNS:{','.join(missing)}")
    stamp = parse_aware_datetime(row["datetime"])
    if timestamp_role == "open":
        stamp += timedelta(minutes=1)
    elif timestamp_role != "close":
        raise ValueError("timestamp_role must be 'open' or 'close'")
    if stamp.second != 0 or stamp.microsecond != 0:
        raise ValueError(f"TIMESTAMP_NOT_ALIGNED_TO_MINUTE:row={row_number}")

    prices: dict[str, float] = {}
    for column in PRICE_COLUMNS:
        try:
            prices[column] = float(row[column])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"NON_NUMERIC_PRICE:row={row_number}:column={column}") from exc
        if not math.isfinite(prices[column]) or prices[column] <= 0:
            raise ValueError(f"INVALID_PRICE:row={row_number}:column={column}")
    if prices["high"] < max(prices["open"], prices["close"]):
        raise ValueError(f"HIGH_BELOW_OPEN_OR_CLOSE:row={row_number}")
    if prices["low"] > min(prices["open"], prices["close"]):
        raise ValueError(f"LOW_ABOVE_OPEN_OR_CLOSE:row={row_number}")
    if prices["high"] < prices["low"]:
        raise ValueError(f"HIGH_BELOW_LOW:row={row_number}")

    return {
        "datetime": stamp.isoformat(timespec="seconds").replace("+00:00", "Z"),
        **prices,
    }


def read_validate_1m_csv(path: Path, *, timestamp_role: str = "close") -> list[dict[str, Any]]:
    """Read CSV without pandas; require a clean, strictly ordered 1m series.

    Optional source volume columns are ignored, never used as a synthetic-index
    feature. Gaps and duplicate instants are fatal for a sealed research dataset.
    """
    if not path.is_file():
        raise FileNotFoundError(f"DATASET_NOT_FOUND:{path}")
    if path.suffix.lower() != ".csv":
        raise ValueError("ONLY_CSV_SUPPORTED_FOR_FREEZE: export parquet to CSV explicitly first")
    if timestamp_role not in ("open", "close"):
        raise ValueError("timestamp_role must be 'open' or 'close'")

    before_stat = path.stat()
    before_hash = sha256_file(path)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("CSV_HEADER_MISSING")
        headers = [str(item).strip().lower() for item in reader.fieldnames]
        if len(headers) != len(set(headers)):
            raise ValueError("DUPLICATE_COLUMN_NAMES")
        if any(not item for item in headers):
            raise ValueError("EMPTY_COLUMN_NAME")
        reader.fieldnames = headers
        missing = [column for column in REQUIRED_COLUMNS if column not in headers]
        if missing:
            raise ValueError(f"MISSING_REQUIRED_COLUMNS:{','.join(missing)}")
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"EXTRA_UNNAMED_FIELDS:row={row_number}")
            if not any(value not in (None, "") for value in row.values()):
                raise ValueError(f"BLANK_ROW:row={row_number}")
            rows.append(_normalise_row(row, timestamp_role=timestamp_role, row_number=row_number))

    if not rows:
        raise ValueError("DATASET_HAS_NO_ROWS")
    stamps = [parse_aware_datetime(row["datetime"]) for row in rows]
    for index, (previous, current) in enumerate(zip(stamps, stamps[1:]), start=2):
        delta = current - previous
        if delta <= timedelta(0):
            raise ValueError(f"TIMESTAMPS_NOT_STRICTLY_INCREASING:row={index + 1}")
        if delta != timedelta(minutes=1):
            raise ValueError(
                f"ONE_MINUTE_GAP_OR_DUPLICATE:between={previous.isoformat()} and {current.isoformat()}"
            )

    after_stat = path.stat()
    after_hash = sha256_file(path)
    if (before_stat.st_size, before_stat.st_mtime_ns, before_hash) != (
        after_stat.st_size, after_stat.st_mtime_ns, after_hash
    ):
        raise RuntimeError("SOURCE_CHANGED_DURING_VALIDATION")
    return rows


def aggregate_15m(rows_1m: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Aggregate only complete 15-candle buckets; labels are close timestamps."""
    by_time = {parse_aware_datetime(row["datetime"]): row for row in rows_1m}
    times = sorted(by_time)
    buckets: dict[datetime, list[datetime]] = {}
    one_minute = timedelta(minutes=1)
    for stamp in times:
        minute_of_day = stamp.hour * 60 + stamp.minute
        end_minute = ((minute_of_day + 14) // 15) * 15
        midnight = stamp.replace(hour=0, minute=0, second=0, microsecond=0)
        end = midnight + timedelta(minutes=end_minute)
        buckets.setdefault(end, []).append(stamp)

    output: list[dict[str, Any]] = []
    dropped_partial_buckets = 0
    for end in sorted(buckets):
        expected = [end - one_minute * offset for offset in range(14, -1, -1)]
        actual = sorted(buckets[end])
        if actual != expected:
            dropped_partial_buckets += 1
            continue
        values = [by_time[stamp] for stamp in expected]
        output.append({
            "datetime": end.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "open": values[0]["open"],
            "high": max(item["high"] for item in values),
            "low": min(item["low"] for item in values),
            "close": values[-1]["close"],
        })
    if not output:
        raise ValueError("NO_COMPLETE_15M_BUCKETS")
    return output, dropped_partial_buckets


def _write_csv_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(REQUIRED_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())


def _file_record(path: Path, materialized_path: Path, rows: list[dict[str, Any]], *, timestamp_role: str) -> dict[str, Any]:
    stamps = [row["datetime"] for row in rows]
    return {
        "path": str(path.as_posix()),
        "file_name": path.name,
        "sha256": sha256_file(materialized_path),
        "file_size_bytes": materialized_path.stat().st_size,
        "row_count": len(rows),
        "start_time_utc": stamps[0],
        "end_time_utc": stamps[-1],
        "timestamp_role_in_snapshot": "close",
        "source_timestamp_role": timestamp_role,
        "status": "SEALED",
    }


def freeze_r100_dual_resolution(
    raw_1m_path: str,
    *,
    source: str,
    description: str,
    timestamp_role: str,
    manifest_dir: str = "data/frozen",
) -> dict[str, Any]:
    """Validate source, write canonical 1m/aggregated 15m snapshots, seal manifest.

    Existing snapshot or manifest paths are never overwritten. The original raw
    input is never chmod-ed or edited. If the input is absent, the operation
    aborts before creating a manifest.
    """
    raw_path = Path(raw_1m_path)
    if not source.strip() or not description.strip():
        raise ValueError("SOURCE_AND_DESCRIPTION_REQUIRED")
    if timestamp_role not in ("open", "close"):
        raise ValueError("TIMESTAMP_ROLE_MUST_BE_DECLARED")
    rows_1m = read_validate_1m_csv(raw_path, timestamp_role=timestamp_role)
    rows_15m, dropped_partial_buckets = aggregate_15m(rows_1m)

    out_dir = Path(manifest_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    one_minute_path = out_dir / "r100_1m.csv"
    fifteen_minute_path = out_dir / "r100_15m.csv"
    manifest_path = out_dir / MANIFEST_NAME
    destinations = (one_minute_path, fifteen_minute_path, manifest_path)
    existing = [str(path) for path in destinations if path.exists()]
    if existing:
        raise FileExistsError("FROZEN_OUTPUT_ALREADY_EXISTS:" + ",".join(existing))

    raw_hash_before = sha256_file(raw_path)
    temp_dir = Path(tempfile.mkdtemp(prefix=".r100-freeze-", dir=out_dir))
    created_paths: list[Path] = []
    try:
        temp_1m = temp_dir / one_minute_path.name
        temp_15m = temp_dir / fifteen_minute_path.name
        _write_csv_exclusive(temp_1m, rows_1m)
        _write_csv_exclusive(temp_15m, rows_15m)
        if sha256_file(raw_path) != raw_hash_before:
            raise RuntimeError("SOURCE_CHANGED_BEFORE_SEAL")

        manifest = {
            "schema": "aurelia.dataset_manifest.v1",
            "dataset_name": "R_100 dual-resolution OHLC research dataset",
            "instrument": "R_100",
            "source": source.strip(),
            "description": description.strip(),
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_file": {
                "path": str(raw_path.as_posix()),
                "sha256": raw_hash_before,
                "file_size_bytes": raw_path.stat().st_size,
            },
            "validation": {
                "status": "PASS",
                "ohlc_columns": list(PRICE_COLUMNS),
                "volume_used": False,
                "timestamps_timezone_aware": True,
                "timestamps_strictly_increasing": True,
                "one_minute_gaps": 0,
                "partial_15m_buckets_dropped_at_dataset_edges": dropped_partial_buckets,
                "resolution_15m_aggregated_from_same_1m_source": True,
            },
            "datasets": {
                "1m": _file_record(one_minute_path, temp_1m, rows_1m, timestamp_role=timestamp_role),
                "15m": _file_record(fifteen_minute_path, temp_15m, rows_15m, timestamp_role="aggregated_from_1m"),
            },
            "status": "SEALED",
            "qualification_allowed": False,
            "qualification_note": "Sealing proves file identity and basic OHLC integrity only; it does not qualify strategy performance.",
        }
        temp_manifest = temp_dir / MANIFEST_NAME
        with temp_manifest.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        # os.replace only after all files exist in temp; destination checks above
        # plus exclusive final creation prevent intentional overwrite.
        for temp, final in ((temp_1m, one_minute_path), (temp_15m, fifteen_minute_path)):
            if final.exists():
                raise FileExistsError(f"FROZEN_OUTPUT_ALREADY_EXISTS:{final}")
            os.link(temp, final)
            created_paths.append(final)
            os.chmod(final, 0o444)
        if manifest_path.exists():
            raise FileExistsError(f"FROZEN_OUTPUT_ALREADY_EXISTS:{manifest_path}")
        os.link(temp_manifest, manifest_path)
        created_paths.append(manifest_path)
        os.chmod(manifest_path, 0o444)
        return manifest
    except Exception:
        for destination in created_paths:
            try:
                destination.unlink()
            except FileNotFoundError:
                pass
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def verify_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Re-hash and revalidate all sealed files before any backtest uses them."""
    path = Path(manifest_path)
    if not path.is_file():
        raise FileNotFoundError(f"SEALED_MANIFEST_MISSING:{path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "aurelia.dataset_manifest.v1" or manifest.get("status") != "SEALED":
        raise ValueError("MANIFEST_NOT_SEALED_OR_UNSUPPORTED")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict) or not {"1m", "15m"}.issubset(datasets):
        raise ValueError("DUAL_RESOLUTION_MANIFEST_REQUIRED")
    for resolution in ("1m", "15m"):
        record = datasets[resolution]
        data_path = Path(record["path"])
        if not data_path.is_absolute():
            data_path = path.parent.parent.parent / data_path
        if not data_path.is_file():
            raise FileNotFoundError(f"SEALED_DATASET_MISSING:{data_path}")
        if sha256_file(data_path) != record.get("sha256"):
            raise ValueError(f"SEALED_DATASET_HASH_MISMATCH:{resolution}")
        if data_path.stat().st_size != record.get("file_size_bytes"):
            raise ValueError(f"SEALED_DATASET_SIZE_MISMATCH:{resolution}")
        with data_path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            headers = [str(item).strip().lower() for item in (reader.fieldnames or [])]
            if not all(column in headers for column in REQUIRED_COLUMNS):
                raise ValueError(f"SEALED_DATASET_SCHEMA_MISMATCH:{resolution}")
            count = sum(1 for _ in reader)
        if count != record.get("row_count"):
            raise ValueError(f"SEALED_DATASET_ROW_COUNT_MISMATCH:{resolution}")
        if record.get("status") != "SEALED":
            raise ValueError(f"DATASET_NOT_SEALED:{resolution}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/raw/r100_1m.csv")
    parser.add_argument("--source", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--timestamp-role", choices=("open", "close"), required=True,
                        help="Whether input datetime timestamps mark each 1m candle's opening or closing time.")
    parser.add_argument("--manifest-dir", default="data/frozen")
    args = parser.parse_args()
    manifest = freeze_r100_dual_resolution(
        args.input, source=args.source, description=args.description,
        timestamp_role=args.timestamp_role, manifest_dir=args.manifest_dir,
    )
    print(json.dumps({
        "status": manifest["status"],
        "manifest": str((Path(args.manifest_dir) / MANIFEST_NAME).as_posix()),
        "datasets": {
            key: {"sha256": value["sha256"], "row_count": value["row_count"]}
            for key, value in manifest["datasets"].items()
        },
        "qualification_allowed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
