from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from .deriv_tick_ingestor import DerivTickIngestor
from .parquet_store import ParquetTickStore


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
