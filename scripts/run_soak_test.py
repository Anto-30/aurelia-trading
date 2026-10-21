#!/usr/bin/env python3
"""Read-only Deriv market-data soak with ping RTT, signal-processing and reconnect telemetry.

Default target is 3,600 elapsed seconds. This does not authorize an account, place
orders, test broker order rejection, or prove strategy profitability. The public
market-data stream needs a numeric app ID but no Deriv account token. A short smoke
run is useful for debugging but never qualifies as the 3,600-second soak artifact.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import websocket
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException

try:
    from runtime.strategy.autonomous_signal_engine import AutonomousSignalHunter
except Exception:
    AutonomousSignalHunter = None  # transport-only soak remains possible; reported below

WS_BASE = "wss://ws.derivws.com/websockets/v3"
REQUIRED_DURATION_SECONDS = 3600
LATENCY_THRESHOLD_MS = 200.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * p)
    return float(ordered[index])


def write_event(stream, event: dict[str, Any]) -> None:
    stream.write(json.dumps({"timestamp_utc": utc_now(), **event}, allow_nan=False) + "\n")
    stream.flush()


def run_soak(app_id: str, duration_seconds: int, out_dir: Path) -> dict[str, Any]:
    if not app_id.isdigit():
        raise ValueError("DERIV_APP_ID must be numeric")
    if not 1 <= duration_seconds <= 86400:
        raise ValueError("duration must be between 1 and 86,400 seconds")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = out_dir / f"deriv_soak_{stamp}.jsonl"
    summary_path = out_dir / f"deriv_soak_{stamp}.summary.json"
    uri = f"{WS_BASE}?app_id={app_id}"

    start = time.monotonic()
    deadline = start + duration_seconds
    ws = None
    next_ping_at = start
    next_req_id = 700000
    pending_pings: dict[int, float] = {}
    ping_rtt: list[float] = []
    processing_ms: list[float] = []
    interarrival_ms: list[float] = []
    last_tick_at: float | None = None
    tick_count = 0
    signal_count = 0
    direction_transitions = 0
    last_direction: str | None = None
    disconnects = 0
    connection_attempts = 0
    successful_connections = 0
    reconnects = 0
    errors: list[str] = []
    max_consecutive_errors = 0
    consecutive_errors = 0
    hunter = AutonomousSignalHunter() if AutonomousSignalHunter is not None else None

    def connect() -> Any:
        nonlocal ws, connection_attempts, successful_connections, reconnects
        connection_attempts += 1
        candidate = websocket.create_connection(uri, timeout=10, enable_multithread=True)
        candidate.settimeout(1.0)
        candidate.send(json.dumps({"ticks": "R_100", "subscribe": 1, "req_id": 700001}))
        ws = candidate
        successful_connections += 1
        if successful_connections > 1:
            reconnects += 1
        write_event(log, {
            "event": "connected" if successful_connections == 1 else "reconnected",
            "connection_attempt": connection_attempts,
        })
        return candidate

    with log_path.open("w", encoding="utf-8") as log:
        write_event(log, {
            "event": "soak_started", "target_duration_seconds": duration_seconds,
            "symbol": "R_100", "account_authorization_used": False,
            "orders_submitted": 0, "signal_engine_available": hunter is not None,
        })
        while time.monotonic() < deadline:
            if ws is None:
                try:
                    connect()
                    consecutive_errors = 0
                    next_ping_at = time.monotonic()
                except Exception as exc:
                    disconnects += 1
                    consecutive_errors += 1
                    max_consecutive_errors = max(max_consecutive_errors, consecutive_errors)
                    errors.append(f"{type(exc).__name__}: connection attempt failed")
                    write_event(log, {"event": "connect_failed", "error_type": type(exc).__name__})
                    time.sleep(min(5.0, max(0.0, deadline - time.monotonic())))
                    continue

            now = time.monotonic()
            if now >= next_ping_at:
                next_req_id += 1
                pending_pings[next_req_id] = now
                try:
                    ws.send(json.dumps({"ping": 1, "req_id": next_req_id}))
                except Exception as exc:
                    disconnects += 1
                    consecutive_errors += 1
                    max_consecutive_errors = max(max_consecutive_errors, consecutive_errors)
                    errors.append(f"{type(exc).__name__}: ping send failed")
                    write_event(log, {"event": "send_failed", "error_type": type(exc).__name__})
                    try:
                        ws.close()
                    except Exception:
                        pass
                    ws = None
                    continue
                next_ping_at = now + 30.0

            try:
                # Keep each blocking read bounded by both one second and the remaining
                # test interval, so the run does not deliberately sleep past its deadline.
                ws.settimeout(max(0.05, min(1.0, deadline - time.monotonic())))
                raw = ws.recv()
                received_at = time.monotonic()
                message = json.loads(raw)
            except WebSocketTimeoutException:
                continue
            except (WebSocketConnectionClosedException, OSError, ValueError, json.JSONDecodeError) as exc:
                disconnects += 1
                consecutive_errors += 1
                max_consecutive_errors = max(max_consecutive_errors, consecutive_errors)
                errors.append(f"{type(exc).__name__}: connection/message failure")
                write_event(log, {"event": "disconnected", "error_type": type(exc).__name__})
                try:
                    ws.close()
                except Exception:
                    pass
                ws = None
                continue
            except Exception as exc:
                disconnects += 1
                consecutive_errors += 1
                max_consecutive_errors = max(max_consecutive_errors, consecutive_errors)
                errors.append(f"{type(exc).__name__}: unexpected receive failure")
                write_event(log, {"event": "unexpected_receive_error", "error_type": type(exc).__name__})
                try:
                    ws.close()
                except Exception:
                    pass
                ws = None
                continue

            if message.get("error"):
                code = message["error"].get("code", "unknown")
                write_event(log, {"event": "api_error", "api_error_code": str(code)})
                # Public API errors should not trigger endless rapid resubscription.
                consecutive_errors += 1
                max_consecutive_errors = max(max_consecutive_errors, consecutive_errors)
                try:
                    ws.close()
                except Exception:
                    pass
                ws = None
                continue

            req_id = message.get("req_id")
            if isinstance(req_id, int) and req_id in pending_pings:
                sent_at = pending_pings.pop(req_id)
                rtt = max(0.0, (received_at - sent_at) * 1000.0)
                ping_rtt.append(rtt)
                write_event(log, {"event": "ping_rtt", "rtt_ms": rtt, "over_200ms": rtt > LATENCY_THRESHOLD_MS})

            tick = message.get("tick")
            if isinstance(tick, dict):
                try:
                    quote = float(tick["quote"])
                    if not math.isfinite(quote) or quote <= 0:
                        raise ValueError("invalid_quote")
                    tick_count += 1
                    if last_tick_at is not None:
                        interarrival_ms.append(max(0.0, (received_at - last_tick_at) * 1000.0))
                    last_tick_at = received_at

                    process_start = time.monotonic()
                    candidate = None
                    if hunter is not None:
                        candidate = hunter.observe(
                            symbol="R_100", quote=quote,
                            received_at=datetime.now(timezone.utc),
                        )
                    process_elapsed_ms = max(0.0, (time.monotonic() - process_start) * 1000.0)
                    processing_ms.append(process_elapsed_ms)
                    if candidate is not None:
                        signal_count += 1
                        if last_direction is not None and candidate.direction != last_direction:
                            direction_transitions += 1
                        last_direction = candidate.direction
                        write_event(log, {
                            "event": "research_signal_candidate",
                            "direction": candidate.direction,
                            "probability_status": candidate.probability_status,
                            "order_submission_permitted": False,
                            "processing_ms": process_elapsed_ms,
                        })
                    if tick_count % 100 == 0:
                        write_event(log, {
                            "event": "progress", "tick_count": tick_count,
                            "signal_candidate_count": signal_count,
                            "processing_ms_last": process_elapsed_ms,
                        })
                except Exception as exc:
                    errors.append(f"{type(exc).__name__}: tick processing failure")
                    write_event(log, {"event": "tick_processing_error", "error_type": type(exc).__name__})

            if consecutive_errors:
                consecutive_errors = 0

        actual_elapsed = time.monotonic() - start
        write_event(log, {
            "event": "soak_stopped", "actual_elapsed_seconds": actual_elapsed,
            "target_duration_seconds": duration_seconds, "tick_count": tick_count,
        })
        try:
            if ws is not None:
                ws.close()
        except Exception:
            pass

    max_ping = max(ping_rtt) if ping_rtt else None
    max_processing = max(processing_ms) if processing_ms else None
    full_duration = duration_seconds == REQUIRED_DURATION_SECONDS and actual_elapsed >= REQUIRED_DURATION_SECONDS
    technical_pass = bool(
        full_duration and tick_count > 0 and ping_rtt and processing_ms
        and max_ping is not None and max_ping <= LATENCY_THRESHOLD_MS
        and max_processing is not None and max_processing <= LATENCY_THRESHOLD_MS
        and not errors
    )
    summary = {
        "schema": "aurelia.deriv_public_soak.v1",
        "target_duration_seconds": duration_seconds,
        "actual_elapsed_seconds": round(actual_elapsed, 3),
        "full_3600_second_run": full_duration,
        "symbol": "R_100",
        "transport": "Deriv public market data websocket",
        "account_authorization_used": False,
        "orders_submitted": 0,
        "tick_count": tick_count,
        "ping_count": len(ping_rtt),
        "ping_rtt_mean_ms": statistics.fmean(ping_rtt) if ping_rtt else None,
        "ping_rtt_p95_ms": percentile(ping_rtt, .95),
        "ping_rtt_max_ms": max_ping,
        "tick_interarrival_mean_ms": statistics.fmean(interarrival_ms) if interarrival_ms else None,
        "signal_engine_available": hunter is not None,
        "signal_processing_mean_ms": statistics.fmean(processing_ms) if processing_ms else None,
        "signal_processing_p95_ms": percentile(processing_ms, .95),
        "signal_processing_max_ms": max_processing,
        "research_signal_candidate_count": signal_count,
        "candidate_direction_transitions": direction_transitions,
        "connection_attempts": connection_attempts,
        "successful_connections": successful_connections,
        "reconnects_observed": reconnects,
        "disconnects_or_connection_errors": disconnects,
        "max_consecutive_errors": max_consecutive_errors,
        "errors_count": len(errors),
        "error_categories": sorted({x.split(":")[0] for x in errors}),
        "latency_threshold_ms": LATENCY_THRESHOLD_MS,
        "max_ping_rtt_within_threshold": max_ping is not None and max_ping <= LATENCY_THRESHOLD_MS,
        "max_signal_processing_within_threshold": max_processing is not None and max_processing <= LATENCY_THRESHOLD_MS,
        "technical_soak_pass": technical_pass,
        "manual_10_second_network_recovery_test": "NOT_PERFORMED_BY_THIS_SCRIPT",
        "broker_readonly_and_trade_rejection_test": "NOT_PERFORMED",
        "strategy_edge_or_profitability_proven": False,
        "final_execution_authorization": False,
        "live_execution": "BLOCKED",
        "raw_log_path": str(log_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("DERIV_SOAK=COMPLETED" if actual_elapsed >= duration_seconds else "DERIV_SOAK=INCOMPLETE")
    print(f"TARGET_DURATION_SECONDS={duration_seconds}")
    print(f"ACTUAL_ELAPSED_SECONDS={actual_elapsed:.3f}")
    print(f"TICK_COUNT={tick_count}")
    print(f"PING_COUNT={len(ping_rtt)}")
    print(f"PING_RTT_MEAN_MS={summary['ping_rtt_mean_ms']}")
    print(f"PING_RTT_MAX_MS={max_ping}")
    print(f"SIGNAL_PROCESSING_MEAN_MS={summary['signal_processing_mean_ms']}")
    print(f"SIGNAL_PROCESSING_MAX_MS={max_processing}")
    print(f"RECONNECTS_OBSERVED={reconnects}")
    print("MANUAL_10_SECOND_RECOVERY_TEST=NOT_PERFORMED")
    print(f"TECHNICAL_SOAK_PASS={str(technical_pass).lower()}")
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    print(f"RAW_LOG_PATH={log_path}")
    print(f"SUMMARY_PATH={summary_path}")
    return 0 if actual_elapsed >= duration_seconds and tick_count > 0 else 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-id", default=os.getenv("DERIV_APP_ID"),
                        help="numeric app ID; no account token is needed for public ticks")
    parser.add_argument("--duration-seconds", type=int, default=REQUIRED_DURATION_SECONDS)
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/soak"))
    args = parser.parse_args()
    if not args.app_id or not str(args.app_id).isdigit():
        parser.error("Set DERIV_APP_ID or pass --app-id; do not provide a Deriv account token.")
    try:
        return run_soak(str(args.app_id), args.duration_seconds, args.out_dir)
    except KeyboardInterrupt:
        print("DERIV_SOAK=INTERRUPTED")
        print("SOAK_EVIDENCE_QUALIFIED=false")
        return 130
    except Exception as exc:
        print("DERIV_SOAK=FAILED")
        print(f"REASON={type(exc).__name__}: {exc}")
        print("FINAL_EXECUTION_AUTHORIZATION=false")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
