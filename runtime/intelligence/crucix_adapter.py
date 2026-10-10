"""Fail-closed, read-only adapter for optional Crucix intelligence sidecars.

This module deliberately emits metadata-only advisories. It does not create trade
signals, decide direction, alter risk limits, or grant capital authority.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_TIMEOUT_SECONDS = 3.0
DEFAULT_MAX_RESPONSE_BYTES = 1_500_000
DEFAULT_MAX_DATA_AGE_SECONDS = 900.0
_ALLOWED_SCHEMES = frozenset({"http", "https"})
_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9 _.-]+")


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validated_url(url: str) -> str:
    candidate = str(url or "").strip()
    try:
        parts = urlsplit(candidate)
        valid = (
            parts.scheme.lower() in _ALLOWED_SCHEMES
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
            and not parts.fragment
            and not any(ord(ch) < 32 for ch in candidate)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("CRUCIX_URL_INVALID_OR_CONTAINS_CREDENTIALS")
    return candidate


def fetch_json(
    url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    maximum_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> dict[str, Any]:
    """GET one bounded JSON object; redirects and embedded credentials are denied."""
    target = _validated_url(url)
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(float(timeout_seconds))
        or not 0 < float(timeout_seconds) <= 15
    ):
        raise ValueError("CRUCIX_TIMEOUT_INVALID")
    if (
        isinstance(maximum_bytes, bool)
        or not isinstance(maximum_bytes, int)
        or not 1 <= maximum_bytes <= 5_000_000
    ):
        raise ValueError("CRUCIX_RESPONSE_LIMIT_INVALID")

    request = Request(
        target,
        headers={
            "Accept": "application/json",
            "User-Agent": "AURELIA-ReadOnly-Intelligence/1.0",
        },
        method="GET",
    )
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=float(timeout_seconds)) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise RuntimeError("CRUCIX_HTTP_STATUS_NOT_OK")
            if response.geturl() != target:
                raise RuntimeError("CRUCIX_REDIRECT_DENIED")
            announced_size = response.headers.get("Content-Length")
            if announced_size:
                try:
                    if int(announced_size) > maximum_bytes:
                        raise RuntimeError("CRUCIX_RESPONSE_TOO_LARGE")
                except ValueError:
                    raise RuntimeError("CRUCIX_CONTENT_LENGTH_INVALID") from None
            raw = response.read(maximum_bytes + 1)
    except HTTPError as exc:
        raise RuntimeError("CRUCIX_HTTP_ERROR:" + str(exc.code)) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("CRUCIX_TRANSPORT_ERROR:" + type(exc).__name__) from None

    if len(raw) > maximum_bytes:
        raise RuntimeError("CRUCIX_RESPONSE_TOO_LARGE")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("CRUCIX_RESPONSE_INVALID_JSON") from None
    if not isinstance(value, dict):
        raise RuntimeError("CRUCIX_JSON_ROOT_MUST_BE_OBJECT")
    return value


async def fetch_json_async(
    url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    maximum_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> dict[str, Any]:
    """Run synchronous HTTP in a worker thread so asyncio remains responsive."""
    return await asyncio.to_thread(
        fetch_json,
        url,
        timeout_seconds=timeout_seconds,
        maximum_bytes=maximum_bytes,
    )


def _as_nonnegative_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    if not math.isfinite(float(value)) or value < 0:
        return default
    return int(value)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _safe_label(value: Any, *, limit: int = 48) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = _SAFE_LABEL_RE.sub("", value).strip()
    return cleaned[:limit] if cleaned else None


def _count_map(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key, count in value.items():
        label = _safe_label(key, limit=40)
        if label is not None and isinstance(count, (int, float)) and not isinstance(count, bool):
            if math.isfinite(float(count)) and count >= 0:
                result[label] = int(count)
    return result


@dataclass(frozen=True)
class CrucixAdvisory:
    generated_at_utc: str | None
    collected_at_utc: str
    freshness_status: str
    age_seconds: float | None
    sources_ok: int
    sources_total: int
    sources_failed: int
    sources_stale: int
    radar_market_freshness: str
    radar_as_of_close: str | None
    radar_warning_count: int
    divergence_state_counts: dict[str, int]
    shock_regime: str | None
    shock_score: float | None
    shock_score_max: float | None
    warnings: tuple[str, ...]
    capital_authority: bool = False
    trade_signal: bool = False
    order_submission_permitted: bool = False

    def to_payload(self) -> dict[str, Any]:
        """Return a compact metadata-only envelope; never forward headlines or prompts."""
        return {
            "schema": "aurelia.crucix_advisory.v1",
            "generated_at_utc": self.generated_at_utc,
            "collected_at_utc": self.collected_at_utc,
            "freshness_status": self.freshness_status,
            "age_seconds": self.age_seconds,
            "sources_ok": self.sources_ok,
            "sources_total": self.sources_total,
            "sources_failed": self.sources_failed,
            "sources_stale": self.sources_stale,
            "radar_market_freshness": self.radar_market_freshness,
            "radar_as_of_close": self.radar_as_of_close,
            "radar_warning_count": self.radar_warning_count,
            "divergence_state_counts": dict(self.divergence_state_counts),
            "shock_regime": self.shock_regime,
            "shock_score": self.shock_score,
            "shock_score_max": self.shock_score_max,
            "warnings": list(self.warnings),
            "capital_authority": False,
            "trade_signal": False,
            "order_submission_permitted": False,
        }


JsonFetcher = Callable[..., Awaitable[dict[str, Any]]]


async def collect_crucix_advisory(
    data_url: str,
    *,
    radar_url: str | None = None,
    shock_url: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    maximum_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    max_data_age_seconds: float = DEFAULT_MAX_DATA_AGE_SECONDS,
    now: datetime | None = None,
    fetcher: JsonFetcher = fetch_json_async,
) -> CrucixAdvisory:
    """Collect Crucix metadata; stale/missing sources can never become trade signals."""
    if not data_url or not str(data_url).strip():
        raise ValueError("CRUCIX_DATA_URL_REQUIRED")
    if (
        isinstance(max_data_age_seconds, bool)
        or not isinstance(max_data_age_seconds, (int, float))
        or not math.isfinite(float(max_data_age_seconds))
        or not 0 < float(max_data_age_seconds) <= 86_400
    ):
        raise ValueError("CRUCIX_MAX_DATA_AGE_INVALID")

    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ValueError("CRUCIX_NOW_MUST_BE_TIMEZONE_AWARE")
    observed = observed.astimezone(timezone.utc)
    raw = await fetcher(
        data_url,
        timeout_seconds=timeout_seconds,
        maximum_bytes=maximum_bytes,
    )
    meta = raw.get("meta")
    if not isinstance(meta, dict):
        raise RuntimeError("CRUCIX_META_MISSING")

    timestamp = _parse_timestamp(meta.get("timestamp"))
    age: float | None = None
    warnings: list[str] = []
    if timestamp is None:
        freshness = "UNKNOWN"
        warnings.append("CRUCIX_TIMESTAMP_MISSING_OR_INVALID")
    else:
        age = (observed - timestamp).total_seconds()
        if age < 0:
            freshness = "UNKNOWN"
            warnings.append("CRUCIX_TIMESTAMP_IN_FUTURE")
        elif age > float(max_data_age_seconds):
            freshness = "STALE"
            warnings.append("CRUCIX_DATA_STALE")
        else:
            freshness = "CURRENT"

    sources_total = _as_nonnegative_int(meta.get("sourcesQueried"))
    sources_ok = _as_nonnegative_int(meta.get("sourcesOk"))
    sources_failed = _as_nonnegative_int(meta.get("sourcesFailed"))
    source_health = raw.get("health")
    sources_stale = 0
    if isinstance(source_health, list):
        for source in source_health:
            if isinstance(source, dict) and source.get("stale") is True:
                sources_stale += 1
            if isinstance(source, dict) and source.get("err") is True:
                sources_failed = max(sources_failed, 1)
    if sources_failed:
        warnings.append("CRUCIX_SOURCE_FAILURES_PRESENT")
    if sources_stale:
        warnings.append("CRUCIX_SOURCE_STALENESS_PRESENT")
    if freshness == "CURRENT" and (sources_failed or sources_stale):
        freshness = "DEGRADED"

    radar_freshness = "NOT_CONFIGURED"
    radar_as_of_close = None
    radar_warning_count = 0
    divergence_state_counts: dict[str, int] = {}
    if radar_url:
        try:
            radar = await fetcher(
                radar_url,
                timeout_seconds=timeout_seconds,
                maximum_bytes=maximum_bytes,
            )
            market_fresh = radar.get("marketFreshness")
            market_readings = radar.get("marketReadings")
            if not isinstance(market_fresh, dict):
                market_fresh = {}
            if not isinstance(market_readings, dict):
                market_readings = {}
            status_value = str(market_fresh.get("status") or market_readings.get("freshnessStatus") or "unknown").lower()
            radar_freshness = status_value if status_value in {"current", "lagging", "stale"} else "unknown"
            as_of = market_fresh.get("asOfClose") or market_readings.get("asOfClose") or radar.get("asOfClose") or radar.get("date")
            radar_as_of_close = as_of[:10] if isinstance(as_of, str) and len(as_of) >= 10 else None
            radar_warnings = radar.get("warnings")
            radar_warning_count = len(radar_warnings) if isinstance(radar_warnings, list) else 0
            divergence_state_counts = _count_map(radar.get("stateCounts"))
            if radar_freshness != "current":
                warnings.append("CRUCIX_RADAR_MARKET_DATA_NOT_CURRENT")
        except (RuntimeError, ValueError, TypeError):
            radar_freshness = "unknown"
            warnings.append("CRUCIX_RADAR_FETCH_OR_SCHEMA_FAILED")

    shock_regime = None
    shock_score = None
    shock_score_max = None
    if shock_url:
        try:
            shock = await fetcher(
                shock_url,
                timeout_seconds=timeout_seconds,
                maximum_bytes=maximum_bytes,
            )
            score_data = shock.get("shockScore")
            if isinstance(score_data, dict):
                regime = _safe_label(score_data.get("regime"))
                shock_regime = regime
                for key, attr in (("score", "score"), ("maxScore", "max")):
                    value = score_data.get(key)
                    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
                        if attr == "score":
                            shock_score = float(value)
                        else:
                            shock_score_max = float(value)
                if shock_score is not None and shock_score_max is not None and (
                    shock_score < 0 or shock_score_max <= 0 or shock_score > shock_score_max
                ):
                    shock_score = None
                    shock_score_max = None
                    warnings.append("CRUCIX_SHOCK_SCORE_INVALID")
            else:
                warnings.append("CRUCIX_SHOCK_SCHEMA_MISSING")
        except (RuntimeError, ValueError, TypeError):
            warnings.append("CRUCIX_SHOCK_FETCH_OR_SCHEMA_FAILED")

    return CrucixAdvisory(
        generated_at_utc=timestamp.isoformat().replace("+00:00", "Z") if timestamp else None,
        collected_at_utc=observed.isoformat().replace("+00:00", "Z"),
        freshness_status=freshness,
        age_seconds=round(age, 3) if age is not None else None,
        sources_ok=sources_ok,
        sources_total=sources_total,
        sources_failed=sources_failed,
        sources_stale=sources_stale,
        radar_market_freshness=radar_freshness,
        radar_as_of_close=radar_as_of_close,
        radar_warning_count=radar_warning_count,
        divergence_state_counts=divergence_state_counts,
        shock_regime=shock_regime,
        shock_score=shock_score,
        shock_score_max=shock_score_max,
        warnings=tuple(dict.fromkeys(warnings)),
        capital_authority=False,
        trade_signal=False,
        order_submission_permitted=False,
    )
