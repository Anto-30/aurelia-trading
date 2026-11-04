from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

PUBLIC_DERIV_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"


class DerivTickIngestionError(RuntimeError):
    """Sanitized public tick-history ingestion failure."""


@dataclass(frozen=True)
class Tick:
    symbol: str
    epoch: int
    quote: float

    def validate(self) -> bool:
        if (
            not isinstance(self.symbol, str)
            or not self.symbol
            or not self.symbol.isascii()
            or not self.symbol.replace("_", "").isalnum()
            or self.symbol != self.symbol.upper()
        ):
            raise ValueError("TICK_SYMBOL_INVALID")
        if isinstance(self.epoch, bool) or not isinstance(self.epoch, int) or self.epoch <= 0:
            raise ValueError("TICK_EPOCH_INVALID")
        if (
            isinstance(self.quote, bool)
            or not isinstance(self.quote, (int, float))
            or not math.isfinite(float(self.quote))
            or float(self.quote) < 0
        ):
            raise ValueError("TICK_QUOTE_INVALID")
        return True


@dataclass(frozen=True)
class HistoryPage:
    ticks: tuple[Tick, ...]
    req_id: int
    payload_sha256: str


@dataclass(frozen=True)
class TickValidationReport:
    input_count: int
    unique_count: int
    duplicate_count: int
    first_epoch: int
    last_epoch: int
    max_gap_seconds: int
    gaps_over_threshold: int


@dataclass(frozen=True)
class IngestionResult:
    status: str
    symbol: str
    start_epoch: int
    end_epoch: int
    pages_fetched: int
    tick_count: int
    duplicates_removed: int
    max_gap_seconds: int
    gaps_over_threshold: int
    first_epoch: int
    last_epoch: int
    dataset_sha256: str
    run_id: str
    ticks: tuple[Tick, ...]
    parquet_paths: tuple[str, ...] = ()
    provenance_paths: tuple[str, ...] = ()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def parse_history_response(
    response: Mapping[str, Any],
    *,
    symbol: str,
    expected_req_id: int,
) -> HistoryPage:
    """Parse one Deriv ticks_history response without guessing missing fields."""
    if not isinstance(response, Mapping):
        raise DerivTickIngestionError("DERIV_RESPONSE_NOT_OBJECT")
    error = response.get("error")
    if error is not None:
        code = error.get("code") if isinstance(error, Mapping) else None
        safe_code = str(code or "UNKNOWN").replace(" ", "_")[:80]
        raise DerivTickIngestionError(f"DERIV_API_ERROR:{safe_code}")
    if response.get("msg_type") != "history":
        raise DerivTickIngestionError("DERIV_HISTORY_MESSAGE_TYPE_INVALID")
    req_id = response.get("req_id")
    if isinstance(req_id, bool) or req_id != expected_req_id:
        raise DerivTickIngestionError("REQUEST_ID_MISMATCH")

    history = response.get("history")
    if not isinstance(history, Mapping):
        raise DerivTickIngestionError("HISTORY_PAYLOAD_MISSING")
    times, prices = history.get("times"), history.get("prices")
    if not isinstance(times, list) or not isinstance(prices, list):
        raise DerivTickIngestionError("HISTORY_ARRAYS_INVALID")
    if len(times) != len(prices):
        raise DerivTickIngestionError("HISTORY_ARRAY_LENGTH_MISMATCH")

    ticks: list[Tick] = []
    previous_epoch: int | None = None
    for epoch, quote in zip(times, prices):
        if isinstance(epoch, bool) or not isinstance(epoch, int):
            raise DerivTickIngestionError("TICK_EPOCH_INVALID")
        if previous_epoch is not None and epoch < previous_epoch:
            raise DerivTickIngestionError("HISTORY_TIMESTAMPS_NOT_MONOTONIC")
        tick = Tick(symbol=symbol, epoch=epoch, quote=quote)
        try:
            tick.validate()
        except (TypeError, ValueError, OverflowError) as exc:
            raise DerivTickIngestionError(str(exc)) from None
        ticks.append(tick)
        previous_epoch = epoch

    digest = hashlib.sha256(_canonical_json(response).encode("utf-8")).hexdigest()
    return HistoryPage(tuple(ticks), int(req_id), digest)


