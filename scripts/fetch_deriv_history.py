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
    parser.add_argument("--app-id", default=None, help="Optional numeric App ID. Public market-data requests do not require an App ID.")
    parser.add_argument("--max-attempts", type=int, default=4, help="Bounded attempts per request (1..8)")
    parser.add_argument("--retry-base-seconds", type=float, default=1.5, help="Exponential backoff base, minimum 1 second")
    parser.add_argument("--request-delay-seconds", type=float, default=1.5, help="Minimum delay between successful history pages")
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
        client = DerivHistoryClient(
            app_id=args.app_id,
            max_attempts=args.max_attempts,
            retry_base_seconds=args.retry_base_seconds,
        )
        bars = client.backfill(
            args.symbol, start, end,
            granularity=args.granularity,
            bars_per_request=args.bars_per_request,
            request_delay_seconds=args.request_delay_seconds,
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

    requested_count = ((end - start) // args.granularity) + 1
    actual_coverage = len(bars) / requested_count
    if actual_coverage < 0.99 or not manifest["coverage_complete"]:
        print("DERIV_HISTORY_FETCH=FAILED")
        print(f"COVERAGE_RATIO={actual_coverage:.8f}")
        print("REASON=coverage below 99% or exact-coverage manifest failed")
        return 3

    print("DERIV_HISTORY_FETCH=VERIFIED")
    print(f"SYMBOL={manifest['symbol']}")
    print(f"GRANULARITY_SECONDS={manifest['granularity_seconds']}")
    print(f"BAR_COUNT={manifest['bar_count']}")
    print(f"REQUESTED_BAR_COUNT={requested_count}")
    print(f"COVERAGE_RATIO={actual_coverage:.8f}")
    print(f"APP_ID_USED={args.app_id or 'none_public_endpoint'}")
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
