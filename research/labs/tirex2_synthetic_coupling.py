"""Isolated, leakage-aware synthetic coupling PoC for TiRex-2-like research.

This module creates synthetic multivariate training examples from separate
univariate price series. It does not claim that the composed series are
causally related, and its output must not be used as a live trading signal.
Only timestamps, series identifiers, and one price column are read; volume,
order-book data, future-known covariates, broker APIs, and execution code are
intentionally out of scope.
"""
from __future__ import annotations

import argparse
import array
import bisect
import csv
import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

SPLITS = ("train", "validation", "test")
COUPLING_SCHEMA = "aurelia.tirex2.synthetic-coupling.v1"


@dataclass(frozen=True)
class SeriesData:
    """Memory-efficient ordered observations for one univariate series."""
    series_id: str
    timestamps: array.array
    values: array.array

    def __len__(self) -> int:
        return len(self.values)


@dataclass(frozen=True)
class WindowPool:
    """Index range from which windows wholly inside one time split are drawn."""
    split: str
    data: SeriesData
    start_index: int
    end_index: int  # exclusive
    context_length: int
    horizon: int

    @property
    def window_count(self) -> int:
        return max(0, self.end_index - self.start_index - self.context_length - self.horizon + 1)

    def draw(self, rng: random.Random) -> "ForecastWindow":
        if self.window_count < 1:
            raise ValueError(f"no windows available for series={self.data.series_id!r}, split={self.split}")
        last_start = self.end_index - self.context_length - self.horizon
        start = rng.randint(self.start_index, last_start)
        context_end = start + self.context_length
        target_end = context_end + self.horizon
        return ForecastWindow(
            split=self.split,
            series_id=self.data.series_id,
            context_start_ts=float(self.data.timestamps[start]),
            context_end_ts=float(self.data.timestamps[context_end - 1]),
            target_start_ts=float(self.data.timestamps[context_end]),
            target_end_ts=float(self.data.timestamps[target_end - 1]),
            context_values=tuple(float(v) for v in self.data.values[start:context_end]),
            target_values=tuple(float(v) for v in self.data.values[context_end:target_end]),
        )


@dataclass(frozen=True)
class ForecastWindow:
    split: str
    series_id: str
    context_start_ts: float
    context_end_ts: float
    target_start_ts: float
    target_end_ts: float
    context_values: tuple[float, ...]
    target_values: tuple[float, ...]

    def validate(self, context_length: int, horizon: int) -> None:
        if self.split not in SPLITS:
            raise ValueError("invalid split")
        if not self.series_id.strip():
            raise ValueError("series_id is required")
        if len(self.context_values) != context_length or len(self.target_values) != horizon:
            raise ValueError("window shape mismatch")
        numeric = (self.context_start_ts, self.context_end_ts, self.target_start_ts,
                   self.target_end_ts, *self.context_values, *self.target_values)
        if not all(math.isfinite(float(v)) for v in numeric):
            raise ValueError("non-finite timestamp or price value")
        if not (self.context_start_ts <= self.context_end_ts < self.target_start_ts <= self.target_end_ts):
            raise ValueError("context and target timestamps are not chronological")
        if any(v <= 0 for v in (*self.context_values, *self.target_values)):
            raise ValueError("price values must be positive")


def parse_timestamp(raw: str) -> float:
    """Parse Unix seconds or timezone-aware ISO-8601 and return UTC epoch seconds."""
    value = raw.strip()
    if not value:
        raise ValueError("empty timestamp")
    try:
        epoch_seconds = float(value)
    except ValueError:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"timestamp must be Unix seconds or timezone-aware ISO-8601: {raw!r}") from exc
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("ISO-8601 timestamps must include a timezone")
        epoch_seconds = dt.astimezone(timezone.utc).timestamp()
    if not math.isfinite(epoch_seconds):
        raise ValueError("timestamp must be finite")
    if abs(epoch_seconds) >= 100_000_000_000:
        raise ValueError("numeric timestamps must use Unix seconds, not milliseconds")
    return epoch_seconds


