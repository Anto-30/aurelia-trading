from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .deriv_tick_ingestor import DerivTickIngestor
from .parquet_store import ParquetTickStore


from research.labs.deterministic_intraday_strategies import StrategyBar
from .deriv_tick_ingestor import Tick, validate_ticks


def resample_ticks_to_strategy_bars(
    ticks: Sequence[Tick],
    *,
    timeframe_seconds: int,
    data_end_epoch: int,
) -> list[StrategyBar]:
    """Build closed UTC OHLC bars from public ticks without inventing volume.

    Only 60-second and 900-second bars are supported. data_end_epoch is the
    exclusive coverage boundary: any bucket whose close is after it is omitted.
    Empty periods remain gaps; they are never filled with synthetic candles.
    """

    if (
        isinstance(timeframe_seconds, bool)
        or not isinstance(timeframe_seconds, int)
        or timeframe_seconds not in {60, 900}
    ):
        raise ValueError("TIMEFRAME_SECONDS_UNSUPPORTED")
    if (
        isinstance(data_end_epoch, bool)
        or not isinstance(data_end_epoch, int)
        or data_end_epoch <= 0
    ):
        raise ValueError("DATA_END_EPOCH_INVALID")

    ordered = sorted(ticks, key=lambda item: item.epoch)
    if not ordered:
        raise ValueError("NO_TICKS_AVAILABLE")
    validate_ticks(ordered, max_gap_seconds=max(timeframe_seconds * 2, 1))

    grouped: dict[int, list[Tick]] = {}
    for tick in ordered:
        bucket_start = (tick.epoch // timeframe_seconds) * timeframe_seconds
        bucket_end = bucket_start + timeframe_seconds
        if bucket_end > data_end_epoch:
            continue
        grouped.setdefault(bucket_start, []).append(tick)

    if not grouped:
        raise ValueError("NO_COMPLETE_BARS_AVAILABLE")

    bars: list[StrategyBar] = []
    for bucket_start, rows in sorted(grouped.items()):
        quotes = [float(row.quote) for row in rows]
        bucket_end = bucket_start + timeframe_seconds
        timestamp = datetime.fromtimestamp(
            bucket_end, tz=timezone.utc
        ).isoformat()
        bars.append(
            StrategyBar(
                timestamp_utc=timestamp,
                open=quotes[0],
                high=max(quotes),
                low=min(quotes),
                close=quotes[-1],
                volume=None,
                session_id=None,
            )
        )

    for index in range(1, len(bars)):
        previous = datetime.fromisoformat(bars[index - 1].timestamp_utc)
        current = datetime.fromisoformat(bars[index].timestamp_utc)
        if current <= previous:
            raise ValueError("RESAMPLED_BAR_TIMESTAMPS_NOT_INCREASING")
    return bars


class HistoricalDataPipeline:
    """Research-only orchestration: public Deriv ticks -> validation -> Parquet."""

    def __init__(
        self,
        output_dir: str | Path = "data/ticks",
        *,
        page_size: int = 1000,
        max_pages: int = 10000,
        rate_limit_seconds: float = 0.25,
    ) -> None:
        self.store = ParquetTickStore(output_dir)
        self.ingestor = DerivTickIngestor(
            page_size=page_size,
            max_pages=max_pages,
            rate_limit_seconds=rate_limit_seconds,
        )

    async def run(
        self,
        *,
        symbol: str,
        start_epoch: int,
        end_epoch: int,
        source_sha: str | None = None,
    ):
        result = await self.ingestor.fetch_ticks(
            symbol,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            store=self.store,
            source_sha=source_sha,
        )
        return result


def _parse_epoch(value: str) -> int:
    try:
        result = int(value)
    except ValueError:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("TIMESTAMP_MUST_INCLUDE_TIMEZONE") from None
        result = int(stamp.astimezone(timezone.utc).timestamp())
    if result <= 0:
        raise ValueError("TIMESTAMP_MUST_BE_POSITIVE")
    return result


async def _main(args: argparse.Namespace) -> int:
    pipeline = HistoricalDataPipeline(
        args.output_dir,
        page_size=args.page_size,
        max_pages=args.max_pages,
        rate_limit_seconds=args.rate_limit_seconds,
    )
    result = await pipeline.run(
        symbol=args.symbol,
        start_epoch=_parse_epoch(args.start),
        end_epoch=_parse_epoch(args.end),
    )
    print(f"INGESTION_STATUS={result.status}")
    print(f"SYMBOL={result.symbol}")
    print(f"TICKS={result.tick_count}")
    print(f"PAGES={result.pages_fetched}")
    print(f"DUPLICATES_REMOVED={result.duplicates_removed}")
    print(f"MAX_GAP_SECONDS={result.max_gap_seconds}")
    print(f"GAPS_OVER_THRESHOLD={result.gaps_over_threshold}")
    print(f"DATASET_SHA256={result.dataset_sha256}")
    print(f"PARQUET_PARTITIONS={len(result.parquet_paths)}")
    print(f"PROVENANCE_FILES={len(result.provenance_paths)}")
    return 0 if result.status == "COMPLETE" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only Deriv tick-history ingestion")
    parser.add_argument("--symbol", default="R_100")
    parser.add_argument("--start", required=True, help="UTC epoch or timezone-aware ISO-8601")
    parser.add_argument("--end", required=True, help="UTC epoch or timezone-aware ISO-8601")
    parser.add_argument("--output-dir", default="data/ticks")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-pages", type=int, default=10000)
    parser.add_argument("--rate-limit-seconds", type=float, default=0.25)
    args = parser.parse_args()
    return asyncio.run(_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
