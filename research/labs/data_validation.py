"""Fail-closed validation for timestamped OHLC research datasets.

This module validates data only. It does not generate signals, choose strategy
parameters, repair observations, or authorize capital.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
REQUIRED_COLUMNS = ("open", "high", "low", "close")


@dataclass(frozen=True)
class ValidationConfig:
    timeframe: str = "1min"
    target_timezone: str = "America/New_York"
    source_timezone: str | None = None
    require_positive_prices: bool = True

    @property
    def interval(self) -> pd.Timedelta:
        try:
            value = pd.Timedelta(self.timeframe)
        except (TypeError, ValueError) as exc:
            raise ValueError("TIMEFRAME_INVALID") from exc
        if value <= pd.Timedelta(0):
            raise ValueError("TIMEFRAME_MUST_BE_POSITIVE")
        return value


@dataclass(frozen=True)
class ValidationResult:
    status: str
    report: dict[str, Any]
    normalized_frame: pd.DataFrame | None


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_frame_sha256(frame: pd.DataFrame) -> str:
    """Hash a deterministic UTC-indexed representation; no row reordering."""
    canonical = frame.copy()
    canonical.index = canonical.index.tz_convert("UTC")
    canonical.index.name = "timestamp_utc"
    payload = canonical.to_csv(
        index=True,
        columns=list(canonical.columns),
        date_format="%Y-%m-%dT%H:%M:%S.%f%z",
        float_format="%.17g",
        lineterminator="\n",
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def validate_frame(
    frame: pd.DataFrame,
    config: ValidationConfig = ValidationConfig(),
    *,
    raw_file_sha256: str | None = None,
) -> ValidationResult:
    """Validate a DataFrame without sorting, filling, dropping, or mutating it."""
    report: dict[str, Any] = {
        "raw_file_sha256": raw_file_sha256,
        "normalized_data_sha256": None,
        "source_timezone": None,
        "target_timezone": config.target_timezone,
        "timeframe": config.timeframe,
        "total_bars": int(len(frame)),
        "duplicate_timestamps": 0,
        "out_of_order_timestamps": 0,
        "missing_bars": None,
        "invalid_ohlc_rows": None,
        "non_finite_rows": None,
        "schema_valid": False,
        "timezone_valid": False,
        "continuity_valid": False,
        "ohlc_valid": False,
        "overall_status": "STATE_UNKNOWN_ABORT",
        "errors": [],
    }

    if not isinstance(frame, pd.DataFrame) or frame.empty:
        report["errors"].append("DATAFRAME_EMPTY_OR_INVALID")
        return ValidationResult("FAIL", report, None)

    missing_columns = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing_columns:
        report["errors"].append("REQUIRED_COLUMNS_MISSING:" + ",".join(missing_columns))
        return ValidationResult("FAIL", report, None)
    report["schema_valid"] = True

    try:
        index = pd.DatetimeIndex(frame.index)
        if index.isna().any():
            raise ValueError("TIMESTAMP_NULL")
        if index.tz is None:
            if not config.source_timezone:
                raise ValueError("NAIVE_TIMESTAMP_WITHOUT_SOURCE_TIMEZONE")
            index = index.tz_localize(
                config.source_timezone, ambiguous="raise", nonexistent="raise"
            )
            report["source_timezone"] = config.source_timezone
        else:
            report["source_timezone"] = str(index.tz)
        utc_index = index.tz_convert("UTC")
        report["timezone_valid"] = True
    except Exception as exc:
        report["errors"].append(str(exc) or "TIMESTAMP_INVALID")
        return ValidationResult("FAIL", report, None)

    duplicated = utc_index.duplicated(keep=False)
    report["duplicate_timestamps"] = int(duplicated.sum())
    utc_ns = utc_index.asi8
    if len(utc_ns) > 1:
        diffs = utc_ns[1:] - utc_ns[:-1]
        report["out_of_order_timestamps"] = int((diffs < 0).sum())
    else:
        diffs = []
    if report["duplicate_timestamps"]:
        report["errors"].append("DUPLICATE_TIMESTAMPS")
    if report["out_of_order_timestamps"]:
        report["errors"].append("TIMESTAMPS_NOT_STRICTLY_INCREASING")

    try:
        interval_ns = config.interval.value
        report["missing_bars"] = int(
            sum(max(0, int(delta // interval_ns) - 1) for delta in diffs if delta > interval_ns)
        )
        report["continuity_valid"] = (
            report["duplicate_timestamps"] == 0
            and report["out_of_order_timestamps"] == 0
            and all(int(delta) == interval_ns for delta in diffs)
        )
        if not report["continuity_valid"]:
            report["errors"].append("TIMEFRAME_CONTINUITY_FAILED")
    except ValueError as exc:
        report["errors"].append(str(exc))
        return ValidationResult("FAIL", report, None)

    numeric = frame.loc[:, list(REQUIRED_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    values = numeric.to_numpy(dtype="float64", na_value=float("nan"))
    import numpy as np
    finite_mask = np.isfinite(values).all(axis=1)
    report["non_finite_rows"] = int((~finite_mask).sum())

    if report["non_finite_rows"] == 0:
        o = numeric["open"].to_numpy(dtype="float64")
        h = numeric["high"].to_numpy(dtype="float64")
        low = numeric["low"].to_numpy(dtype="float64")
        c = numeric["close"].to_numpy(dtype="float64")
        invalid = (
            (h < np.maximum.reduce([o, c, low]))
            | (low > np.minimum.reduce([o, c, h]))
        )
        if config.require_positive_prices:
            invalid |= (values <= 0).any(axis=1)
        report["invalid_ohlc_rows"] = int(invalid.sum())
    else:
        report["invalid_ohlc_rows"] = None
        report["errors"].append("NON_FINITE_OR_NON_NUMERIC_OHLC")

    report["ohlc_valid"] = (
        report["non_finite_rows"] == 0 and report["invalid_ohlc_rows"] == 0
    )
    if not report["ohlc_valid"] and report["invalid_ohlc_rows"]:
        report["errors"].append("OHLC_RELATIONSHIP_INVALID")

    normalized = frame.copy()
    normalized.index = index.tz_convert(config.target_timezone)
    normalized.index.name = "timestamp"
    try:
        report["normalized_data_sha256"] = _canonical_frame_sha256(normalized)
    except Exception as exc:
        report["errors"].append("NORMALIZED_HASH_FAILED:" + str(exc))

    passed = (
        report["schema_valid"]
        and report["timezone_valid"]
        and report["continuity_valid"]
        and report["ohlc_valid"]
        and report["normalized_data_sha256"] is not None
        and not report["errors"]
    )
    report["overall_status"] = "PASS" if passed else "STATE_UNKNOWN_ABORT"
    return ValidationResult("PASS" if passed else "FAIL", report, normalized if passed else None)


class DataValidationEngine:
    """Parquet loader and fail-closed validator for research datasets."""

    def __init__(
        self,
        filepath: str,
        config: ValidationConfig = ValidationConfig(),
    ) -> None:
        self.filepath = Path(filepath)
        self.config = config
        self.result: ValidationResult | None = None

    def load_and_validate(self) -> pd.DataFrame:
        if not self.filepath.is_file():
            raise FileNotFoundError(f"DATA_FILE_NOT_FOUND:{self.filepath}")
        raw_hash = _file_sha256(self.filepath)
        try:
            frame = pd.read_parquet(self.filepath)
        except ImportError as exc:
            raise RuntimeError("PARQUET_ENGINE_MISSING_INSTALL_PYARROW_OR_FASTPARQUET") from exc
        self.result = validate_frame(frame, self.config, raw_file_sha256=raw_hash)
        if self.result.status != "PASS":
            raise ValueError("DATA_VALIDATION_FAILED:" + ",".join(self.result.report["errors"]))
        return self.result.normalized_frame.copy()

    def generate_report(self) -> dict[str, Any]:
        if self.result is None:
            raise RuntimeError("VALIDATION_NOT_RUN")
        return asdict(self.result)["report"]