def load_series_csv(
    path: str | Path,
    *,
    timestamp_column: str = "timestamp",
    series_column: str = "symbol",
    value_column: str = "close",
    expected_interval_seconds: float | None = 60.0,
) -> dict[str, SeriesData]:
    """Load long-format price CSV and fail on duplicates, disorder, or gaps.

    Required columns default to timestamp,symbol,close. Series may be
    interleaved in the CSV, but each series must be strictly chronological.
    A configured expected interval is enforced instead of silently bridging
    missing bars.
    """
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"input CSV not found: {source}")
    if expected_interval_seconds is not None and (
        not math.isfinite(expected_interval_seconds) or expected_interval_seconds <= 0
    ):
        raise ValueError("expected_interval_seconds must be positive and finite")

    timestamps: dict[str, array.array] = {}
    values: dict[str, array.array] = {}
    last_ts: dict[str, float] = {}
    with source.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {timestamp_column, series_column, value_column}
        present = set(reader.fieldnames or ())
        missing = sorted(required - present)
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(missing)}")
        for line_no, row in enumerate(reader, start=2):
            series_id = (row.get(series_column) or "").strip()
            if not series_id:
                raise ValueError(f"empty series id at CSV line {line_no}")
            try:
                timestamp = parse_timestamp(row.get(timestamp_column) or "")
                price = float(row.get(value_column) or "")
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid data at CSV line {line_no}: {exc}") from exc
            if not math.isfinite(price) or price <= 0:
                raise ValueError(f"price must be positive and finite at CSV line {line_no}")
            previous = last_ts.get(series_id)
            if previous is not None:
                if timestamp <= previous:
                    raise ValueError(f"non-increasing timestamp for {series_id!r} at CSV line {line_no}")
                if expected_interval_seconds is not None:
                    gap = timestamp - previous
                    tolerance = max(1e-6, expected_interval_seconds * 1e-6)
                    if abs(gap - expected_interval_seconds) > tolerance:
                        raise ValueError(
                            f"unexpected interval for {series_id!r} at CSV line {line_no}: "
                            f"{gap:g}s, expected {expected_interval_seconds:g}s"
                        )
            timestamps.setdefault(series_id, array.array("d")).append(timestamp)
            values.setdefault(series_id, array.array("d")).append(price)
            last_ts[series_id] = timestamp

    if not timestamps:
        raise ValueError("CSV contains no observations")
    result = {
        series_id: SeriesData(series_id, timestamps[series_id], values[series_id])
        for series_id in sorted(timestamps)
    }
    if any(len(series) < 3 for series in result.values()):
        short = [series_id for series_id, series in result.items() if len(series) < 3]
        raise ValueError(f"each series needs at least three observations; too short: {short}")
    return result


