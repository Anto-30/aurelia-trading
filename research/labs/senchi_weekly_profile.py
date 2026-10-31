from __future__ import annotations

"""Deterministic Senchi weekly-profile research; never an execution signal.

The research variant uses complete UTC-aligned 1D candles and the prior
Monday-Sunday UTC calendar week as its objective external range. Monday
reversals are evaluated against Tuesday's OHLC path. If both the target and
Monday-extreme invalidation are touched in the same Tuesday candle, event order
is unknown from daily OHLC and the observation is classified as ambiguous.
"""

import argparse
import csv
import hashlib
import json
import math
import os
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
MODEL_ID = "SENCHI_PWH_PWL_WEEKLY_PROFILE"
MODEL_VERSION = "0.1.0"

MONDAY_ACTIONS = (
    "BULLISH_REVERSAL",
    "BEARISH_REVERSAL",
    "BULLISH_EXPANSION",
    "BEARISH_EXPANSION",
    "INSIDE",
    "COMPLEX_DUAL_SWEEP",
    "NO_PRIOR_WEEK_RANGE",
)
TUESDAY_OUTCOMES = (
    "TARGET_FIRST",
    "STOP_FIRST",
    "TARGET_GAP_AT_OPEN",
    "STOP_GAP_AT_OPEN",
    "AMBIGUOUS_BOTH_TOUCHED",
    "NO_HIT",
    "MISSING_TUESDAY",
    "NOT_A_REVERSAL",
)


