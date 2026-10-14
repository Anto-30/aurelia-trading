"""Deterministic calendar-month walk-forward split planning for research.

This helper creates split boundaries only. It does not fit a model, score a
strategy, establish instrument economics, or qualify capital. Callers must
prove the input dataset fully covers each requested UTC month and must keep
all preprocessing/model fitting inside the training interval.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import re


_MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def _parse_month(value: str) -> datetime:
    match = _MONTH_RE.fullmatch(value or "")
    if not match:
        raise ValueError("MONTH_MUST_USE_YYYY_MM")
    year, month = int(match.group(1)), int(match.group(2))
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _add_months(value: datetime, months: int) -> datetime:
    absolute = value.year * 12 + (value.month - 1) + months
    year, zero_month = divmod(absolute, 12)
    return datetime(year, zero_month + 1, 1, tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class WalkForwardSplit:
    """Half-open UTC windows; purge observations are never fit or scored."""

    split_id: str
    train_start_utc: str
    train_end_exclusive_utc: str
    purge_start_utc: str
    purge_end_exclusive_utc: str
    oos_start_utc: str
    oos_end_exclusive_utc: str
    nominal_in_sample_months: int
    out_of_sample_months: int
    step_months: int
    purge_days: int

    def as_payload(self) -> dict[str, object]:
        return asdict(self)


def monthly_walk_forward_splits(
    start_month: str,
    end_month_exclusive: str,
    *,
    in_sample_months: int = 3,
    out_of_sample_months: int = 1,
    step_months: int = 1,
    purge_days: int = 0,
) -> list[WalkForwardSplit]:
    """Build rolling monthly split plans over the half-open requested range.

    Calendar boundaries are UTC. The nominal in-sample interval is first
    reserved as a whole; the last purge_days before OOS are then excluded
    from fitting and scoring. Incomplete trailing OOS windows are omitted.
    """
    start = _parse_month(start_month)
    end = _parse_month(end_month_exclusive)
    if end <= start:
        raise ValueError("END_MONTH_MUST_FOLLOW_START_MONTH")
    if in_sample_months < 1 or out_of_sample_months < 1 or step_months < 1:
        raise ValueError("WALK_FORWARD_MONTH_COUNTS_MUST_BE_POSITIVE")
    if purge_days < 0:
        raise ValueError("PURGE_DAYS_MUST_NOT_BE_NEGATIVE")
    if purge_days >= in_sample_months * 28:
        raise ValueError("PURGE_WINDOW_TOO_LARGE")

    splits: list[WalkForwardSplit] = []
    cursor = start
    while True:
        oos_start = _add_months(cursor, in_sample_months)
        oos_end = _add_months(oos_start, out_of_sample_months)
        if oos_end > end:
            break

        train_end = oos_start - timedelta(days=purge_days)
        if train_end <= cursor:
            raise ValueError("PURGE_WINDOW_REMOVES_TRAINING_INTERVAL")
        label = f"{cursor:%Y-%m}_IS{in_sample_months}M_OOS{oos_start:%Y-%m}"
        splits.append(
            WalkForwardSplit(
                split_id=label,
                train_start_utc=_iso(cursor),
                train_end_exclusive_utc=_iso(train_end),
                purge_start_utc=_iso(train_end),
                purge_end_exclusive_utc=_iso(oos_start),
                oos_start_utc=_iso(oos_start),
                oos_end_exclusive_utc=_iso(oos_end),
                nominal_in_sample_months=in_sample_months,
                out_of_sample_months=out_of_sample_months,
                step_months=step_months,
                purge_days=purge_days,
            )
        )
        cursor = _add_months(cursor, step_months)
    return splits


def validate_split(split: WalkForwardSplit) -> None:
    """Fail closed if split boundaries are malformed or overlap."""
    values = (
        split.train_start_utc,
        split.train_end_exclusive_utc,
        split.purge_start_utc,
        split.purge_end_exclusive_utc,
        split.oos_start_utc,
        split.oos_end_exclusive_utc,
    )
    parsed: list[datetime] = []
    for value in values:
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("SPLIT_TIMESTAMP_INVALID") from exc
        if stamp.tzinfo is None:
            raise ValueError("SPLIT_TIMESTAMP_MUST_BE_AWARE")
        parsed.append(stamp.astimezone(timezone.utc))
    train_start, train_end, purge_start, purge_end, oos_start, oos_end = parsed
    if not (train_start < train_end == purge_start <= purge_end == oos_start < oos_end):
        raise ValueError("WALK_FORWARD_WINDOWS_OVERLAP_OR_REVERSED")
    if split.nominal_in_sample_months < 1 or split.out_of_sample_months < 1 or split.step_months < 1:
        raise ValueError("WALK_FORWARD_MONTH_COUNTS_MUST_BE_POSITIVE")
    if split.purge_days < 0:
        raise ValueError("PURGE_DAYS_MUST_NOT_BE_NEGATIVE")
