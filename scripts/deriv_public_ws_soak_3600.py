from __future__ import annotations

"""Read-only Deriv public market-data WebSocket soak.

Tests public symbol discovery, tick subscription, keepalive and controlled
reconnect/re-subscription. It loads no credentials and cannot authenticate,
submit/modify orders, or move capital. It does not test strategy P&L,
authenticated lifecycle, or production trading readiness.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


class HashChainWriter:
    def __init__(self, path: Path, source_sha: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("x", encoding="utf-8")
        self._source_sha = source_sha
        self._sequence = 0
        self._previous_hash = "0" * 64

    def append(self, event_type: str, **fields: Any) -> str:
        self._sequence += 1
        body = {
            "sequence": self._sequence,
            "event_type": event_type,
            "observed_at_utc": _utc_now(),
            "source_sha": self._source_sha,
            "previous_hash": self._previous_hash,
            **fields,
        }
        digest = hashlib.sha256(
            self._previous_hash.encode("ascii") + _canonical_bytes(body)
        ).hexdigest()
        self._file.write(json.dumps(
            {**body, "record_hash": digest}, sort_keys=True, allow_nan=False
        ) + "\n")
        self._file.flush()
        os.fsync(self._file.fileno())
        self._previous_hash = digest
        return digest

    @property
    def last_hash(self) -> str:
        return self._previous_hash

    def close(self) -> None:
        self._file.close()


def _valid_tick(message: dict[str, Any], expected_symbol: str) -> tuple[int, float]:
    if not isinstance(message, dict) or message.get("msg_type") != "tick":
        raise RuntimeError("PUBLIC_TICK_MESSAGE_TYPE_INVALID")
    tick = message.get("tick")
    if not isinstance(tick, dict):
        raise RuntimeError("PUBLIC_TICK_PAYLOAD_MISSING")
    # The public Deriv tick schema can omit tick.symbol. The subscription is
    # already bound to expected_symbol; validate the echo whenever provided.
    echoed_symbol = tick.get("symbol")
    if echoed_symbol is not None and echoed_symbol != expected_symbol:
        raise RuntimeError("PUBLIC_TICK_SYMBOL_MISMATCH")
    epoch = tick.get("epoch")
    if type(epoch) is not int or epoch <= 0:
        raise RuntimeError("PUBLIC_TICK_EPOCH_INVALID")
    quote = tick.get("quote")
    if isinstance(quote, bool) or not isinstance(quote, (int, float)):
        raise RuntimeError("PUBLIC_TICK_QUOTE_INVALID")
    value = float(quote)
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError("PUBLIC_TICK_QUOTE_INVALID")
    return epoch, value


async def run_public_ws_soak(
    *,
    symbol: str,
    duration_seconds: int,
    reconnect_interval_seconds: int,
    recovery_timeout_seconds: int,
    evidence_path: Path,
    summary_path: Path,
    transport_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("SOAK_SYMBOL_REQUIRED")
    for name, value in (
        ("duration_seconds", duration_seconds),
        ("reconnect_interval_seconds", reconnect_interval_seconds),
        ("recovery_timeout_seconds", recovery_timeout_seconds),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("SOAK_" + name.upper() + "_INVALID")
    if reconnect_interval_seconds >= duration_seconds:
        raise ValueError("SOAK_RECONNECT_INTERVAL_MUST_BE_SHORTER_THAN_DURATION")

    if transport_factory is None:
        from runtime.adapters.deriv_ws import DerivWebSocketTransport
        transport_factory = DerivWebSocketTransport

    source_sha = (
        os.getenv("GITHUB_SHA", "").strip()
        or os.getenv("AURELIA_SOURCE_SHA", "").strip()
        or "LOCAL_UNPINNED"
    )
    writer = HashChainWriter(evidence_path, source_sha)
    transport = None
    stream = None
    next_tick: asyncio.Task | None = None
    start = time.monotonic()
    deadline = start + duration_seconds
    next_reconnect = start + reconnect_interval_seconds
    first_tick_deadline = start + recovery_timeout_seconds
    recovery_deadline: float | None = None
    reconnect_started: float | None = None
    reconnect_baseline_epoch: int | None = None
    tick_count = 0
    reconnect_count = 0
    recovery_success_count = 0
    out_of_order_count = 0
    invalid_messages = 0
    tick_gap_count = 0
    max_interarrival_gap = 0.0
    prior_epoch: int | None = None
    prior_received: float | None = None
    error_text: str | None = None
    elapsed = 0.0
    status = "FAIL"

    writer.append(
        "SOAK_STARTED",
        endpoint=PUBLIC_WS_URL,
        symbol=symbol,
        duration_seconds=duration_seconds,
        reconnect_interval_seconds=reconnect_interval_seconds,
        recovery_timeout_seconds=recovery_timeout_seconds,
        authentication_used=False,
        capital_authority=False,
        order_submission_permitted=False,
    )

    try:
        transport = transport_factory(PUBLIC_WS_URL, timeout_seconds=10.0)
        await transport.connect()
        active_reply = await transport.request({"active_symbols": "brief"})
        rows = active_reply.get("active_symbols") if isinstance(active_reply, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError("ACTIVE_SYMBOLS_RESPONSE_INVALID")
        if not any(
            isinstance(row, dict)
            and row.get("underlying_symbol") == symbol
            for row in rows
        ):
            raise RuntimeError("SOAK_SYMBOL_NOT_IN_ACTIVE_SYMBOLS")
        writer.append("PUBLIC_SYMBOL_VERIFIED", active_symbol_count=len(rows))

        stream = transport.subscribe("ticks:" + symbol, {"ticks": symbol})
        next_tick = asyncio.create_task(stream.__anext__())

        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_reconnect and now < deadline:
                reconnect_count += 1
                reconnect_baseline_epoch = prior_epoch
                writer.append(
                    "CONTROLLED_RECONNECT_STARTED",
                    reconnect_number=reconnect_count,
                    last_pre_reconnect_tick_epoch=reconnect_baseline_epoch,
                )
                await transport.reconnect()
                reconnect_started = time.monotonic()
                recovery_deadline = reconnect_started + recovery_timeout_seconds
                next_reconnect += reconnect_interval_seconds
                writer.append(
                    "CONTROLLED_RECONNECT_COMPLETE",
                    reconnect_number=reconnect_count,
                )
                continue

            wake_at = min(deadline, next_reconnect)
            if recovery_deadline is not None:
                wake_at = min(wake_at, recovery_deadline)
            if tick_count == 0:
                wake_at = min(wake_at, first_tick_deadline)
            done, _ = await asyncio.wait(
                {next_tick}, timeout=max(0.0, wake_at - now)
            )

            if done:
                try:
                    message = next_tick.result()
                except StopAsyncIteration as exc:
                    raise RuntimeError("PUBLIC_TICK_STREAM_ENDED") from exc
                received = time.monotonic()
                try:
                    epoch, quote_value = _valid_tick(message, symbol)
                except RuntimeError:
                    invalid_messages += 1
                    raise

                if (
                    recovery_deadline is not None
                    and reconnect_baseline_epoch is not None
                    and epoch <= reconnect_baseline_epoch
                ):
                    writer.append(
                        "STALE_PRE_RECONNECT_TICK_IGNORED",
                        reconnect_baseline_epoch=reconnect_baseline_epoch,
                        observed_epoch=epoch,
                    )
                    next_tick = asyncio.create_task(stream.__anext__())
                    continue
                if prior_epoch is not None and epoch < prior_epoch:
                    out_of_order_count += 1
                    writer.append(
                        "OUT_OF_ORDER_TICK",
                        previous_epoch=prior_epoch,
                        observed_epoch=epoch,
                    )
                    raise RuntimeError("PUBLIC_TICK_OUT_OF_ORDER")
                if prior_received is not None:
                    gap = received - prior_received
                    max_interarrival_gap = max(max_interarrival_gap, gap)
                    if gap > recovery_timeout_seconds:
                        tick_gap_count += 1
                        writer.append("TICK_GAP", gap_seconds=round(gap, 6))
                        raise RuntimeError("PUBLIC_TICK_GAP_EXCEEDS_RECOVERY_TIMEOUT")

                prior_epoch = epoch
                prior_received = received
                tick_count += 1
                if recovery_deadline is not None:
                    recovery_success_count += 1
                    writer.append(
                        "RECONNECT_RECOVERED",
                        recovery_seconds=round(
                            received - (reconnect_started or received), 6
                        ),
                        tick_epoch=epoch,
                    )
                    recovery_deadline = None
                    reconnect_started = None
                    reconnect_baseline_epoch = None
                elif tick_count == 1:
                    writer.append("FIRST_TICK_RECEIVED", tick_epoch=epoch)

                if not math.isfinite(quote_value):
                    invalid_messages += 1
                    raise RuntimeError("PUBLIC_TICK_QUOTE_INVALID")
                next_tick = asyncio.create_task(stream.__anext__())
                continue

            now = time.monotonic()
            if tick_count == 0 and now >= first_tick_deadline:
                raise RuntimeError("INITIAL_PUBLIC_TICK_TIMEOUT")
            if recovery_deadline is not None and now >= recovery_deadline:
                raise RuntimeError("PUBLIC_WS_RECONNECT_RECOVERY_TIMEOUT")
            if prior_received is not None and now - prior_received >= recovery_timeout_seconds:
                raise RuntimeError("PUBLIC_TICK_STREAM_STALLED")

        elapsed = time.monotonic() - start
        passed = (
            elapsed >= duration_seconds
            and tick_count > 0
            and recovery_success_count == reconnect_count
            and out_of_order_count == 0
            and invalid_messages == 0
            and tick_gap_count == 0
        )
        status = "PASS" if passed else "FAIL"

    except Exception as exc:
        elapsed = time.monotonic() - start
        raw_reason = str(exc)
        safe_reason = (
            raw_reason
            if re.fullmatch(r"[A-Z0-9_:-]{1,120}", raw_reason)
            else type(exc).__name__.upper()
        )
        error_text = safe_reason
        writer.append(
            "SOAK_FAILED",
            error_class=type(exc).__name__,
            error_reason=safe_reason,
        )
        status = "FAIL"

    finally:
        if next_tick is not None and not next_tick.done():
            next_tick.cancel()
            try:
                await next_tick
            except (asyncio.CancelledError, Exception):
                pass
        if stream is not None:
            try:
                await stream.aclose()
            except Exception:
                pass
        if transport is not None:
            try:
                await transport.close()
            except Exception:
                pass

    writer.append(
        "SOAK_FINISHED",
        status=status,
        elapsed_seconds=round(elapsed, 6),
        tick_count=tick_count,
        reconnect_count=reconnect_count,
        recovery_success_count=recovery_success_count,
        out_of_order_count=out_of_order_count,
        invalid_messages=invalid_messages,
        tick_gap_count=tick_gap_count,
        maximum_interarrival_gap_seconds=round(max_interarrival_gap, 6),
        error=error_text,
    )
    evidence_tail_hash = writer.last_hash
    writer.close()
    evidence_file_hash = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    summary = {
        "schema": "aurelia.deriv_public_ws_soak.v1",
        "evidence_type": "NON_PRODUCTION_READ_ONLY_PUBLIC_WEBSOCKET_SOAK",
        "status": status,
        "source_sha": source_sha,
        "endpoint": PUBLIC_WS_URL,
        "symbol": symbol,
        "target_duration_seconds": duration_seconds,
        "observed_duration_seconds": round(elapsed, 6),
        "tick_count": tick_count,
        "reconnect_count": reconnect_count,
        "recovery_success_count": recovery_success_count,
        "out_of_order_count": out_of_order_count,
        "invalid_messages": invalid_messages,
        "tick_gap_count": tick_gap_count,
        "maximum_interarrival_gap_seconds": round(max_interarrival_gap, 6),
        "error": error_text,
        "authentication_used": False,
        "account_identity_verified": False,
        "broker_transaction": False,
        "capital_movement": False,
        "capital_authority": False,
        "order_submission_permitted": False,
        "strategy_logic_tested": False,
        "strategy_profitability_proven": False,
        "evidence_jsonl_sha256": evidence_file_hash,
        "evidence_hash_chain_tail": evidence_tail_hash,
        "generated_at_utc": _utc_now(),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default=os.getenv("SOAK_SYMBOL", "R_100"))
    parser.add_argument("--duration-seconds", type=int, default=3600)
    parser.add_argument("--reconnect-interval-seconds", type=int, default=900)
    parser.add_argument("--recovery-timeout-seconds", type=int, default=60)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/deriv-public-ws-soak")
    )
    args = parser.parse_args()
    try:
        summary = asyncio.run(
            run_public_ws_soak(
                symbol=args.symbol,
                duration_seconds=args.duration_seconds,
                reconnect_interval_seconds=args.reconnect_interval_seconds,
                recovery_timeout_seconds=args.recovery_timeout_seconds,
                evidence_path=args.output_dir / "evidence.jsonl",
                summary_path=args.output_dir / "summary.json",
            )
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAIL",
            "error": type(exc).__name__ + ":" + str(exc),
        }))
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
