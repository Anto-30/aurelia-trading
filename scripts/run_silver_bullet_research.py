#!/usr/bin/env python3
"""Fetch and evaluate the frozen ICT Silver Bullet research hypothesis.

Research-only. Public Deriv market data only. No account login, proposals,
orders, broker execution, production deployment, or capital authorization.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import sys
from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from research.labs.silver_bullet import (
    BacktestConfig,
    DEFAULT_WINDOWS,
    DerivCandleClient,
    run_backtest,
    validate_complete_coverage,
)

NY = ZoneInfo("America/New_York")
DEFAULT_START = date(2024, 1, 1)
DEFAULT_END = date(2026, 10, 31)


def local_midnight_epoch(value: date) -> int:
    local = datetime.combine(value, time.min, tzinfo=NY)
    roundtrip = local.astimezone(timezone.utc).astimezone(NY).replace(tzinfo=None)
    if roundtrip != local.replace(tzinfo=None):
        raise ValueError(f"NY_MIDNIGHT_NOT_REPRESENTABLE:{value.isoformat()}")
    return int(local.timestamp())


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read¶»§q«^