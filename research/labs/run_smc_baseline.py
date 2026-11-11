"""Run the independent ATOS v2.0 SMC baseline from public OHLC history."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
from importlib import metadata as importlib_metadata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from research.labs.atos_smc_v2 import (
    BacktestConfig,
    ResearchDataError,
    Strategy1Config,
    Strategy2Config,
    TimeWindow,
    data_quality_report,
    run_strategy_comparison,
    validate_ohlc,
)
from research.labs.deriv_history import (
    fetch_deriv_candles,
    fetch_deriv_symbol_metadata,
    fetch_yfinance_ohlc,
)


def _aware_datetime(value: str) -> datetime:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include UTC offset or Z")
    return stamp.astimezone(timezone.utc)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Research-only ATOS v2 SMC strategy comparison"
    )
    parser.add_argument("--provider", choices=("deriv", "yfinance", "csv"), default="deriv")
    parser.add_argument("--symbol", default="R_100", help="Exact Deriv symbol or Yahoo ticker")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--start", type=_aware_datetime)
    parser.add_argument("--end", type=_aware_datetime)
    parser.add_argument("--input-csv", type=Path)
    parser.add_argument("--interval", default="1m")
    parser.add_argument("--tick-size", type=float, help="Explicit minimum price increment backed by an instrument-specific source")
    parser.add_argument("--tick-size-source", default="UNVERIFIED_USER_INPUT")
    parser.add_argument("--point-value", type=float, default=1.0,
                        help="Cash P&L per normalized price-unit; default 1.0 is not a verified Deriv contract multiplier")
    parser.add_argument("--point-value-verified", action="store_true")
    parser.add_argument("--point-value-source", default="UNVERIFIED_NORMALIZED_UNIT")
    parser.add_argument("--spread-ticks-round-trip", type=float, default=0.0)
    parser.add_argument("--slippage-ticks-round-trip", type=float, default=0.0)
    parser.add_argument("--commission-cash-per-unit-round-trip", type=float, default=0.0)
    parser.add_argument("--costs-verified", action="store_true")
    parser.add_argument("--cost-source", default="UNVERIFIED_USER_ASSUMPTION")
    parser.add_argument("--starting-equity", type=float, default=10_000.0)
    parser.add_argument("--risk-fraction", type=float, default=0.01)
    parser.add_argument("--daily-drawdown-limit", type=float, default=0.03)
    parser.add_argument("--window-start", default="00:00")
    parser.add_argument("--cutoff", default="08:50")
    parser.add_argument("--minimum-coverage-pct", type=float, default=99.0)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/research/atos_smc_v2"))
    return parser


async def _download_deriv(args: argparse.Namespace, start: datetime, end: datetime):
    metadata = await fetch_deriv_symbol_metadata(args.symbol)
    data = await fetch_deriv_candles(args.symbol, start, end)
    return data, metadata


def _read_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    timestamp_column = next(
        (column for column in frame.columns if str(column).lower() in ("timestamp_utc", "timestamp", "datetime", "time")),
        None,
    )
    if timestamp_column is None:
        raise ResearchDataError("CSV_TIMESTAMP_COLUMN_REQUIRED")
    parsed = pd.to_datetime(frame.pop(timestamp_column), utc=False, errors="raise")
    if isinstance(parsed, pd.Series):
        if not pd.api.types.is_datetime64_any_dtype(parsed.dtype) or parsed.dt.tz is None:
            raise ResearchDataError("CSV_TIMESTAMP_MUST_INCLUDE_TIMEZONE")
        index = pd.DatetimeIndex(parsed)
    else:
        index = pd.DatetimeIndex(parsed)
    if index.tz is None:
        raise ResearchDataError("CSV_TIMESTAMP_MUST_INCLUDE_TIMEZONE")
    frame.index = index
    return validate_ohlc(frame)


def _distribution_version(name: str) -> str | None:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def _json_default(value: Any):
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def main() -> int:
    """Fail closed: legacy S1/S2 CLI is not an ATOS v2.0 preregistered experiment."""
    raise RuntimeError(
        "LEGACY_ATOS_SMC_BASELINE_QUARANTINED: no download, backtest, or artifact write "
        "is permitted until the v2.0 strategy, licensed data, cost model, and G0 registration are complete"
    )


if __name__ == "__main__":
    raise SystemExit(main())
