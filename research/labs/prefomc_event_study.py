#!/usr/bin/env python3
"""Research-only pre-FOMC event study. Never creates trade orders.

Inputs:
  bars.csv: timestamp,close. Timestamps should be ISO-8601; naive values are
            interpreted in America/New_York.
  fomc_events.csv: meeting_date (YYYY-MM-DD),announcement_at (ISO timestamp, required.
                   Use the actual policy-statement timestamp in ET or UTC).

The window ends 15 minutes before each actual statement timestamp and
starts at the same clock time on the previous valid US equity session. This
supports the historical 14:15 ET announcement convention (14:00 reference)
and later 14:00 ET convention (13:45 reference). Missing event timestamps are
excluded rather than assumed.

Example:
  python research/labs/prefomc_event_study.py --bars bars.csv --events fomc_events.csv \
    --round-trip-cost-bps 2 --out results.csv

Data must be sourced, licensed, timestamp-validated and versioned by the
operator. This script does not fetch data or certify the historical event list.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
NY = ZoneInfo("America/New_York")


def parse_timestamp(raw: str) -> datetime:
    value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=NY)
    return value.astimezone(NY)


def load_bars(path: Path) -> dict[datetime, float]:
    bars: dict[datetime, float] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"timestamp", "close"}.issubset(reader.fieldnames):
            raise ValueError("bars CSV requires timestamp,close columns")
        for row_num, row in enumerate(reader, start=2):
            ts = parse_timestamp(row["timestamp"])
            if ts.second or ts.microsecond:
                raise ValueError(f"bar timestamp must be minute-aligned (row {row_num})")
            close = float(row["close"])
            if not math.isfinite(close) or close <= 0:
                raise ValueError(f"close must be finite and positive (row {row_num})")
            if ts in bars:
                raise ValueError(f"duplicate timestamp: {ts.isoformat()}")
            bars[ts] = close
    if not bars:
        raise ValueError("no bars loaded")
    return bars


def load_events(path: Path) -> list[dict]:
    events = []
    seen: set[date] = set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"meeting_date", "announcement_at"}.issubset(reader.fieldnames):
            raise ValueError("events CSV requires meeting_date,announcement_at columns")
        for row_num, row in enumerate(reader, start=2):
            meeting_day = date.fromisoformat(row["meeting_date"].strip())
            if meeting_day in seen:
                raise ValueError(f"duplicate meeting date: {meeting_day}")
            seen.add(meeting_day)
            announcement = row.get("announcement_at", "").strip()
            if announcement:
                parse_timestamp(announcement)  # validate supplied timestamp
            events.append({"meeting_date": meeting_day, "announcement_at": announcement})
    return sorted(events, key=lambda x: x["meeting_date"])


def exact_close(bars: dict[datetime, float], day: date, at: time) -> tuple[datetime, float] | None:
    ts = datetime.combine(day, at, tzinfo=NY)
    value = bars.get(ts)
    return (ts, value) if value is not None else None


def run_study(bars: dict[datetime, float], events: list[dict], round_trip_cost_bps: float) -> list[dict]:
    if not math.isfinite(round_trip_cost_bps) or round_trip_cost_bps < 0:
        raise ValueError("round-trip cost must be finite and non-negative")

    # End 15 minutes before each actual statement timestamp. Statement time
    # changed from 14:15 ET to 14:00 ET during the historical sample.
    output = []
    previous_session_by_time: dict[time, dict[date, date]] = {}
    for event in events:
        d = event["meeting_date"]
        announcement_raw = str(event.get("announcement_at", "")).strip()
        base = {
            "meeting_date": d.isoformat(),
            "announcement_timestamp": announcement_raw,
            "reference_time_et": "",
            "entry_timestamp": "",
            "exit_timestamp": "",
            "entry_close": "",
            "exit_close": "",
            "gross_return": "",
            "gross_log_return": "",
            "round_trip_cost_bps": round_trip_cost_bps,
            "net_return": "",
            "net_log_return": "",
            "status": "",
        }
        if not announcement_raw:
            base["status"] = "MISSING_ANNOUNCEMENT_TIMESTAMP"
            output.append(base)
            continue

        announcement = parse_timestamp(announcement_raw)
        if announcement.date() != d:
            raise ValueError(
                f"announcement_at date {announcement.date()} does not match meeting_date {d}"
            )
        if announcement.second or announcement.microsecond:
            raise ValueError("announcement_at must be minute-aligned")

        reference_dt = announcement - timedelta(minutes=15)
        reference_time = reference_dt.time().replace(tzinfo=None)
        base["reference_time_et"] = reference_time.isoformat()

        # Infer available sessions only from days with the exact reference
        # minute. Validate the sample against an authoritative exchange calendar.
        if reference_time not in previous_session_by_time:
            session_days = sorted({
                ts.date() for ts in bars
                if ts.timetz().replace(tzinfo=None) == reference_time
            })
            previous_session_by_time[reference_time] = {
                session_days[i]: session_days[i - 1]
                for i in range(1, len(session_days))
            }
        previous_session = previous_session_by_time[reference_time]

        exit_ = exact_close(bars, d, reference_time)
        if exit_ is None:
            base["status"] = "MISSING_EXACT_REFERENCE_BAR"
            output.append(base)
            continue
        if d not in previous_session:
            base["status"] = "MISSING_EVENT_SESSION_OR_PRIOR_SESSION"
            output.append(base)
            continue

        entry_day = previous_session[d]
        entry = exact_close(bars, entry_day, reference_time)
        if entry is None:
            base["status"] = "MISSING_EXACT_REFERENCE_BAR"
            output.append(base)
            continue

        entry_ts, entry_price = entry
        exit_ts, exit_price = exit_
        gross_log_return = math.log(exit_price / entry_price)
        # A proportional cost is additive in log-return space. This remains a
        # flat cost assumption, not a broker-specific fill/spread simulation.
        cost_log_return = round_trip_cost_bps / 10_000.0
        net_log_return = gross_log_return - cost_log_return
        gross_return = math.exp(gross_log_return) - 1.0
        net_return = math.exp(net_log_return) - 1.0
        base.update({
            "entry_timestamp": entry_ts.isoformat(),
            "exit_timestamp": exit_ts.isoformat(),
            "entry_close": f"{entry_price:.10g}",
            "exit_close": f"{exit_price:.10g}",
            "gross_return": f"{gross_return:.10g}",
            "gross_log_return": f"{gross_log_return:.10g}",
            "net_return": f"{net_return:.10g}",
            "net_log_return": f"{net_log_return:.10g}",
            "status": "OK",
        })
        output.append(base)
    return output

def summarize(rows: list[dict]) -> dict:
    valid = [float(r["net_return"]) for r in rows if r["status"] == "OK"]
    log_valid = [float(r["net_log_return"]) for r in rows if r["status"] == "OK"]
    n = len(valid)
    mean = statistics.fmean(valid) if valid else None
    std = statistics.stdev(valid) if n > 1 else None
    t_stat = mean / (std / math.sqrt(n)) if mean is not None and std and std > 0 else None
    log_mean = statistics.fmean(log_valid) if log_valid else None
    log_std = statistics.stdev(log_valid) if n > 1 else None
    log_t_stat = (
        log_mean / (log_std / math.sqrt(n))
        if log_mean is not None and log_std and log_std > 0
        else None
    )
    equity = peak = 1.0
    max_drawdown = 0.0
    for ret in valid:
        equity *= 1 + ret
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak)
    wins = sum(x > 0 for x in valid)
    losses = sum(x < 0 for x in valid)
    gross_wins = sum(x for x in valid if x > 0)
    gross_losses = abs(sum(x for x in valid if x < 0))
    return {
        "schema": "aurelia.prefomc_event_study_summary.v1",
        "research_only": RESEARCH_ONLY,
        "capital_authority": CAPITAL_AUTHORITY,
        "live_execution": LIVE_EXECUTION,
        "events_total": len(rows),
        "events_valid": n,
        "events_excluded": len(rows) - n,
        "return_basis": "simple_return_with_log_return_fields",
        "mean_net_return": mean,
        "median_net_return": statistics.median(valid) if valid else None,
        "mean_net_log_return": log_mean,
        "median_net_log_return": statistics.median(log_valid) if log_valid else None,
        "win_rate": wins / n if n else None,
        "profit_factor": gross_wins / gross_losses if gross_losses else None,
        "compounded_return": equity - 1 if n else None,
        "max_drawdown": max_drawdown if n else None,
        "descriptive_t_stat": t_stat,
        "descriptive_log_return_t_stat": log_t_stat,
        "p_value": None,
        "p_value_note": "Not computed: use an appropriate small-sample/event-dependence inference procedure; do not treat the descriptive t-statistic as a validated significance test.",
        "exclusions": dict((status, sum(r["status"] == status for r in rows)) for status in sorted({r["status"] for r in rows if r["status"] != "OK"})),
        "limitations": [
            "Exact reference-minute sampling is not a fill simulation.",
            "Normalize bar timestamp conventions first; a bar-start timestamp paired with its close price is not the same as a price observed at that timestamp.",
            "Cost is a user-specified flat round-trip haircut, not verified historical spread or slippage.",
            "No risk-free adjustment, benchmark adjustment, dividends, or market-impact model is applied.",
            "Announcement timestamp must be independently verified for each event; reference time is 15 minutes before it.",
            "Available sessions are inferred from reference bars; validate against an authoritative US exchange calendar and complete-session data.",
            "This output is not a trade signal or evidence of deployable alpha.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars", required=True, type=Path)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--round-trip-cost-bps", type=float, default=0.0)
    parser.add_argument("--out", type=Path, default=Path("prefomc_event_results.csv"))
    parser.add_argument("--summary", type=Path, default=Path("prefomc_event_summary.json"))
    args = parser.parse_args()

    bars = load_bars(args.bars)
    events = load_events(args.events)
    rows = run_study(bars, events, args.round_trip_cost_bps)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [
            "meeting_date", "announcement_timestamp", "reference_time_et", "entry_timestamp",
            "exit_timestamp", "entry_close", "exit_close", "gross_return",
            "round_trip_cost_bps", "net_return", "status"
        ])
        writer.writeheader()
        writer.writerows(rows)
    summary = summarize(rows)
    summary["bars_sha256"] = hashlib.sha256(args.bars.read_bytes()).hexdigest()
    summary["events_sha256"] = hashlib.sha256(args.events.read_bytes()).hexdigest()
    summary["bar_count"] = len(bars)
    summary["event_file_count"] = len(events)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["events_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
