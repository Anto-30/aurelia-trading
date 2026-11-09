from __future__ import annotations

"""Unauthenticated, provenance-preserving Deriv historical OHLC acquisition."""

import argparse
import asyncio
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Callable, Sequence

from research.labs.deterministic_intraday_strategies import StrategyBar
from runtime.adapters.deriv_ws import DerivWebSocketTransport


PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
LEGACY_PUBLIC_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"
SUPPORTED_GRANULARITIES = (60, 900)
API_VARIANTS = {"new": PUBLIC_WS_URL, "legacy": LEGACY_PUBLIC_WS_URL}
CSV_COLUMNS = ("timestamp_utc", "open", "high", "low", "close")


def _validate_window(*, symbol: str, start_epoch: int, end_epoch: int,
                     granularity: int, chunk_bars: int) -> None:
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9_]{2,30}", symbol):
        raise ValueError("HISTORICAL_SYMBOL_INVALID")
    if type(granularity) is not int or granularity not in SUPPORTED_GRANULARITIES:
        raise ValueError("HISTORICAL_GRANULARITY_UNSUPPORTED")
    if type(start_epoch) is not int or type(end_epoch) is not int:
        raise ValueError("HISTORICAL_EPOCH_INVALID")
    if start_epoch < 0 or end_epoch <= start_epoch:
        raise ValueError("HISTORICAL_WINDOW_INVALID")
    if start_epoch % granularity or end_epoch % granularity:
        raise ValueError("HISTORICAL_WINDOW_NOT_GRANULARITY_ALIGNED")
    if type(chunk_bars) is not int or not 2 <= chunk_bars <= 1000:
        raise ValueError("HISTORICAL_CHUNK_SIZE_INVALID")


def _validate_echo_request(
    response: dict[str, Any],
    request: dict[str, Any],
) -> None:
    """Require Deriv to echo the requested historical query verbatim."""
    echo = response.get("echo_req")
    if not isinstance(echo, dict):
        raise RuntimeError("DERIV_HISTORICAL_ECHO_REQUEST_MISSING")

    fields = ("ticks_history", "style", "granularity", "start", "end", "count")
    for field in fields:
        expected = request[field]
        actual = echo.get(field)
        if field in {"granularity", "start", "count"}:
            try:
                if isinstance(actual, bool) or int(actual) != int(expected):
                    raise RuntimeError("DERIV_HISTORICAL_ECHO_REQUEST_MISMATCH")
            except (TypeError, ValueError, OverflowError):
                raise RuntimeError("DERIV_HISTORICAL_ECHO_REQUEST_MISMATCH") from None
        elif actual != expected:
            raise RuntimeError("DERIV_HISTORICAL_ECHO_REQUEST_MISMATCH")


def _parse_candle(raw: dict[str, Any], *, granularity: int) -> StrategyBar:
    if not isinstance(raw, dict):
        raise ValueError("HISTORICAL_CANDLE_SHAPE_INVALID")
    epoch = raw.get("epoch")
    if type(epoch) is not int or epoch < 0 or epoch % granularity:
        raise ValueError("HISTORICAL_CANDLE_EPOCH_INVALID")
    values: dict[str, float] = {}
    for field in ("open", "high", "low", "close"):
        value = raw.get(field)
        if isinstance(value, bool):
            raise ValueError("HISTORICAL_CANDLE_PRICE_INVALID")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("HISTORICAL_CANDLE_PRICE_INVALID") from exc
        if not math.isfinite(number) or number <= 0:
            raise ValueError("HISTORICAL_CANDLE_PRICE_INVALID")
        values[field] = number
    if values["high"] < max(values["open"], values["close"], values["low"]):
        raise ValueError("HISTORICAL_CANDLE_OHLC_INVARIANT_FAILED")
    if values["low"] > min(values["open"], values["close"], values["high"]):
        raise ValueError("HISTORICAL_CANDLE_OHLC_INVARIANT_FAILED")
    stamp = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
    return StrategyBar(timestamp_utc=stamp, **values)