@dataclass(frozen=True)
class DailyBar:
    timestamp_utc: str
    open: float
    high: float
    low: float
    close: float

    def parsed_timestamp(self) -> datetime:
        raw = self.timestamp_utc.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            raise ValueError("DAILY_BAR_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
        return parsed.astimezone(timezone.utc)

    @property
    def session_date_utc(self) -> date:
        return self.parsed_timestamp().date()


@dataclass(frozen=True)
class WeeklyRange:
    week_start: str
    week_end: str
    high: float
    low: float
    source_bar_count: int


@dataclass(frozen=True)
class MondaySignal:
    monday_date: str
    action: str
    pwh: float | None
    pwl: float | None
    monday_open: float
    monday_high: float
    monday_low: float
    monday_close: float
    target: float | None
    invalidation: float | None


@dataclass(frozen=True)
class TuesdayOutcome:
    monday_date: str
    action: str
    outcome: str
    target: float | None
    invalidation: float | None
    tuesday_open: float | None
    tuesday_high: float | None
    tuesday_low: float | None
    tuesday_close: float | None
    target_touched: bool | None
    invalidation_touched: bool | None


def _finite(value: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"NON_FINITE_OHLC_VALUE:{name}")
    return number


def canonical_json_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_daily_bars(
    bars: Sequence[DailyBar], *, require_contiguous_days: bool = True
) -> None:
    if not bars:
        raise ValueError("DAILY_DATASET_EMPTY")
    previous: datetime | None = None
    seen: set[datetime] = set()
    for bar in bars:
        stamp = bar.parsed_timestamp()
        if stamp in seen:
            raise ValueError(f"DUPLICATE_DAILY_TIMESTAMP:{bar.timestamp_utc}")
        seen.add(stamp)
        if stamp.hour or stamp.minute or stamp.second or stamp.microsecond:
            raise ValueError(
                f"DAILY_CANDLE_NOT_UTC_MIDNIGHT_ALIGNED:{bar.timestamp_utc}"
            )
        if previous is not None:
            delta = (stamp - previous).total_seconds()
            if delta <= 0:
                raise ValueError("DAILY_BARS_NOT_STRICTLY_CHRONOLOGICAL")
            if require_contiguous_days and delta != 86400:
                raise ValueError("DAILY_DATASET_HAS_GAP_OR_IRREGULAR_INTERVAL")
        values = {
            "open": _finite(bar.open, "open"),
            "high": _finite(bar.high, "high"),
            "low": _finite(bar.low, "low"),
            "close": _finite(bar.close, "close"),
        }
        if any(value <= 0 for value in values.values()):
            raise ValueError("OHLC_PRICES_MUST_BE_POSITIVE")
        if values["high"] < max(values["open"], values["close"]):
            raise ValueError("OHLC_HIGH_BELOW_OPEN_OR_CLOSE")
        if values["low"] > min(values["open"], values["close"]):
            raise ValueError("OHLC_LOW_ABOVE_OPEN_OR_CLOSE")
        if values["high"] < values["low"]:
            raise ValueError("OHLC_HIGH_BELOW_LOW")
        previous = stamp


def load_daily_csv(path: str | Path) -> list[DailyBar]:
    required = {"timestamp_utc", "open", "high", "low", "close"}
    bars: list[DailyBar] = []
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV_MUST_CONTAIN:" + ",".join(sorted(required)))
        for line_number, row in enumerate(reader, start=2):
            try:
                bars.append(DailyBar(
                    timestamp_utc=str(row["timestamp_utc"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                ))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"CSV_INVALID_ROW:{line_number}:{exc}") from exc
    # Preserve source order so chronology defects are rejected, not silently repaired.
    validate_daily_bars(bars)
    return bars


def _monday_of(value: date) -> date:
    return value - timedelta(days=value.weekday())


def build_completed_weekly_ranges(
    bars: Sequence[DailyBar], *, require_full_week: bool = True
) -> dict[date, WeeklyRange]:
    """Return ranges keyed by the Monday starting each fully observed week."""
    weeks: dict[date, list[DailyBar]] = {}
    for bar in bars:
        start = _monday_of(bar.session_date_utc)
        weeks.setdefault(start, []).append(bar)

    result: dict[date, WeeklyRange] = {}
    for week_start, rows in weeks.items():
        expected_dates = [week_start + timedelta(days=offset) for offset in range(7)]
        present_dates = {row.session_date_utc for row in rows}
        if require_full_week and not all(day in present_dates for day in expected_dates):
            continue
        # Week aggregates are computed only from that week, never from a rolling
        # five-row window that can cross a holiday/week boundary.
        result[week_start] = WeeklyRange(
            week_start=week_start.isoformat(),
            week_end=(week_start + timedelta(days=6)).isoformat(),
            high=max(row.high for row in rows),
            low=min(row.low for row in rows),
            source_bar_count=len(rows),
        )
    return result


def classify_monday_signals(
    bars: Sequence[DailyBar], *, require_full_prior_week: bool = True
) -> list[MondaySignal]:
    validate_daily_bars(bars)
    ranges = build_completed_weekly_ranges(bars, require_full_week=require_full_prior_week)
    signals: list[MondaySignal] = []

    for bar in bars:
        monday = bar.session_date_utc
        if monday.weekday() != 0:
            continue
        prior_week_start = monday - timedelta(days=7)
        prior_range = ranges.get(prior_week_start)
        if prior_range is None:
            signals.append(MondaySignal(
                monday_date=monday.isoformat(), action="NO_PRIOR_WEEK_RANGE",
                pwh=None, pwl=None, monday_open=bar.open, monday_high=bar.high,
                monday_low=bar.low, monday_close=bar.close,
                target=None, invalidation=None,
            ))
            continue

        pwh, pwl = prior_range.high, prior_range.low
        close_inside = pwl <= bar.close <= pwh
        swept_high = bar.high > pwh
        swept_low = bar.low < pwl

        # Expansion takes precedence whenever the daily close is outside the
        # previous completed week's range, even if the opposite boundary wicked.
        if bar.close > pwh:
            action = "BULLISH_EXPANSION"
        elif bar.close < pwl:
            action = "BEARISH_EXPANSION"
        elif close_inside and swept_low and swept_high:
            action = "COMPLEX_DUAL_SWEEP"
        elif close_inside and swept_low:
            action = "BULLISH_REVERSAL"
        elif close_inside and swept_high:
            action = "BEARISH_REVERSAL"
        elif close_inside and not swept_low and not swept_high:
            action = "INSIDE"
        else:
            action = "COMPLEX_DUAL_SWEEP"

        bullish = action == "BULLISH_REVERSAL"
        bearish = action == "BEARISH_REVERSAL"
        signals.append(MondaySignal(
            monday_date=monday.isoformat(), action=action, pwh=pwh, pwl=pwl,
            monday_open=bar.open, monday_high=bar.high, monday_low=bar.low,
            monday_close=bar.close,
            target=pwh if bullish else (pwl if bearish else None),
            invalidation=bar.low if bullish else (bar.high if bearish else None),
        ))
    return signals


def measure_tuesday_outcomes(
    bars: Sequence[DailyBar], signals: Sequence[MondaySignal]
) -> list[TuesdayOutcome]:
    validate_daily_bars(bars)
    by_date = {bar.session_date_utc: bar for bar in bars}
    outcomes: list[TuesdayOutcome] = []
    for signal in signals:
        if signal.action not in ("BULLISH_REVERSAL", "BEARISH_REVERSAL"):
            outcomes.append(TuesdayOutcome(
                monday_date=signal.monday_date, action=signal.action,
                outcome="NOT_A_REVERSAL", target=signal.target,
                invalidation=signal.invalidation, tuesday_open=None,
                tuesday_high=None, tuesday_low=None, tuesday_close=None,
                target_touched=None, invalidation_touched=None,
            ))
            continue

        monday = date.fromisoformat(signal.monday_date)
        tuesday = by_date.get(monday + timedelta(days=1))
        if tuesday is None:
            outcomes.append(TuesdayOutcome(
                monday_date=signal.monday_date, action=signal.action,
                outcome="MISSING_TUESDAY", target=signal.target,
                invalidation=signal.invalidation, tuesday_open=None,
                tuesday_high=None, tuesday_low=None, tuesday_close=None,
                target_touched=None, invalidation_touched=None,
            ))
            continue

        assert signal.target is not None and signal.invalidation is not None
        bullish = signal.action == "BULLISH_REVERSAL"
        if bullish:
            target_gap = tuesday.open >= signal.target
            stop_gap = tuesday.open <= signal.invalidation
            target_touched = tuesday.high >= signal.target
            invalidation_touched = tuesday.low <= signal.invalidation
        else:
            target_gap = tuesday.open <= signal.target
            stop_gap = tuesday.open >= signal.invalidation
            target_touched = tuesday.low <= signal.target
            invalidation_touched = tuesday.high >= signal.invalidation

        if target_gap:
            outcome = "TARGET_GAP_AT_OPEN"
        elif stop_gap:
            outcome = "STOP_GAP_AT_OPEN"
        elif target_touched and invalidation_touched:
            outcome = "AMBIGUOUS_BOTH_TOUCHED"
        elif target_touched:
            outcome = "TARGET_FIRST"
        elif invalidation_touched:
            outcome = "STOP_FIRST"
        else:
            outcome = "NO_HIT"

        outcomes.append(TuesdayOutcome(
            monday_date=signal.monday_date, action=signal.action,
            outcome=outcome, target=signal.target,
            invalidation=signal.invalidation, tuesday_open=tuesday.open,
            tuesday_high=tuesday.high, tuesday_low=tuesday.low,
            tuesday_close=tuesday.close, target_touched=target_touched,
            invalidation_touched=invalidation_touched,
        ))
    return outcomes


def wilson_interval(
    successes: int, trials: int, *, z: float = 1.959963984540054
) -> tuple[float, float] | None:
    """Return a binomial IID interval; it is not dependence-aware time-series inference."""
    if trials <= 0:
        return None
    if successes < 0 or successes > trials:
        raise ValueError("BINOMIAL_COUNTS_INVALID")
    p = successes / trials
    denominator = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denominator
    radius = (
        z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * trials)) / trials)
    ) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def summarize_outcomes(outcomes: Sequence[TuesdayOutcome]) -> dict[str, object]:
    reversal_rows = [
        row for row in outcomes
        if row.action in ("BULLISH_REVERSAL", "BEARISH_REVERSAL")
    ]
    counts = Counter(row.outcome for row in reversal_rows)
    target_first = counts["TARGET_FIRST"] + counts["TARGET_GAP_AT_OPEN"]
    stop_first = counts["STOP_FIRST"] + counts["STOP_GAP_AT_OPEN"]
    resolved = target_first + stop_first
    target_touched = sum(row.target_touched is True for row in reversal_rows)
    return {
        "monday_reversal_setups": len(reversal_rows),
        "tuesday_outcome_counts": {key: counts.get(key, 0) for key in TUESDAY_OUTCOMES},
        "target_touched_count_including_ambiguous": target_touched,
        "target_touched_rate_all_setups": (
            target_touched / len(reversal_rows) if reversal_rows else None
        ),
        "target_first_count_including_open_gaps": target_first,
        "stop_first_count_including_open_gaps": stop_first,
        "resolved_event_count": resolved,
        "target_first_rate_on_resolved_events": (
            target_first / resolved if resolved else None
        ),
        "target_first_wilson_95pct_interval_iid_diagnostic_only": (
            list(wilson_interval(target_first, resolved)) if resolved else None
        ),
        "unresolved_or_unreached_count": (
            counts["AMBIGUOUS_BOTH_TOUCHED"] + counts["NO_HIT"] + counts["MISSING_TUESDAY"]
        ),
        "interpretation": (
            "Descriptive daily-OHLC path study only. No entry, spread, slippage, stop-fill, "
            "or M1/M15 execution model is represented. Ambiguous same-day double touches "
            "are excluded from resolved-event rate and must not be counted as wins. The Wilson "
            "interval is an IID binomial diagnostic only and ignores serial dependence."
        ),
    }


