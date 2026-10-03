"""Canonical evidence envelope generator.

Writes deterministic, execution-neutral evidence metadata. It never submits
orders or touches broker state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()

def build_evidence(
    *,
    evidence_id: str,
    source_hash: str,
    artifact_hash: str,
    config_hash: str,
    data_hash: str,
    environment: str,
    started_at_utc: str,
    ended_at_utc: str,
    status: str,
    valid_until_utc: str | None = None,
    result: str = "UNPROVEN",
    invariants_checked: list[str] | None = None,
    invariants_failed: list[str] | None = None,
) -> dict[str, Any]:
    record = {
        "evidence_id": evidence_id,
        "source_hash": source_hash,
        "artifact_hash": artifact_hash,
        "config_hash": config_hash,
        "data_hash": data_hash,
        "environment": environment,
        "started_at_utc": started_at_utc,
        "ended_at_utc": ended_at_utc,
        "status": status,
        "valid_until_utc": valid_until_utc,
        "result": result,
        "invariants_checked": invariants_checked or [],
        "invariants_failed": invariants_failed or [],
    }
    record["record_hash"] = payload_sha256(record)
    return record

def write_evidence(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(record) + "\n", encoding="utf-8")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--evidence-id", required=True)
    parser.add_argument("--source-hash", required=True)
    parser.add_argument("--artifact-hash", required=True)
    parser.add_argument("--config-hash", required=True)
    parser.add_argument("--data-hash", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--ended-at", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--result", default="UNPROVEN")
    args = parser.parse_args()
    record = build_evidence(
        evidence_id=args.evidence_id,
        source_hash=args.source_hash,
        artifact_hash=args.artifact_hash,
        config_hash=args.config_hash,
        data_hash=args.data_hash,
        environment=args.environment,
        started_at_utc=args.started_at,
        ended_at_utc=args.ended_at,
        status=args.status,
        result=args.result,
    )
    write_evidence(Path(args.out), record)
    print(f"EVIDENCE_WRITTEN={args.out}")
    print(f"EVIDENCE_HASH={record['record_hash']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
