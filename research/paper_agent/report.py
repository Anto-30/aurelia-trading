"""Evidence-only daily/nightly review report for the Deriv research paper gate.

This report does not estimate PnL from intents. A PAPER_INTENT is a "would trade"
decision, not a fill. Calibration metrics remain unavailable until the ledger
contains verified, outcome-labelled observations from a separately approved
paper contract simulator.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


def schema_diff(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> dict[str, Any]:
    """Report top-level schema changes; never rewrites or promotes a schema."""
    previous = dict(previous or {})
    current = dict(current)
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed = []
    for key in sorted(set(previous) & set(current)):
        if type(previous[key]).__name__ != type(current[key]).__name__:
            changed.append({
                "field": key,
                "previous_type": type(previous[key]).__name__,
                "current_type": type(current[key]).__name__,
            })
        elif previous[key] != current[key]:
            changed.append({
                "field": key,
                "previous_type": type(previous[key]).__name__,
                "current_type": type(current[key]).__name__,
                "value_changed": True,
            })
    return {"added": added, "removed": removed, "changed": changed}


def _parse_event(row: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(str(row.get("payload_json", "{}")))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None, "PAYLOAD_JSON_INVALID"
    if not isinstance(payload, dict):
        return None, "PAYLOAD_ROOT_NOT_OBJECT"
    return payload, None


def build_nightly_report(
    events: Sequence[Mapping[str, Any]],
    *,
    generated_at_utc: datetime | None = None,
    schema_previous: Mapping[str, Any] | None = None,
    schema_current: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize the trailing UTC 24h of evidence without inventing fills or PnL."""
    now = generated_at_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("REPORT_TIMEZONE_REQUIRED")
    now = now.astimezone(timezone.utc)
    start = now - timedelta(hours=24)

    recent: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    malformed = 0
    for row in events:
        try:
            stamp = datetime.fromisoformat(str(row.get("occurred_at_utc", "")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            malformed += 1
            continue
        if stamp.tzinfo is None:
            malformed += 1
            continue
        stamp = stamp.astimezone(timezone.utc)
        if not start <= stamp <= now:
            continue
        payload, error = _parse_event(row)
        if error:
            malformed += 1
            continue
        recent.append((row, payload))

    counts = Counter(str(row.get("event_type", "UNKNOWN")) for row, _ in recent)
    miss_reasons: Counter[str] = Counter()
    regime_counts: Counter[str] = Counter()
    for row, payload in recent:
        if row.get("event_type") == "MISSED_SIGNAL":
            reason = str(payload.get("reason") or ",".join(payload.get("reasons", [])) or "UNSPECIFIED")
            miss_reasons[reason] += 1
        decision = payload.get("decision")
        if isinstance(decision, dict):
            regime = str(decision.get("regime") or "UNKNOWN")
            regime_counts[regime] += 1

    return {
        "schema": "aurelia.paper_agent.nightly_review.v1",
        "generated_at_utc": now.isoformat(),
        "window_start_utc": start.isoformat(),
        "window_end_utc": now.isoformat(),
        "scope": "RESEARCH_ONLY_PAPER_DECISIONS",
        "orders_submitted": 0,
        "confirmed_fills": 0,
        "simulated_pnl": None,
        "net_expectancy": None,
        "brier_score": None,
        "calibration_status": "NOT_MEASURABLE_WITHOUT_VERIFIED_OUTCOME_LABELS",
        "performance_claims_permitted": False,
        "event_counts_24h": dict(sorted(counts.items())),
        "paper_intents_are_not_fills": True,
        "missed_signal_reasons": dict(sorted(miss_reasons.items())),
        "regime_observation_counts": dict(sorted(regime_counts.items())),
        "malformed_events_skipped": malformed,
        "schema_diff": schema_diff(schema_previous, schema_current or {}),
        "promotion_recommendation": "NO_PROMOTION_WITHOUT_OOS_COST_AND_OUTCOME_EVIDENCE",
        "capital_authority": False,
        "live_execution_authorized": False,
    }


def read_events_readonly(database_path: str | Path) -> list[dict[str, Any]]:
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError("PAPER_LEDGER_NOT_FOUND")
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5.0)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """SELECT sequence, event_id, occurred_at_utc, event_type, payload_json,
                      payload_sha256, previous_hash, event_hash
               FROM paper_events ORDER BY sequence ASC"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def write_report_atomic(output_path: str | Path, report: Mapping[str, Any]) -> Path:
    target = Path(output_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(report), sort_keys=True, indent=2, allow_nan=False) + "\n"
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with open(fd, "w", encoding="utf-8", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            import os
            os.fsync(handle.fileno())
        Path(name).replace(target)
    except Exception:
        try:
            Path(name).unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite paper_event ledger path")
    parser.add_argument("--output", required=True, help="Nightly report JSON output path")
    args = parser.parse_args(argv)
    events = read_events_readonly(args.db)
    report = build_nightly_report(events)
    path = write_report_atomic(args.output, report)
    print(json.dumps({
        "report_path": str(path),
        "event_count_24h": sum(report["event_counts_24h"].values()),
        "simulated_pnl": None,
        "brier_score": None,
        "live_execution_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
