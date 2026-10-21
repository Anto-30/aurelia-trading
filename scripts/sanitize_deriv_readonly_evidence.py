#!/usr/bin/env python3
"""Create a minimized, privacy-preserving summary from private Deriv evidence files.

Raw inputs stay on the ephemeral runner under /tmp and must never be uploaded.
The public artifact contains verification booleans and hashes only: no account
IDs, balances, symbols, proposal/intent IDs, contract IDs, or transaction rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}: evidence root must be an object")
    if value.get("result") != "PROVEN" or value.get("status") != "CURRENT":
        raise ValueError(f"{label}: evidence is not current and proven")
    if value.get("orders_submitted") != 0:
        raise ValueError(f"{label}: order submission count is not zero")
    if value.get("capital_authority_granted") is not False:
        raise ValueError(f"{label}: capital authority must remain false")
    if value.get("order_submission_permitted") is not False:
        raise ValueError(f"{label}: order submission permission must remain false")
    if not value.get("record_hash") or not value.get("data_hash"):
        raise ValueError(f"{label}: evidence hashes are missing")
    if not isinstance(value.get("observed"), dict):
        raise ValueError(f"{label}: observed section is missing")
    return value


def _record(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": value.get("evidence_id"),
        "source_hash": value.get("source_hash"),
        "config_hash": value.get("config_hash"),
        "data_hash": value.get("data_hash"),
        "record_hash": value.get("record_hash"),
        "started_at_utc": value.get("started_at_utc"),
        "ended_at_utc": value.get("ended_at_utc"),
        "valid_until_utc": value.get("valid_until_utc"),
        "verification_scope": value.get("verification_scope"),
        "result": value.get("result"),
        "status": value.get("status"),
    }


def build_summary(session_path: Path, broker_path: Path, lifecycle_path: Path) -> dict[str, Any]:
    session = _load(session_path, "session")
    broker = _load(broker_path, "broker")
    lifecycle = _load(lifecycle_path, "lifecycle")
    s = session["observed"]
    b = broker["observed"]
    l = lifecycle["observed"]

    if s.get("environment") != "real" or s.get("currency") != "USD":
        raise ValueError("session environment/currency binding failed")
    if broker.get("verification_scope") != "REAL_DERIV_BROKER_ACCOUNT_READ_ONLY":
        raise ValueError("broker evidence has unexpected scope")
    if b.get("environment") != "real" or b.get("currency") != "USD":
        raise ValueError("broker environment/currency binding failed")
    if b.get("capital_movement_performed_by_verifier") is not False:
        raise ValueError("broker verifier must not move capital")
    if lifecycle.get("verification_scope") != "REAL_DERIV_LIFECYCLE_VERIFY_ONLY":
        raise ValueError("lifecycle evidence has unexpected scope")
    if l.get("mode") != "VERIFY_ONLY" or l.get("broker_submission_performed") is not False:
        raise ValueError("lifecycle was not strictly verify-only")
    if l.get("capital_movement") is not False:
        raise ValueError("lifecycle capital movement must remain false")

    records = {
        "session": _record(session),
        "broker": _record(broker),
        "lifecycle": _record(lifecycle),
    }
    sources = {x["source_hash"] for x in records.values()}
    configs = {x["config_hash"] for x in records.values()}
    if len(sources) != 1 or None in sources or len(configs) != 1 or None in configs:
        raise ValueError("evidence source/configuration hashes are not consistent")

    summary: dict[str, Any] = {
        "schema": "aurelia.deriv_readonly_summary.v1",
        "source_hash": next(iter(sources)),
        "config_hash": next(iter(configs)),
        "checks": {
            "authenticated_session_current": True,
            "real_account_binding_verified": True,
            "currency_binding_verified": True,
            "fresh_balance_snapshot_verified": True,
            "broker_statement_and_portfolio_read_only": True,
            "verify_only_lifecycle_proven": True,
            "orders_submitted": 0,
            "capital_movement": False,
            "capital_authority_granted": False,
            "order_submission_permitted": False,
        },
        "source_evidence": records,
        "sensitive_fields_redacted": True,
    }
    canon = json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    summary["summary_sha256"] = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--broker", type=Path, required=True)
    parser.add_argument("--lifecycle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = build_summary(args.session, args.broker, args.lifecycle)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_name(args.out.name + ".tmp")
    tmp.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(args.out)
    print("DERIV_READONLY_SUMMARY=VERIFIED")
    print(f"DERIV_READONLY_SUMMARY_SHA256={result['summary_sha256']}")
    print("SENSITIVE_FIELDS_REDACTED=true")
    print("ORDERS_SUBMITTED=0")
    print("CAPITAL_MOVEMENT=false")
    print("CAPITAL_AUTHORITY_GRANTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