def build_research_report(
    bars: Sequence[DailyBar], *, symbol: str, source: str,
    input_sha256: str | None = None, code_commit: str | None = None,
    calendar_basis: str = "UTC_86400S_DAILY_CANDLES",
) -> dict[str, object]:
    validate_daily_bars(bars)
    signals = classify_monday_signals(bars)
    outcomes = measure_tuesday_outcomes(bars, signals)
    monday_counts = Counter(row.action for row in signals)
    records = {
        "monday_signals": [asdict(row) for row in signals],
        "tuesday_outcomes": [asdict(row) for row in outcomes],
    }
    report: dict[str, object] = {
        "schema": "aurelia.senchi.weekly_profile_research.v1",
        "research_only": True,
        "capital_authority": False,
        "live_execution": False,
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION,
        "symbol": symbol,
        "source": source,
        "calendar_basis": calendar_basis,
        "weekly_range_definition": "previous completed Monday-Sunday UTC calendar week",
        "monday_reversal_definition": (
            "strict high > PWH or low < PWL wick sweep; close must finish inside inclusive range; "
            "dual sweep is complex; close outside always classifies as expansion"
        ),
        "tuesday_invalidation_definition": "Monday reversal candle extreme",
        "data": {
            "bar_count": len(bars),
            "first_timestamp_utc": bars[0].parsed_timestamp().isoformat().replace("+00:00", "Z"),
            "last_timestamp_utc": bars[-1].parsed_timestamp().isoformat().replace("+00:00", "Z"),
            "input_sha256": input_sha256,
        },
        "code_commit": code_commit or os.getenv("GITHUB_SHA", "UNKNOWN"),
        "monday_action_counts": {key: monday_counts.get(key, 0) for key in MONDAY_ACTIONS},
        "outcomes": summarize_outcomes(outcomes),
        "records": records,
        "limitations": [
            "This experiment uses UTC day/week boundaries, not an ICT New York-close daily candle profile.",
            "The daily OHLC path cannot order target and invalidation touches within the same candle; these cases are ambiguous.",
            "Daily target-touch outcomes are not tradable P&L and do not model T4F M15/M1 entries.",
            "No costs are applied; instrument-specific costs are mandatory before tradability claims.",
            "A rolling five-row PWH/PWL calculation is deliberately not used; the prior completed UTC week must be present.",
        ],
        "trade_signal": False,
        "execution_authorized": False,
    }
    report["report_sha256"] = canonical_json_hash(report)
    return report