def build_window_pools(
    series: Mapping[str, SeriesData],
    *,
    context_length: int = 128,
    horizon: int = 1,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> tuple[dict[str, dict[str, WindowPool]], tuple[float, float]]:
    """Create chronological index pools; windows never cross split boundaries.

    Split cutoffs are based on elapsed UTC time from the earliest to latest
    observation, not randomly shuffled rows. Only index ranges are stored, so
    long minute-resolution histories do not create millions of Python windows.
    """
    if context_length < 1 or horizon < 1:
        raise ValueError("context_length and horizon must be positive")
    if not (0.5 <= train_fraction < 0.9):
        raise ValueError("train_fraction must be in [0.5, 0.9)")
    if not (0.05 <= validation_fraction < 0.3) or train_fraction + validation_fraction >= 1:
        raise ValueError("invalid validation_fraction or no remaining test split")
    if not series:
        raise ValueError("series data is empty")

    global_min = min(float(data.timestamps[0]) for data in series.values())
    global_max = max(float(data.timestamps[-1]) for data in series.values())
    if global_max <= global_min:
        raise ValueError("dataset must span more than one timestamp")
    train_cut = global_min + (global_max - global_min) * train_fraction
    validation_cut = global_min + (global_max - global_min) * (train_fraction + validation_fraction)
    if not (global_min < train_cut < validation_cut < global_max):
        raise ValueError("chronological split boundaries are not valid")

    pools: dict[str, dict[str, WindowPool]] = {split: {} for split in SPLITS}
    for series_id, data in series.items():
        train_end = bisect.bisect_left(data.timestamps, train_cut)
        validation_end = bisect.bisect_left(data.timestamps, validation_cut)
        ranges = {
            "train": (0, train_end),
            "validation": (train_end, validation_end),
            "test": (validation_end, len(data)),
        }
        for split, (start, end) in ranges.items():
            pool = WindowPool(split, data, start, end, context_length, horizon)
            if pool.window_count > 0:
                pools[split][series_id] = pool
    return pools, (train_cut, validation_cut)


def couple_windows(
    pools: Mapping[str, WindowPool],
    *,
    n_variates: int = 3,
    sample_count: int = 1000,
    seed: int = 7,
) -> list[dict[str, object]]:
    """Compose independent windows from distinct univariate series.

    Every example is explicitly tagged synthetic. No temporal synchronization
    or empirical relationship between source series is implied. Different
    instruments must not be interpreted as real covariates merely because
    they are placed in the same synthetic example.
    """
    if n_variates < 2:
        raise ValueError("synthetic coupling requires at least two variates")
    if sample_count < 1:
        raise ValueError("sample_count must be positive")
    eligible = {sid: pool for sid, pool in pools.items() if pool.window_count > 0}
    split_names = {pool.split for pool in eligible.values()}
    if len(split_names) != 1:
        raise ValueError("coupling pool must contain exactly one split")
    split = next(iter(split_names))
    series_ids = sorted(eligible)
    if len(series_ids) < n_variates:
        raise ValueError(
            f"split {split!r} has {len(series_ids)} eligible series; {n_variates} are required; refusing fallback"
        )
    rng = random.Random(seed)
    samples: list[dict[str, object]] = []
    for index in range(sample_count):
        chosen_ids = rng.sample(series_ids, n_variates)
        variates = []
        for series_id in chosen_ids:
            window = eligible[series_id].draw(rng)
            window.validate(eligible[series_id].context_length, eligible[series_id].horizon)
            variates.append({
                "series_id": window.series_id,
                "context_start_ts": window.context_start_ts,
                "context_end_ts": window.context_end_ts,
                "target_start_ts": window.target_start_ts,
                "target_end_ts": window.target_end_ts,
                "context": list(window.context_values),
                "target": list(window.target_values),
            })
        samples.append({
            "sample_id": f"{split}-{index:06d}",
            "split": split,
            "synthetic_coupling": True,
            "live_features_permitted": False,
            "coupling_semantics": "independent_univariate_windows_not_real_cross_series_relationships",
            "future_known_covariates": [],
            "variates": variates,
        })
    return samples


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def epoch_to_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def write_artifacts(
    *,
    output_dir: str | Path,
    input_csv: str | Path,
    pools: Mapping[str, Mapping[str, WindowPool]],
    samples_by_split: Mapping[str, list[dict[str, object]]],
    split_boundaries: tuple[float, float],
    context_length: int,
    horizon: int,
    n_variates: int,
    seed: int,
    expected_interval_seconds: float | None,
) -> Path:
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"output directory already exists; refusing to overwrite: {destination}")
    destination.mkdir(parents=True, exist_ok=False)
    samples_path = destination / "coupled_samples.jsonl"
    with samples_path.open("w", encoding="utf-8", newline="\n") as handle:
        for split in SPLITS:
            for sample in samples_by_split[split]:
                handle.write(json.dumps(sample, separators=(",", ":"), allow_nan=False) + "\n")
    manifest = {
        "schema": COUPLING_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "input_file_name": Path(input_csv).name,
        "input_sha256": sha256_file(input_csv),
        "split_rule": "chronological_by_elapsed_utc_time; context_and_target_contained_in_one_split",
        "split_boundaries_utc": {
            "train_validation": epoch_to_iso(split_boundaries[0]),
            "validation_test": epoch_to_iso(split_boundaries[1]),
        },
        "context_length": context_length,
        "forecast_horizon": horizon,
        "n_variates": n_variates,
        "seed": seed,
        "expected_interval_seconds": expected_interval_seconds,
        "source_series_count": len({sid for split in pools.values() for sid in split}),
        "available_windows_per_split": {
            split: {sid: pool.window_count for sid, pool in sorted(pools[split].items())}
            for split in SPLITS
        },
        "samples_per_split": {split: len(samples_by_split[split]) for split in SPLITS},
        "synthetic_coupling": True,
        "coupling_semantics": "random independent windows from distinct series; no real cross-series dependency claimed",
        "data_policy": {
            "price_column_only": True,
            "volume_used": False,
            "order_book_used": False,
            "future_known_covariates_used": False,
            "live_features_permitted": False,
        },
        "permitted_use": "isolated research/pretraining experiments and data-pipeline validation only",
        "promotion_status": "RESEARCH_ONLY_NOT_LAYER9_INTEGRATED",
        "samples_file_sha256": sha256_file(samples_path),
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Long-format CSV with timestamp,symbol,close columns by default")
    parser.add_argument("--output-dir", required=True, help="New output directory; existing paths are never overwritten")
    parser.add_argument("--timestamp-column", default="timestamp")
    parser.add_argument("--series-column", default="symbol")
    parser.add_argument("--value-column", default="close")
    parser.add_argument("--context-length", type=int, default=128)
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--variates", type=int, default=3)
    parser.add_argument("--samples-per-split", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--expected-interval-seconds", type=float, default=60.0,
                        help="Set 900 for 15-minute bars; use 0 to disable strict interval checks")
    args = parser.parse_args(argv)

    interval = None if args.expected_interval_seconds == 0 else args.expected_interval_seconds
    series = load_series_csv(
        args.csv,
        timestamp_column=args.timestamp_column,
        series_column=args.series_column,
        value_column=args.value_column,
        expected_interval_seconds=interval,
    )
    pools, boundaries = build_window_pools(series, context_length=args.context_length, horizon=args.horizon)
    samples_by_split: dict[str, list[dict[str, object]]] = {}
    for split in SPLITS:
        samples_by_split[split] = couple_windows(
            pools[split], n_variates=args.variates, sample_count=args.samples_per_split, seed=args.seed
        )
    manifest_path = write_artifacts(
        output_dir=args.output_dir,
        input_csv=args.csv,
        pools=pools,
        samples_by_split=samples_by_split,
        split_boundaries=boundaries,
        context_length=args.context_length,
        horizon=args.horizon,
        n_variates=args.variates,
        seed=args.seed,
        expected_interval_seconds=interval,
    )
    print(json.dumps({
        "status": "POC_DATA_PIPELINE_COMPLETE",
        "manifest": str(manifest_path),
        "samples": str(Path(args.output_dir) / "coupled_samples.jsonl"),
        "input_sha256": sha256_file(args.csv),
        "series_count": len(series),
        "available_windows": {split: {sid: pool.window_count for sid, pool in pools[split].items()} for split in SPLITS},
        "sample_counts": {split: len(samples_by_split[split]) for split in SPLITS},
        "live_execution_attempted": False,
        "live_features_permitted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