async def collect_timeframe(
    transport: Any, *, symbol: str, start_epoch: int, end_epoch: int,
    granularity: int, chunk_bars: int = 900,
    request_delay_seconds: float = 0.35,
) -> tuple[StrategyBar, ...]:
    """Fetch exact contiguous candle chunks; missing bars abort the dataset."""
    _validate_window(symbol=symbol, start_epoch=start_epoch, end_epoch=end_epoch,
                     granularity=granularity, chunk_bars=chunk_bars)
    if (isinstance(request_delay_seconds, bool)
        or not isinstance(request_delay_seconds, (int, float))
        or not math.isfinite(float(request_delay_seconds))
        or request_delay_seconds < 0):
        raise ValueError("HISTORICAL_REQUEST_DELAY_INVALID")

    bars: list[StrategyBar] = []
    cursor = start_epoch
    while cursor < end_epoch:
        chunk_end = min(end_epoch - granularity,
                        cursor + granularity * (chunk_bars - 1))
        expected_epochs = list(range(cursor, chunk_end + 1, granularity))
        request = {
            "ticks_history": symbol,
            "style": "candles",
            "granularity": granularity,
            "start": cursor,
            "end": str(chunk_end),
            "count": len(expected_epochs),
        }
        try:
            response = await transport.request(request)
        except Exception as exc:
            raise RuntimeError(
                "DERIV_HISTORICAL_REQUEST_FAILED:" + type(exc).__name__
            ) from None
        if not isinstance(response, dict):
            raise RuntimeError("DERIV_HISTORICAL_RESPONSE_SHAPE_INVALID")
        if "error" in response:
            error = response.get("error")
            code = error.get("code") if isinstance(error, dict) else None
            if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", code):
                code = "UNKNOWN_CODE"
            raise RuntimeError("DERIV_HISTORICAL_API_REJECTED:" + code)
        _validate_echo_request(response, request)
        if response.get("msg_type") != "candles":
            message_type = response.get("msg_type")
            if isinstance(message_type, str) and message_type in {"history", "tick", "ohlc", "candles"}:
                raise RuntimeError("DERIV_HISTORICAL_RESPONSE_TYPE_INVALID:" + message_type)
            raise RuntimeError("DERIV_HISTORICAL_RESPONSE_TYPE_INVALID")
        candles = response.get("candles")
        if not isinstance(candles, list):
            raise RuntimeError("DERIV_HISTORICAL_CANDLES_MISSING")
        chunk = tuple(_parse_candle(row, granularity=granularity) for row in candles)
        epochs = [int(datetime.fromisoformat(x.timestamp_utc).timestamp()) for x in chunk]
        if epochs and (min(epochs) < cursor or max(epochs) > chunk_end):
            raise RuntimeError(
                "DERIV_HISTORICAL_SOURCE_RETURNED_OUT_OF_RANGE_CANDLES:"
                f"requested_start={cursor}:requested_end={chunk_end}:"
                f"actual_first={min(epochs)}:actual_last={max(epochs)}"
            )
        if epochs != expected_epochs:
            if len(epochs) == len(expected_epochs) and len(set(epochs)) == len(epochs) and sorted(epochs) == expected_epochs:
                chunk = tuple(sorted(chunk, key=lambda x: x.timestamp_utc))
                epochs = expected_epochs
            else:
                actual_first = epochs[0] if epochs else 0
                actual_last = epochs[-1] if epochs else 0
                raise RuntimeError(
                    "DERIV_HISTORICAL_GAP_OR_TRUNCATION_DETECTED:"
                    f"expected_count={len(expected_epochs)}:"
                    f"actual_count={len(epochs)}:"
                    f"expected_first={expected_epochs[0]}:"
                    f"expected_last={expected_epochs[-1]}:"
                    f"actual_first={actual_first}:"
                    f"actual_last={actual_last}"
                )
        if bars and chunk and epochs[0] <= int(
            datetime.fromisoformat(bars[-1].timestamp_utc).timestamp()
        ):
            raise RuntimeError("DERIV_HISTORICAL_CHUNK_OVERLAP_DETECTED")
        bars.extend(chunk)
        cursor = chunk_end + granularity
        if cursor < end_epoch and request_delay_seconds:
            await asyncio.sleep(float(request_delay_seconds))

    if len(bars) != (end_epoch - start_epoch) // granularity:
        raise RuntimeError("DERIV_HISTORICAL_FINAL_BAR_COUNT_MISMATCH")
    return tuple(bars)