def run_csv_research(
    input_path: str | Path, output_path: str | Path, *, symbol: str,
    source: str, calendar_basis: str = "UTC_86400S_DAILY_CANDLES",
) -> dict[str, object]:
    bars = load_daily_csv(input_path)
    report = build_research_report(
        bars, symbol=symbol, source=source, input_sha256=sha256_file(input_path),
        calendar_basis=calendar_basis,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Research-only Senchi weekly profile measurement")
    parser.add_argument("--input", required=True, help="CSV with timestamp_utc,open,high,low,close")
    parser.add_argument("--output", required=True, help="Output JSON report path")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--source", required=True, help="Exact data-source/provenance label")
    parser.add_argument("--calendar-basis", default="UTC_86400S_DAILY_CANDLES")
    args = parser.parse_args(argv)
    report = run_csv_research(
        args.input, args.output, symbol=args.symbol, source=args.source,
        calendar_basis=args.calendar_basis,
    )
    summary = report["outcomes"]
    print(json.dumps({
        "status": "RESEARCH_COMPLETE",
        "research_only": True,
        "symbol": report["symbol"],
        "data": report["data"],
        "monday_action_counts": report["monday_action_counts"],
        "outcomes": summary,
        "report_sha256": report["report_sha256"],
        "execution_authorized": False,
    }, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
