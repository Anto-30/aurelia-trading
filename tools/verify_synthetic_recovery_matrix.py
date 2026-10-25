#!/usr/bin/env python3
"""Synthetic local-only recovery matrix for the Deriv WebSocket transport.

This does not use broker credentials, OTPs, authenticated URLs or order requests.
It tests the transport against a localhost WebSocket server that injects a
connection drop and a rate-limit response. It is supporting unit evidence, not
proof of authenticated broker recovery or protection against real duplicate trades.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets
from websockets.asyncio.server import serve

from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport
from runtime.core.request_ledger import RequestLedger, RequestState


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def run_matrix(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("OUTPUT_DIR_NOT_EMPTY")
    output_dir.mkdir(parents=True, exist_ok=True)
    event_path = output_dir / "recovery_events.jsonl"
    report_path = output_dir / "recovery_matrix.json"
    events: list[dict[str, Any]] = []
    server_requests: list[dict[str, Any]] = []
    server_errors: list[str] = []
    server_connections = 0
    dropped_first_connection = False
    rate_limit_sent = False

    def event(name: str, **fields: Any) -> None:
        row = {"at_utc": utc_now(), "event": name, **fields}
        events.append(row)
        with event_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    async def handler(ws: Any) -> None:
        nonlocal server_connections, dropped_first_connection, rate_limit_sent
        server_connections += 1
        connection_number = server_connections
        event("mock_server_connected", connection_number=connection_number)
        try:
            async for raw in ws:
                request = json.loads(raw)
                if not isinstance(request, dict):
                    server_errors.append("INVALID_REQUEST_TYPE")
                    continue
                req_id = request.get("req_id")
                command_keys = sorted(
                    key for key in request
                    if key not in {"req_id", "subscribe", "forget"}
                )
                server_requests.append({
                    "connection_number": connection_number,
                    "req_id": req_id,
                    "command_keys": command_keys,
                    "subscribe": request.get("subscribe"),
                    "forget_present": "forget" in request,
                })
                if not isinstance(req_id, int):
                    server_errors.append("REQUEST_ID_MISSING")
                    continue

                if "active_symbols" in request and connection_number == 1:
                    await ws.send(json.dumps({
                        "req_id": req_id,
                        "msg_type": "active_symbols",
                        "active_symbols": [{"underlying_symbol": "SYNTHETIC_TEST_SYMBOL"}],
                    }))
                    if not dropped_first_connection:
                        dropped_first_connection = True
                        event("injected_network_drop", connection_number=connection_number)
                        await ws.close(code=1011, reason="synthetic drop for recovery test")
                        return
                elif "balance" in request and not rate_limit_sent:
                    rate_limit_sent = True
                    await ws.send(json.dumps({
                        "req_id": req_id,
                        "error": {"code": "RateLimit", "message": "synthetic rate limit"},
                    }))
                    event("injected_rate_limit", req_id=req_id)
                elif "active_symbols" in request:
                    await ws.send(json.dumps({
                        "req_id": req_id,
                        "msg_type": "active_symbols",
                        "active_symbols": [{"underlying_symbol": "SYNTHETIC_TEST_SYMBOL"}],
                    }))
                elif "ticks" in request and request.get("subscribe") == 1:
                    await ws.send(json.dumps({
                        "req_id": req_id,
                        "msg_type": "tick",
                        "tick": {
                            "symbol": request["ticks"],
                            "epoch": 1_800_000_000 + connection_number,
                            "quote": "100.25",
                        },
                        "subscription": {"id": "synthetic-subscription-" + str(connection_number)},
                    }))
                elif "forget" in request:
                    await ws.send(json.dumps({"req_id": req_id, "msg_type": "forget"}))
                else:
                    server_errors.append("UNEXPECTED_COMMAND:" + ",".join(command_keys))
                    await ws.send(json.dumps({
                        "req_id": req_id,
                        "error": {"code": "InvalidRequest", "message": "unexpected synthetic test command"},
                    }))
        except Exception as exc:
            server_errors.append("SERVER_HANDLER:" + type(exc).__name__)

    started_at = utc_now()
    tests: dict[str, dict[str, Any]] = {}
    transport: DerivWebSocketTransport | None = None
    request_ids: list[int] = []
    ledger = RequestLedger(max_pending_age_seconds=30.0)

    try:
        async with serve(handler, "127.0.0.1", 0, ping_interval=None) as server:
            port = server.sockets[0].getsockname()[1]
            local_url = "ws://127.0.0.1:" + str(port)
            transport = DerivWebSocketTransport(local_url, timeout_seconds=2.0, ping_interval=1.0)
            await transport.connect()
            first = await transport.request({"active_symbols": "brief"})
            request_ids.append(int(first["req_id"]))
            tests["initial_request_response_correlation"] = {
                "status": "PASS" if first.get("active_symbols") else "FAIL",
                "req_id": first.get("req_id"),
            }
            # Wait for the simulated server drop to be observed by the single reader.
            deadline = time.monotonic() + 2.0
            while transport.ws is not None and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            tests["network_drop_detected"] = {
                "status": "PASS" if transport.ws is None else "FAIL",
                "detail": "Synthetic local server closed connection after a valid response",
            }
            try:
                await transport.request({"active_symbols": "brief"})
                tests["request_fails_closed_while_disconnected"] = {"status": "FAIL"}
            except DerivTransportError as exc:
                tests["request_fails_closed_while_disconnected"] = {
                    "status": "PASS" if "NOT_CONNECTED" in str(exc) else "FAIL",
                    "error_code": str(exc)[:120],
                }

            await transport.reconnect(fresh_url=local_url)
            tests["transport_reconnect"] = {
                "status": "PASS" if transport.ws is not None else "FAIL",
                "connection_count": server_connections,
            }

            try:
                await transport.request({"balance": 1})
                tests["rate_limit_is_not_silent_success"] = {"status": "FAIL"}
            except DerivTransportError as exc:
                tests["rate_limit_is_not_silent_success"] = {
                    "status": "PASS" if "RateLimit" in str(exc) else "FAIL",
                    "error_code": str(exc)[:160],
                }

            second = await transport.request({"active_symbols": "brief"})
            request_ids.append(int(second["req_id"]))
            tests["fresh_request_after_rate_limit"] = {
                "status": "PASS" if second.get("active_symbols") else "FAIL",
                "req_id": second.get("req_id"),
            }

            iterator = transport.subscribe("ticks:R_100", {"ticks": "R_100"})
            tick = await asyncio.wait_for(anext(iterator), timeout=2.0)
            tick_payload = tick.get("tick") or {}
            subscription = tick.get("subscription") or {}
            tests["subscription_restored_after_reconnect"] = {
                "status": "PASS" if (
                    tick.get("msg_type") == "tick"
                    and tick_payload.get("symbol") == "R_100"
                    and subscription.get("id")
                ) else "FAIL",
                "tick_epoch": tick_payload.get("epoch"),
                "subscription_id_received": bool(subscription.get("id")),
            }
            try:
                duplicate_iterator = transport.subscribe("ticks:R_100", {"ticks": "R_100"})
                await asyncio.wait_for(anext(duplicate_iterator), timeout=1.0)
                tests["duplicate_subscription_rejected"] = {"status": "FAIL"}
            except DerivTransportError as exc:
                tests["duplicate_subscription_rejected"] = {
                    "status": "PASS" if "DUPLICATE_SUBSCRIPTION" in str(exc) else "FAIL",
                    "error_code": str(exc)[:120],
                }
            finally:
                await iterator.aclose()
                if "duplicate_iterator" in locals():
                    await duplicate_iterator.aclose()

            # Prove duplicate confirmations for the same request ID do not create a second ledger row.
            tracked = ledger.create_request("synthetic_read", {"active_symbols": "brief"}, req_id=90001)
            confirmed = ledger.confirm(90001, {"req_id": 90001, "active_symbols": []})
            duplicate_confirm = ledger.confirm(90001, {"req_id": 90001, "active_symbols": []})
            tests["request_ledger_duplicate_confirmation_ignored"] = {
                "status": "PASS" if confirmed is tracked and duplicate_confirm is None and ledger.pending_count == 0 else "FAIL",
                "first_confirmation": confirmed is not None,
                "duplicate_confirmation_ignored": duplicate_confirm is None,
                "pending_count_after_confirmation": ledger.pending_count,
            }

            await transport.close()
            transport = None
    except Exception as exc:
        tests["matrix_harness_exception"] = {
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "error_code": str(exc)[:200],
        }
    finally:
        if transport is not None:
            await transport.close()

    all_tests_pass = bool(tests) and all(item.get("status") == "PASS" for item in tests.values())
    unique_ids = len(request_ids) == len(set(request_ids))
    no_trade_commands = not any(
        key in {"buy", "sell", "proposal", "cancel"}
        for request in server_requests
        for key in request.get("command_keys", [])
    )
    no_server_errors = len(server_errors) == 0
    status = "PASS_SYNTHETIC_ONLY" if all_tests_pass and unique_ids and no_trade_commands and no_server_errors else "FAILED"
    report = {
        "schema": "aurelia.synthetic_public_recovery_matrix.v1",
        "status": status,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "environment": "localhost-only mock WebSocket server",
        "authenticated": False,
        "otp_generated_or_requested": False,
        "broker_endpoint_contacted": False,
        "broker_order_or_trade_requests_sent": 0,
        "tests": tests,
        "transport_request_ids": request_ids,
        "request_ids_unique": unique_ids,
        "server_connection_count": server_connections,
        "server_requests": server_requests,
        "server_errors": server_errors,
        "no_trade_commands_sent": no_trade_commands,
        "all_tests_pass": all_tests_pass,
        "scope_limit": "Synthetic transport-level recovery evidence only; does not prove Deriv OTP renewal, authenticated real/demo session recovery or absence of duplicate broker trades.",
        "event_log_path": str(event_path),
    }
    report["event_log_sha256"] = sha256_file(event_path) if event_path.exists() else None
    write_json(report_path, report)
    print("RECOVERY_MATRIX_RESULT=" + status)
    print("RECOVERY_TEST_COUNT=" + str(len(tests)))
    print("RECOVERY_TESTS_PASSED=" + str(sum(1 for v in tests.values() if v.get("status") == "PASS")))
    print("SERVER_CONNECTION_COUNT=" + str(server_connections))
    print("REQUEST_IDS_UNIQUE=" + str(unique_ids).lower())
    print("NO_TRADE_COMMANDS_SENT=" + str(no_trade_commands).lower())
    print("EVENT_LOG_SHA256=" + str(report["event_log_sha256"]))
    print("REPORT_SHA256=" + sha256_file(report_path))
    return report


async def run_cli(output_dir: Path) -> int:
    report = await run_matrix(output_dir)
    return 0 if report["status"] == "PASS_SYNTHETIC_ONLY" else 2


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/recovery_matrix_synthetic"))
    args = parser.parse_args()
    try:
        return asyncio.run(run_cli(args.output_dir))
    except Exception as exc:
        print("RECOVERY_MATRIX_RESULT=BLOCKED")
        print("RECOVERY_MATRIX_REASON=" + type(exc).__name__ + ":" + str(exc)[:160])
        return 2


if __name__ == "__main__":
    sys.exit(main())
