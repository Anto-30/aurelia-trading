"""Research-only, deterministic ICT Silver Bullet model. No order routing or capital authority."""
from __future__ import annotations

import asyncio
from bisect import bisect_left, bisect_right
import hashlib
import json
import math
import statistics
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from runtime.adapters.deriv_adapter import PUBLIC_WS_URL
from runtime.adapters.deriv_ws import DerivWebSocketTransport

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
STRATEGY_ID = "ICT_SILVER_BULLET"
STRATEGY_VERSION = "0.1.0"
NY_TIMEZONE = "America/New_York"


@dataclass(frozen=True)
class Candle:
    epoch: int
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self):
        if isinstance(self.epoch, bool) or int(self.epoch) != self.epoch or self.epoch < 0:
            raise ValueError("CANDLE_EPOCH_INVALID")
        prices = (self.open, self.high, self.low, self.close)
        if not all(math.isfinite(float(x)) and float(x) > 0 for x in prices):
            raise ValueError("CANDLE_PRICES_MUST_BE_FINITE_AND_POSITIVE")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("CANDLE_HIGH_INCONSISTENT")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("CANDLE_LOW_INCONSISTENT")


@dataclass(frozen=True)
class S¶»§q«^