def validate_ticks(
    ticks: Sequence[Tick],
    *,
    max_gap_seconds: int = 120,
) -> TickValidationReport:
    """Deduplicate exact repeats, preserving distinct quotes at the same epoch."""
    if (
        isinstance(max_gap_seconds, bool)
        or not isinstance(max_gap_seconds, int)
        or max_gap_seconds < 1
    ):
        raise ValueError("MAX_GAP_SECONDS_INVALID")
    if not ticks:
        raise DerivTickIngestionError("NO_TICKS_RETURNED")

    input_count = len(ticks)
    seen: set[tuple[str, int, float]] = set()
    unique: list[Tick] = []
    for tick in ticks:
        if not isinstance(tick, Tick):
            raise DerivTickIngestionError("TICK_RECORD_TYPE_INVALID")
        try:
            tick.validate()
        except (TypeError, ValueError, OverflowError) as exc:
            raise DerivTickIngestionError(str(exc)) from None
        key = (tick.symbol, tick.epoch, float(tick.quote))
        if key not in seen:
            seen.add(key)
            unique.append(tick)

    if len({tick.symbol for tick in unique}) != 1:
        raise DerivTickIngestionError("MULTIPLE_SYMBOLS_IN_TICK_SET")
    if any(unique[i].epoch > unique[i + 1].epoch for i in range(len(unique) - 1)):
        raise DerivTickIngestionError("TICK_TIMESTAMPS_NOT_MONOTONIC")

    gaps = [
        unique[i + 1].epoch - unique[i].epoch
        for i in range(len(unique) - 1)
    ]
    return TickValidationReport(
        input_count=input_count,
        unique_count=len(unique),
        duplicate_count=input_count - len(unique),
        first_epoch=unique[0].epoch,
        last_epoch=unique[-1].epoch,
        max_gap_seconds=max(gaps, default=0),
        gaps_over_threshold=sum(1 for gap in gaps if gap > max_gap_seconds),
    )


def _default_ws_connect(url: str):
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise DerivTickIngestionError("WEBSOCKETS_DEPENDENCY_MISSING") from exc
    return connect(
        url,
        open_timeout=10,
        close_timeout=5,
        ping_interval=20,
        ping_timeout=20,
        max_size=2**20,
    )


