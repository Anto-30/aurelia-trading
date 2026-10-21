#!/usr/bin/env python3
"""Fetch bounded Deriv candle history and persist a checksummed research dataset.

No authentication token is accepted or read. Market history requests are public;
this script never constructs a trade, proposal, buy, or execution request.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.atos_validation.deriv_data import DerivHistoryClient, persist_history


def parse_epoch(raw: str, name: str) -> int:
    value = raw.strip()
    if value.isdigit():
        return int(value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{name} must be epoch seconds or ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError(f"{name} must include an explicit timezone, preferably Z")
    return int(parsed.astimezone(timezone.utc).timestamp())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, help="Deriv symbol, e.g. R_100")
    parser.add_argument("--start", required=True, help="UTC epoch seconds or timezone-qualified ISO-8601")
    parser.add_argument("--end", required=True, help="UTC epoch seconds or timezone-qualified ISO-8601")
    parser.add_argument("--granularity", type=int, choices=(60, 900), default=60, help="60=1m, 900=15m")
    parser.add_argument("--bars-per-request", type=int, default=4500)
    parser.add_argument("--out", type=Path, required=True, help="Normalized candle CSV path")
    args = parser.parse_args()
    try:
        start = parse_epoch(args.start, "--start")
        end = parse_epoch(args.end, "--end")
        client = DerivHistoryClient()
        bars = client.backfill(
            args.symbol, start, end,
            granularity=args.granularity,
            bars_per_request=args.bars_per_request,
        )
        manifest = persist_history(
            bars, args.out, symbol=args.symbol,
            granularity=args.granularity,
            start_epoch=start, end_epoch=end,
        )
    except Exception as exc:
        print("DERIV_HISTORY_FETCH=FAILED")
        print(f"REASON={type(exc).__name__}: {exc}")
        return 2

    print("DERIV_HISTORY_FETCH=VERIFIED")
    print(f"SYMBOL={manifest['symbol']}")
    print(f"GRANULARITY_SECONDS={manifest['granularity_seconds']}")
    print(f"BAR_COUNT={manifest['bar_count']}")
    print(f"COVERAGE_COMPLETE={str(manifest['coverage_complete']).lower()}")
    print(f"DATA_SHA256={manifest['data_sha256']}")
    print(f"MANIFEST_SHA256={manifest['manifest_sha256']}")
    print(f"DATA_PATH={args.out}")
    print(f"MANIFEST_PATH={args.out.with_suffix(args.out.suffix + '.manifest.json')}")
    print("VOLUME_FABRICATED=false")
    print("ORDERS_SUBMITTED=0")
    print("CAPITAL_AUTHORITY_GRANTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