def normalized_bars_sha256(bars: Sequence[StrategyBar]) -> str:
    """Hash the same canonical normalized-bar representation as the WFO engine."""
    digest = hashlib.sha256()
    digest.update(b"[")
    for index, bar in enumerate(bars):
        if index:
            digest.update(b",")
        row = {
            "timestamp_utc": bar.timestamp_utc,
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": None if bar.volume is None else float(bar.volume),
            "session_id": bar.session_id,
        }
        digest.update(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                 allow_nan=False).encode("utf-8"))
    digest.update(b"]")
    return digest.hexdigest()


def _write_dataset(output_dir: Path, *, symbol: str, granularity: int,
                   bars: Sequence[StrategyBar], start_epoch: int,
                   end_epoch: int, source_commit: str,
                   source_endpoint: str) -> dict[str, Any]:
    timeframe = "M1" if granularity == 60 else "M15"
    path = output_dir / f"{symbol}_{timeframe}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for bar in bars:
            writer.writerow({
                "timestamp_utc": bar.timestamp_utc,
                "open": format(bar.open, ".15g"),
                "high": format(bar.high, ".15g"),
                "low": format(bar.low, ".15g"),
                "close": format(bar.close, ".15g"),
            })
    file_digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            file_digest.update(block)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "granularity_seconds": granularity,
        "start_epoch_inclusive": start_epoch,
        "end_epoch_exclusive": end_epoch,
        "start_utc": datetime.fromtimestamp(start_epoch, timezone.utc).isoformat(),
        "end_utc": datetime.fromtimestamp(end_epoch, timezone.utc).isoformat(),
        "bar_count": len(bars),
        "expected_bar_count": (end_epoch - start_epoch) // granularity,
        "gap_count": 0,
        "csv_file": path.name,
        "csv_sha256": file_digest.hexdigest(),
        "normalized_bars_sha256": normalized_bars_sha256(bars),
        "source": "Deriv public ticks_history (style=candles), unauthenticated",
        "source_endpoint": source_endpoint,
        "source_commit": source_commit,
    }


