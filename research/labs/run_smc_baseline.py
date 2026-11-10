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
    DEFAULT_DERIV_APP_ID,
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
    parser.add_argument("--app-id", default=DEFAULT_DERIV_APP_ID)
    parser.add_argument("--input-csv", type=Path)
    parser.add_argument("--interval", default="1m")
    parser.add_argument("--tick-size", type=float, help="Explicit minimum price increment backed by an instrument-specific source")
    parser.add_argument("--tick-size-source", default="UNVERIFIED_USER_INPUT")
    parser.add_argument("--use-display-increment-proxy", action="store_true",
                        help="Use 10^-pip_size for research sensitivity only; this is not verified as the minimum tradeable tick")
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
    metadata = await fetch_deriv_symbol_metadata(args.symbol, app_id=args.app_id)
    data = await fetch_deriv_candles(args.symbol, start, end, app_id=args.app_id)
    return data, metadata


def _read_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    timestamp_column = next(
        (column for column in frame.columns if str(column).lower() in ("timestamp_utc", "timestamp", "datetime", "time")),
        None,
    )
    if timestamp_column is None:
        raise ResearchDataError("CSV_TIMESTAMP_COLUMN_REQUIRED")
    index = pd.to_datetime(frame.pop(timestamp_column), utc=False, errors="raise")
    if not isinstance(index, pd.DatetimeIndex) or index.tz is None:
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
    args = _parser().parse_args()
    if args.days < 1 or args.days > 365:
        raise SystemExit("--days must be between 1 and 365")
    if not 0 < args.minimum_coverage_pct <= 100:
        raise SystemExit("--minimum-coverage-pct must be in (0,100]")
    if args.costs_verified and args.cost_source == "UNVERIFIED_USER_ASSUMPTION":
        raise SystemExit("--costs-verified requires a documented --cost-source")
    if args.point_value_verified and args.point_value_source == "UNVERIFIED_NORMALIZED_UNIT":
        raise SystemExit("--point-value-verified requires a documented --point-value-source")
    if args.tick_size is not None and args.tick_size_source == "UNVERIFIED_USER_INPUT":
        raise SystemExit("--tick-size requires a documented --tick-size-source")

    end = args.end or (
        pd.Timestamp.now(tz="UTC").floor("min") - pd.Timedelta(minutes=1)
    ).to_pydatetime()
    start = args.start or (end - timedelta(days=args.days))
    if end <= start:
        raise SystemExit("history end must be later than start")

    metadata: dict[str, Any]
    if args.provider == "deriv":
        data, metadata = asyncio.run(_download_deriv(args, start, end))
    elif args.provider == "yfinance":
        data = fetch_yfinance_ohlc(args.symbol, start, end, interval=args.interval)
        metadata = {
            "symbol": args.symbol,
            "provider": "Yahoo Finance via yfinance",
            "authenticated": False,
            "metadata_source": "not applicable",
        }
    else:
        if args.input_csv is None:
            raise SystemExit("--input-csv is required when --provider=csv")
        data = _read_csv(args.input_csv)
        metadata = {
            "symbol": args.symbol,
            "provider": "user-supplied CSV",
            "authenticated": False,
            "source_path": str(args.input_csv),
        }

    data = validate_ohlc(data)
    data.attrs["symbol"] = args.symbol
    tick_size: float | None = args.tick_size
    tick_size_status = "USER_DECLARED_SOURCE_NOT_INDEPENDENTLY_VERIFIED" if args.tick_size is not None else "UNVERIFIED"
    tick_size_source = args.tick_size_source if args.tick_size is not None else "UNVERIFIED"
    if tick_size is None and args.use_display_increment_proxy:
        tick_size = metadata.get("display_increment_proxy")
        tick_size_status = "UNVERIFIED_DISPLAY_INCREMENT_PROXY"
        tick_size_source = "10^-Deriv-pip_size; display precision only"
    if tick_size is None or float(tick_size) <= 0:
        raise SystemExit(
            "INSTRUMENT_TICK_SIZE_UNKNOWN: supply --tick-size with an instrument-specific "
            "minimum-increment source, or explicitly opt into --use-display-increment-proxy"
        )
    quality = data_quality_report(
        data,
        start_utc=pd.Timestamp(start),
        end_utc=pd.Timestamp(end) + pd.Timedelta(minutes=1),
    )
    if quality["coverage_pct"] is None or quality["coverage_pct"] < args.minimum_coverage_pct:
        report = {
            "schema": "atos.smc.baseline.blocked.v1",
            "status": "BLOCKED_DATA_QUALITY",
            "reason": "HISTORY_COVERAGE_BELOW_THRESHOLD",
            "symbol": args.symbol,
            "source_metadata": metadata,
            "data_quality": quality,
            "required_coverage_pct": args.minimum_coverage_pct,
            "research_only": True,
            "live_execution": "BLOCKED",
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "baseline_blocked.json").write_text(
            json.dumps(report, indent=2, default=_json_default, allow_nan=False),
            encoding="utf-8",
        )
        print(json.dumps(report, indent=2, default=_json_default))
        return 2

    time_window = TimeWindow(start=args.window_start, cutoff=args.cutoff)
    backtest = BacktestConfig(
        starting_equity=args.starting_equity,
        risk_fraction=args.risk_fraction,
        daily_drawdown_limit=args.daily_drawdown_limit,
        tick_size=float(tick_size),
        point_value=float(args.point_value),
        spread_ticks_round_trip=float(args.spread_ticks_round_trip),
        slippage_ticks_round_trip=float(args.slippage_ticks_round_trip),
        commission_cash_per_unit_round_trip=float(args.commission_cash_per_unit_round_trip),
        costs_verified=bool(args.costs_verified),
        point_value_verified=bool(args.point_value_verified),
        time_window=time_window,
    )
    comparison = run_strategy_comparison(
        data,
        tick_size=float(tick_size),
        backtest=backtest,
        strategy1=Strategy1Config(time_window=time_window),
        strategy2=Strategy2Config(time_window=time_window),
    )
    comparison["source_metadata"] = metadata
    comparison["data_quality"] = quality
    comparison["period"] = {
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "days_requested": args.days,
        "bar_count": len(data),
    }
    comparison["run_provenance"] = {
        "source_commit": os.environ.get("GITHUB_SHA", "LOCAL_UNBOUND"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "pandas_version": pd.__version__,
        "dependencies": {
            "numpy": __import__("numpy").__version__,
            "websockets": _distribution_version("websockets"),
            "yfinance": _distribution_version("yfinance"),
        },
    }
    comparison["input_assumptions"] = {
        "tick_size": float(tick_size),
        "tick_size_source": tick_size_source,
        "tick_size_status": tick_size_status,
        "display_precision": metadata.get("price_precision"),
        "display_increment_proxy": metadata.get("display_increment_proxy"),
        "point_value": float(args.point_value),
        "point_value_user_asserted_verified": bool(args.point_value_verified),
        "point_value_source": args.point_value_source,
        "point_value_status": (
            "USER_ASSERTED_NOT_INDEPENDENTLY_CHECKED" if args.point_value_verified
            else "NORMALIZED_OR_UNVERIFIED"
        ),
        "costs_user_asserted_verified": bool(args.costs_verified),
        "cost_source": args.cost_source,
        "cost_status": (
            "USER_ASSERTED_NOT_INDEPENDENTLY_CHECKED" if args.costs_verified
            else "UNVERIFIED_ASSUMPTION"
        ),
        "tick_size_source_status": metadata.get("tick_size_source_status", tick_size_status),
        "spread_ticks_round_trip": float(args.spread_ticks_round_trip),
        "slippage_ticks_round_trip": float(args.slippage_ticks_round_trip),
        "commission_cash_per_unit_round_trip": float(args.commission_cash_per_unit_round_trip),
        "normalized_position_units": not bool(args.point_value_verified),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = args.output_dir / f"{args.symbol}_1m_{args.days}d_{stamp}.json"
    data_path = args.output_dir / f"{args.symbol}_1m_{args.days}d_{stamp}.csv"
    data.to_csv(data_path, index_label="timestamp_utc")
    comparison["data_artifact"] = {
        "filename": data_path.name,
        "sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "rows": int(len(data)),
    }
    report_path.write_text(
        json.dumps(comparison, indent=2, default=_json_default, allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "COMPLETED_RESEARCH_ONLY",
        "report": str(report_path),
        "data": str(data_path),
        "symbol": args.symbol,
        "quality": quality,
        "strategy_1_metrics": comparison["strategy_1"]["metrics"],
        "strategy_2_metrics": comparison["strategy_2"]["metrics"],
        "costs_user_asserted_verified": args.costs_verified,
        "point_value_user_asserted_verified": args.point_value_verified,
        "tick_size_status": tick_size_status,
        "live_execution": "BLOCKED",
    }, indent=2, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
