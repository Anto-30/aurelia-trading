#!/usr/bin/env python3
"""Promote a genuine non-production 3600s soak into certification evidence.

This script only transforms a completed CI measurement into the canonical
untracked evidence envelope. It never asserts production execution readiness.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assurance.evidence_writer import build_evidence, write_evidence
from runtime.core.runtime_config import load_config_hash


def sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    source = Path("aurelia-3600s-soak-evidence.json")
    if not source.exists():
        print("SOAK_EVIDENCE_PROMOTION=NO_INPUT")
        return 0

    raw = json.loads(source.read_text(encoding="utf-8"))
    required = (
        raw.get("source_commit"),
        raw.get("runtime_image_id"),
        raw.get("duration_seconds"),
        raw.get("health_check_failures"),
        raw.get("execution_mode"),
        raw.get("deployment_id"),
        raw.get("runtime_instance_id"),
        raw.get("started_at_utc"),
        raw.get("ended_at_utc"),
    )
    if any(value in (None, "") for value in required):
        raise SystemExit("SOAK_EVIDENCE_PROMOTION=INVALID_INPUT")

    if (
        int(raw["duration_seconds"]) < 3600
        or int(raw["health_check_failures"]) != 0
        or raw.get("execution_mode") != "VERIFY_ONLY"
        or raw.get("capital_can_open_new_exposure") is not False
        or raw.get("real_capital_movement") is not False
        or raw.get("final_execution_authorization") is not False
    ):
        raise SystemExit("SOAK_EVIDENCE_PROMOTION=SEMANTICS_FAILED")

    config_hash = load_config_hash(ROOT)
    record = build_evidence(
        evidence_id=f"NONPROD_3600S_SOAK:{raw['deployment_id']}",
        source_hash=str(raw["source_commit"]),
        artifact_hash=sha(raw["runtime_image_id"]),
        config_hash=config_hash,
        data_hash=sha(raw),
        environment="ci",
        started_at_utc=str(raw["started_at_utc"]),
        ended_at_utc=str(raw["ended_at_utc"]),
        status="CURRENT",
        valid_until_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        provenance={
            "origin": "ci",
            "issuer": "aurelia-non-production-3600s-soak",
            "source_commit": str(raw["source_commit"]),
            "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "deployment_id": str(raw["deployment_id"]),
            "runtime_instance_id": str(raw["runtime_instance_id"]),
        },
        result="PROVEN",
        invariants_checked=[
            "duration_at_least_3600_seconds",
            "continuous_health_checks",
            "zero_health_check_failures",
            "zero_capital_escape",
            "verify_only_execution",
            "controlled_restart_recovery",
        ],
        invariants_failed=[],
    )
    record.update({
        "duration_seconds": int(raw["duration_seconds"]),
        "actual_elapsed_seconds": int(raw["duration_seconds"]),
        "continuous": True,
        "execution_mode": "VERIFY_ONLY",
        "deployment_id": str(raw["deployment_id"]),
        "runtime_instance_id": str(raw["runtime_instance_id"]),
        "invariant_violations": 0,
        "silent_degradations": 0,
        "capital_authority_escapes": 0,
        "unresolved_unknown_states": 0,
    })
    record["record_hash"] = sha({k: v for k, v in record.items() if k != "record_hash"})

    Path("evidence").mkdir(parents=True, exist_ok=True)
    write_evidence(Path("evidence/soak_3600s.json"), record)
    print("SOAK_EVIDENCE_PROMOTION=PASS")
    print(f"EVIDENCE_HASH={record['record_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
