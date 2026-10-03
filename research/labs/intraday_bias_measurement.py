from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False

CLASSIFICATIONS = (
    "NO_EVIDENCE", "INSUFFICIENT_SAMPLE", "IN_SAMPLE_ONLY", "OOS_FAILED",
    "UNSTABLE", "COST_ERODED", "REGIME_CONDITIONAL",
    "ROBUST_BULLISH_PRIOR", "ROBUST_BEARISH_PRIOR",
    "INVALIDATED", "STALE_REQUIRES_REVALIDATION",
)

def _finite(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("non-finite numeric value")
    return float(value)

def _normal_two_sided_p(z: float) -> float:
    return max(0.0, min(1.0, math.erfc(abs(z) / math.sqrt(2.0))))

def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    if not p_values:
        return []
    if any((not math.isfinite(p)) or p < 0 or p > 1 for p in p_values):
        raise ValueError("p-values must be finite and in [0, 1]")
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [1.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        idx, p = indexed[rank - 1]
        running = min(running, p * m / rank)
        adjusted[idx] = min(1.0, running)
    return adjusted

@dataclass(frozen=True)
class Bar:
    timestamp_utc: str
    open: float
    high: float | None = None
    low: float | None = None
    close: float | None = None

    def parsed_timestamp(self) -> datetime:
        dt = datetime.fromisoformat(self.timestamp_utc.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("bar timestamp must be timezone-aware")
        return dt.astimezone(timezone.utc)

@dataclass(frozen=True)
class ForwardObservation:
    symbol: str
    hour_bucket_utc: int
    signal_timestamp_utc: str
    entry_timestamp_utc: str
    exit_timestamp_utc: str
    entry_open: float
    exit_open: float
    raw_return: float

@dataclass(frozen=True)
class Statistics:
    n: int
    mean_return: float | None
    median_return: float | None
    win_rate: float | None
    expectancy: float | None
    std_dev: float | None
    downside_dev: float | None
    profit_factor: float | None
    cumulative_return: float | None
    max_drawdown: float | None
    t_stat: float | None
    p_value: float | None

def build_hourly_bars_from_ticks(ticks: Iterable[dict]) -> list[Bar]:
    buckets: dict[datetime, list[float]] = {}
    for tick in ticks:
        dt = datetime.fromisoformat(str(tick["timestamp_utc"]).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("tick timestamp must be timezone-aware")
        dt = dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        price = _finite(float(tick["price"]))
        buckets.setdefault(dt, []).append(price)
    bars: list[Bar] = []
    for dt in sorted(buckets):
        prices = buckets[dt]
        bars.append(Bar(
            timestamp_utc=dt.isoformat().replace("+00:00", "Z"),
            open=prices[0], high=max(prices), low=min(prices), close=prices[-1],
        ))
    return bars

def validate_hourly_bars(bars: Sequence[Bar]) -> None:
    previous: datetime | None = None
    seen: set[str] = set()
    for bar in bars:
        dt = bar.parsed_timestamp()
        key = dt.isoformat()
        if key in seen:
            raise ValueError("duplicate hourly bar timestamp")
        seen.add(key)
        if previous is not None and (dt - previous).total_seconds() != 3600:
            raise ValueError("hourly bars contain a gap or irregular interval")
        _finite(float(bar.open))
        previous = dt

def generate_hourly_observations(bars: Sequence[Bar], symbol: str) -> list[ForwardObservation]:
    validate_hourly_bars(bars)
    observations: list[ForwardObservation] = []
    for i in range(len(bars) - 2):
        signal, entry, exit_bar = bars[i], bars[i + 1], bars[i + 2]
        entry_open, exit_open = _finite(float(entry.open)), _finite(float(exit_bar.open))
        observations.append(ForwardObservation(
            symbol=symbol,
            hour_bucket_utc=signal.parsed_timestamp().hour,
            signal_timestamp_utc=signal.parsed_timestamp().isoformat().replace("+00:00", "Z"),
            entry_timestamp_utc=entry.parsed_timestamp().isoformat().replace("+00:00", "Z"),
            exit_timestamp_utc=exit_bar.parsed_timestamp().isoformat().replace("+00:00", "Z"),
            entry_open=entry_open, exit_open=exit_open,
            raw_return=_finite((exit_open - entry_open) / entry_open),
        ))
    return observations

def calculate_statistics(returns: Sequence[float]) -> Statistics:
    values = [_finite(float(x)) for x in returns]
    n = len(values)
    if not n:
        return Statistics(n=0, mean_return=None, median_return=None, win_rate=None, expectancy=None,
                          std_dev=None, downside_dev=None, profit_factor=None,
                          cumulative_return=None, max_drawdown=None, t_stat=None, p_value=None)
    mean = statistics.fmean(values)
    median = statistics.median(values)
    wins = [x for x in values if x > 0]
    losses = [x for x in values if x < 0]
    std = statistics.stdev(values) if n > 1 else None
    downside = math.sqrt(statistics.fmean([min(0.0, x) ** 2 for x in values]))
    gross_win, gross_loss = sum(wins), abs(sum(losses))
    pf = gross_win / gross_loss if gross_loss > 0 else (math.inf if gross_win > 0 else None)
    equity, peak, max_dd = 1.0, 1.0, 0.0
    for x in values:
        equity *= 1.0 + x
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    t_stat = mean / (std / math.sqrt(n)) if std and std > 0 else None
    p_value = _normal_two_sided_p(t_stat) if t_stat is not None else None
    return Statistics(n=n, mean_return=mean, median_return=median, win_rate=len(wins)/n,
                      expectancy=mean, std_dev=std, downside_dev=downside,
                      profit_factor=pf, cumulative_return=equity-1.0, max_drawdown=max_dd,
                      t_stat=t_stat, p_value=p_value)

def sha256_json(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def bias_passport(*, symbol: str, timezone_name: str, timeframe: str, hour_bucket_utc: int,
                  observations: Sequence[ForwardObservation],
                  is_observations: Sequence[ForwardObservation],
                  oos_observations: Sequence[ForwardObservation],
                  adjusted_q_value: float | None = None,
                  classification: str = "NO_EVIDENCE",
                  data_version: str = "unknown",
                  research_generation: str = "unknown") -> dict:
    if classification not in CLASSIFICATIONS:
        raise ValueError("unknown classification")
    if not 0 <= hour_bucket_utc <= 23:
        raise ValueError("hour bucket must be 0..23")
    passport = {
        "schema": "aurelia.intraday_bias_passport.v1",
        "research_only": True, "capital_authority": False, "live_execution": False,
        "symbol": symbol, "timezone": timezone_name, "timeframe": timeframe,
        "hour_bucket_utc": hour_bucket_utc,
        "statistics": asdict(calculate_statistics([o.raw_return for o in observations])),
        "in_sample": asdict(calculate_statistics([o.raw_return for o in is_observations])),
        "out_of_sample": asdict(calculate_statistics([o.raw_return for o in oos_observations])),
        "multiple_testing": {
            "method": "benjamini_hochberg" if adjusted_q_value is not None else "pending",
            "adjusted_q_value": adjusted_q_value,
            "interpretation": "screening evidence only; not proof of tradability",
        },
        "classification": classification, "trade_signal": False,
        "data_version": data_version, "research_generation": research_generation,
        "limitations": [
            "Raw drift excludes transaction costs and execution friction.",
            "Time-of-day evidence is a research prior, never execution authorization.",
            "The p-value is a screening statistic and does not establish IID returns.",
        ],
    }
    passport["passport_hash"] = sha256_json(passport)
    return passport

def bias_to_execution_command(*_args, **_kwargs):
    raise RuntimeError("Intraday Bias is research-only and cannot authorize execution")