async def collect_historical_dataset(
    *, symbol: str, start_epoch: int, end_epoch: int,
    granularities: Sequence[int], output_dir: str | Path,
    source_commit: str, chunk_bars: int = 900,
    request_delay_seconds: float = 0.35,
    api_variant: str = "new",
    transport_factory: Callable[..., Any] = DerivWebSocketTransport,
) -> dict[str, Any]:
    """Collect timeframes on one unauthenticated public WebSocket connection."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("HISTORICAL_SOURCE_COMMIT_INVALID")
    if not granularities or any(
        type(g) is not int or g not in SUPPORTED_GRANULARITIES for g in granularities
    ):
        raise ValueError("HISTORICAL_TIMEFRAMES_INVALID")
    if len(set(granularities)) != len(granularities):
        raise ValueError("HISTORICAL_TIMEFRAMES_DUPLICATED")
    if api_variant not in API_VARIANTS:
        raise ValueError("HISTORICAL_API_VARIANT_INVALID")
    endpoint_url = API_VARIANTS[api_variant]

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    transport = transport_factory(
        endpoint_url, timeout_seconds=45.0,
        application_ping_interval_seconds=30.0,
    )
    datasets: list[dict[str, Any]] = []
    await transport.connect()
    try:
        for granularity in granularities:
            bars = await collect_timeframe(
                transport, symbol=symbol, start_epoch=start_epoch,
                end_epoch=end_epoch, granularity=granularity,
                chunk_bars=chunk_bars,
                request_delay_seconds=request_delay_seconds,
            )
            datasets.append(_write_dataset(
                directory, symbol=symbol, granularity=granularity, bars=bars,
                start_epoch=start_epoch, end_epoch=end_epoch,
                source_commit=source_commit, source_endpoint=endpoint_url,
            ))
    finally:
        await transport.close()

    manifest = {
        "schema": "aurelia.deriv.historical_ohlc_manifest.v1",
        "symbol": symbol,
        "start_epoch_inclusive": start_epoch,
        "end_epoch_exclusive": end_epoch,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "api_variant": api_variant,
        "authentication_used": False,
        "capital_authority": False,
        "order_submission_permitted": False,
        "datasets": datasets,
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_timeframes(raw: str) -> tuple[int, ...]:
    try:
        values = tuple(int(x.strip()) for x in raw.split(",") if x.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeframes must be comma-separated seconds") from exc
    if not values or any(x not in SUPPORTED_GRANULARITIES for x in values):
        raise argparse.ArgumentTypeError("only 60 and 900 second timeframes are supported")
    return values


def safe_historical_error_reason(exc: Exception) -> str:
    """Expose only fixed internal reasons and syntactically valid public API codes."""
    args = getattr(exc, "args", ())
    if len(args) == 1 and isinstance(args[0], str):
        reason = args[0]
        if re.fullmatch(r"HISTORICAL_[A-Z0-9_]+", reason):
            return reason
        if re.fullmatch(r"DERIV_HISTORICAL_[A-Z0-9_]+", reason):
            return reason
        match = re.fullmatch(
            r"DERIV_HISTORICAL_REQUEST_FAILED:([A-Za-z][A-Za-z0-9_]{0,63})",
            reason,
        )
        if match:
            return reason
        match = re.fullmatch(
            r"DERIV_HISTORICAL_API_REJECTED:([A-Za-z][A-Za-z0-9_]{0,63})",
            reason,
        )
        if match:
            return reason
        match = re.fullmatch(
            r"DERIV_HISTORICAL_RESPONSE_TYPE_INVALID:(history|tick|ohlc|candles)",
            reason,
        )
        if match:
            return reason
        match = re.fullmatch(
            r"DERIV_HISTORICAL_SOURCE_RETURNED_OUT_OF_RANGE_CANDLES:"
            r"requested_start=[0-9]+:requested_end=[0-9]+:"
            r"actual_first=[0-9]+:actual_last=[0-9]+",
            reason,
        )
        if match:
            return reason
        match = re.fullmatch(
            r"DERIV_HISTORICAL_GAP_OR_TRUNCATION_DETECTED:"
            r"expected_count=[0-9]+:actual_count=[0-9]+:"
            r"expected_first=[0-9]+:expected_last=[0-9]+:"
            r"actual_first=[0-9]+:actual_last=[0-9]+",
            reason,
        )
        if match:
            return reason
    return "UNCLASSIFIED_" + type(exc).__name__.upper()


def main() -> int:
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="R_100")
    parser.add_argument("--start-epoch", type=int, required=True)
    parser.add_argument("--end-epoch", type=int, required=True)
    parser.add_argument("--timeframes", type=_parse_timeframes, default=(60, 900))
    parser.add_argument("--output-dir", default="artifacts/r100-historical")
    parser.add_argument("--chunk-bars", type=int, default=900)
    parser.add_argument("--request-delay-seconds", type=float, default=0.35)
    parser.add_argument("--api-variant", choices=tuple(API_VARIANTS), default="new")
    args = parser.parse_args()
    try:
        manifest = asyncio.run(collect_historical_dataset(
            symbol=args.symbol, start_epoch=args.start_epoch, end_epoch=args.end_epoch,
            granularities=args.timeframes, output_dir=args.output_dir,
            source_commit=os.environ.get("GITHUB_SHA", ""),
            chunk_bars=args.chunk_bars,
            request_delay_seconds=args.request_delay_seconds,
            api_variant=args.api_variant,
        ))
    except Exception as exc:
        print("R100_HISTORICAL_COLLECTION=FAILED")
        print("REASON=" + safe_historical_error_reason(exc))
        return 2
    total = sum(x["bar_count"] for x in manifest["datasets"])
    print("R100_HISTORICAL_COLLECTION=COMPLETE")
    print(f"R100_HISTORICAL_SYMBOL={args.symbol}")
    print(f"R100_HISTORICAL_BARS={total}")
    print(f"R100_HISTORICAL_MANIFEST={Path(args.output_dir) / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