class DerivTickIngestor:
    """Research-only, unauthenticated, backward-paged Deriv tick-history client."""

    def __init__(
        self,
        *,
        endpoint: str = PUBLIC_DERIV_WS_URL,
        ws_connect: Callable[[str], Any] | None = None,
        page_size: int = 1000,
        max_pages: int = 10000,
        timeout_seconds: float = 15.0,
        rate_limit_seconds: float = 0.25,
        max_gap_seconds: int = 120,
    ) -> None:
        if not isinstance(endpoint, str) or endpoint != PUBLIC_DERIV_WS_URL:
            raise ValueError("DERIV_PUBLIC_HISTORY_ENDPOINT_NOT_ALLOWLISTED")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 1000:
            raise ValueError("DERIV_HISTORY_PAGE_SIZE_INVALID")
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1:
            raise ValueError("DERIV_HISTORY_MAX_PAGES_INVALID")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not 1 <= timeout_seconds <= 60
        ):
            raise ValueError("DERIV_HISTORY_TIMEOUT_INVALID")
        if (
            not isinstance(rate_limit_seconds, (int, float))
            or isinstance(rate_limit_seconds, bool)
            or not 0 <= rate_limit_seconds <= 10
        ):
            raise ValueError("DERIV_HISTORY_RATE_LIMIT_INVALID")
        if isinstance(max_gap_seconds, bool) or not isinstance(max_gap_seconds, int) or max_gap_seconds < 1:
            raise ValueError("DERIV_HISTORY_MAX_GAP_INVALID")

        self.endpoint = endpoint
        self.ws_connect = ws_connect or _default_ws_connect
        self.page_size = page_size
        self.max_pages = max_pages
        self.timeout_seconds = float(timeout_seconds)
        self.rate_limit_seconds = float(rate_limit_seconds)
        self.max_gap_seconds = max_gap_seconds

    async def fetch_ticks(
        self,
        symbol: str,
        *,
        start_epoch: int,
        end_epoch: int,
        store: Any | None = None,
        run_id: str | None = None,
        source_sha: str | None = None,
    ) -> IngestionResult:
        if (
            not isinstance(symbol, str)
            or not symbol
            or not symbol.isascii()
            or not symbol.replace("_", "").isalnum()
            or symbol != symbol.upper()
        ):
            raise ValueError("DERIV_SYMBOL_INVALID")
        if (
            isinstance(start_epoch, bool)
            or not isinstance(start_epoch, int)
            or isinstance(end_epoch, bool)
            or not isinstance(end_epoch, int)
            or start_epoch <= 0
            or end_epoch <= start_epoch
        ):
            raise ValueError("DERIV_HISTORY_TIME_RANGE_INVALID")

        run_identifier = run_id or uuid4().hex
        revision = source_sha or os.getenv("GITHUB_SHA", "").strip() or "LOCAL_UNPINNED"
        collected: list[Tick] = []
        seen_page_hashes: set[str] = set()
        parquet_paths: list[str] = []
        provenance_paths: list[str] = []
        cursor = end_epoch
        pages_fetched = 0
        last_request_at: float | None = None
        coverage_reached = False
        source_exhausted = False

        async with self.ws_connect(self.endpoint) as websocket:
            for page_number in range(1, self.max_pages + 1):
                if last_request_at is not None and self.rate_limit_seconds:
                    wait_for = self.rate_limit_seconds - (time.monotonic() - last_request_at)
                    if wait_for > 0:
                        await asyncio.sleep(wait_for)

                req_id = page_number
                request = {
                    "ticks_history": symbol,
                    "start": start_epoch,
                    "end": str(cursor),
                    "count": self.page_size,
                    "style": "ticks",
                    "subscribe": 0,
                    "req_id": req_id,
                }
                page: HistoryPage | None = None
                for attempt in range(3):
                    try:
                        await websocket.send(_canonical_json(request))
                        last_request_at = time.monotonic()
                        response_text = await asyncio.wait_for(
                            websocket.recv(), timeout=self.timeout_seconds
                        )
                        if isinstance(response_text, bytes):
                            response_text = response_text.decode("utf-8")
                        response = json.loads(response_text)
                        page = parse_history_response(
                            response, symbol=symbol, expected_req_id=req_id
                        )
                        break
                    except DerivTickIngestionError as exc:
                        if not str(exc).startswith("DERIV_API_ERROR:RateLimit") or attempt == 2:
                            raise
                        await asyncio.sleep(0.5 * (attempt + 1))
                    except (asyncio.TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                        if attempt == 2:
                            raise DerivTickIngestionError(
                                f"DERIV_HISTORY_TRANSPORT_FAILED:{type(exc).__name__}"
                            ) from None
                        await asyncio.sleep(0.25 * (attempt + 1))
                if page is None:
                    raise DerivTickIngestionError("DERIV_HISTORY_RETRY_EXHAUSTED")

                if page.payload_sha256 in seen_page_hashes:
                    raise DerivTickIngestionError("HISTORY_PAGINATION_STALLED")
                seen_page_hashes.add(page.payload_sha256)
                pages_fetched += 1
                in_range = tuple(
                    tick for tick in page.ticks
                    if start_epoch <= tick.epoch <= end_epoch
                )
                if not in_range:
                    source_exhausted = True
                    break
                collected.extend(in_range)

                if store is not None:
                    written = store.write_page(
                        symbol=symbol,
                        run_id=run_identifier,
                        page_number=page_number,
                        ticks=in_range,
                        request=request,
                        source_sha=revision,
                        page_sha256=page.payload_sha256,
                    )
                    parquet_paths.extend(written.parquet_paths)
                    provenance_paths.extend(written.provenance_paths)

                earliest = min(tick.epoch for tick in in_range)
                if earliest <= start_epoch:
                    coverage_reached = True
                    break
                if len(page.ticks) < self.page_size:
                    source_exhausted = True
                    break
                if earliest > cursor:
                    raise DerivTickIngestionError("HISTORY_PAGINATION_MOVED_FORWARD")
                cursor = earliest

        if not collected:
            raise DerivTickIngestionError("NO_TICKS_RETURNED")

        collected.sort(key=lambda item: item.epoch)
        deduped: list[Tick] = []
        seen_ticks: set[tuple[str, int, float]] = set()
        for tick in collected:
            key = (tick.symbol, tick.epoch, float(tick.quote))
            if key not in seen_ticks:
                deduped.append(tick)
                seen_ticks.add(key)

        report = validate_ticks(deduped, max_gap_seconds=self.max_gap_seconds)
        dataset_payload = [
            {"symbol": tick.symbol, "epoch": tick.epoch, "quote": float(tick.quote)}
            for tick in deduped
        ]
        dataset_sha = hashlib.sha256(
            _canonical_json(dataset_payload).encode("utf-8")
        ).hexdigest()
        result = IngestionResult(
            status="COMPLETE" if coverage_reached else "PARTIAL",
            symbol=symbol,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            pages_fetched=pages_fetched,
            tick_count=report.unique_count,
            duplicates_removed=report.duplicate_count,
            max_gap_seconds=report.max_gap_seconds,
            gaps_over_threshold=report.gaps_over_threshold,
            first_epoch=report.first_epoch,
            last_epoch=report.last_epoch,
            dataset_sha256=dataset_sha,
            run_id=run_identifier,
            ticks=tuple(deduped),
            parquet_paths=tuple(parquet_paths),
            provenance_paths=tuple(provenance_paths),
        )
        if store is not None:
            store.write_run_manifest(result, source_sha=revision)
        if not coverage_reached and not source_exhausted and pages_fetched >= self.max_pages:
            raise DerivTickIngestionError("PAGE_LIMIT_REACHED")
        return result
