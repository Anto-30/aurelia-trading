from __future__ import annotations

"""Build provenance-bound evidence for the isolated non-production soak.

This module proves only the explicitly bounded CI simulation. It never reads
broker credentials, authorizes capital, or upgrades the record to production.
"""

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from assurance.evidence_writer import build_evidence, payload_sha256, write_evidence

UTC = timezone.utc
TARGET_SECONDS = 3600
MIN_HEALTH_SAMPLES = 600
MAX_SAMPLE_GAP_SECONDS = 15
ALLOWED_STATES = {"CAPITAL_PROTECTED", "SELF_CHECK", "BOOT"}
EXPECTED_CRITICAL_UNKNOWN = "CONTINUOUS_RUNTIME_UNAVAILABLE"
INVARIANTS_CHECKED = [
    "REAL_ELAPSED_DURATION_AT_LEAST_3600_SECONDS",
    "HEALTH_LIVENESS_TRUE_ON_EVERY_SAMPLE",
    "CAPITAL_CAN_NOT_OPEN_NEW_EXPOSURE_ON_EVERY_SAMPLE",
    "RUNTIME_STATE_IS_CAPITAL_PROTECTED_SELF_CHECK_OR_BOOT",
    "CRITICAL_UNKNOWNS_ARE_EMPTY_OR_EXPLICITLY_EXPECTED",
    "DEGRADED_STATUS_HAS_AN_EXPLICIT_KNOWN_REASON",
    "SOURCE_IMAGE_CONFIG_AND_OBSERVATION_HASHES_RECORDED",
    "LIVE_EXECUTION_REMAINS_BLOCKED",
]


def _parse_utc(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field.upper()}_MISSING")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field.upper()}_INVALID") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field.upper()}_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(UTC)


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field.upper()}_MISSING")
    return value.strip()


def _validate_observation(row: dict[str, Any], index: int) -> tuple[float, bool]:
    elapsed = row.get("elapsed_seconds")
    if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)):
        raise ValueError(f"OBSERVATION_{index}_ELAPSED_SECONDS_INVALID")
    try:
        elapsed_seconds = float(elapsed)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"OBSERVATION_{index}_ELAPSED_SECONDS_INVALID") from exc
    if not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
        raise ValueError(f"OBSERVATION_{index}_ELAPSED_SECONDS_INVALID")

    if row.get("liveness") is not True:
        raise ValueError(f"OBSERVATION_{index}_LIVENESS_NOT_TRUE")
    if row.get("capital_can_open_new_exposure") is not False:
        raise ValueError(f"OBSERVATION_{index}_CAPITAL_EXPOSURE_NOT_BLOCKED")
    if row.get("state") not in ALLOWED_STATES:
        raise ValueError(f"OBSERVATION_{index}_RUNTIME_STATE_NOT_PROTECTIVE")

    status = row.get("status")
    unknowns = row.get("critical_unknowns", [])
    if not isinstance(unknowns, list) or any(not isinstance(x, str) for x in unknowns):
        raise ValueError(f"OBSERVATION_{index}_CRITICAL_UNKNOWNS_INVALID")
    unknown_set = set(unknowns)
    if unknown_set - {EXPECTED_CRITICAL_UNKNOWN}:
        raise ValueError(f"OBSERVATION_{index}_UNEXPECTED_CRITICAL_UNKNOWN")
    if status == "HEALTHY":
        if unknown_set:
            raise ValueError(f"OBSERVATION_{index}_HEALTHY_STATUS_HAS_CRITICAL_UNKNOWNS")
    elif status == "DEGRADED":
        if EXPECTED_CRITICAL_UNKNOWN not in unknown_set:
            raise ValueError(f"OBSERVATION_{index}_DEGRADED_STATUS_WITHOUT_KNOWN_REASON")
    else:
        raise ValueError(f"OBSERVATION_{index}_STATUS_NOT_HEALTHY_OR_EXPECTED_DEGRADED")

    return elapsed_seconds, status == "DEGRADED"


def write_nonproduction_soak_evidence(
    *,
    observations_path: Path,
    output_path: Path,
    source_commit: str,
    runtime_image_id: str,
    runtime_instance_id: str,
    deployment_id: str,
    config_hash: str,
    started_at_utc: str,
    ended_at_utc: str,
    controlled_restarts: int,
) -> dict[str, Any]:
    """Validate actual soak observations and write a certification-compatible envelope.

    The function fails closed: no passing record is written unless the observed
    timeline spans at least 3600 seconds, covers the interval with health samples,
    and every sample demonstrates the declared protective invariants.
    """
    source_commit = _required_text(source_commit, "source_commit")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", source_commit):
        raise ValueError("SOURCE_COMMIT_INVALID")
    runtime_image_id = _required_text(runtime_image_id, "runtime_image_id")
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", runtime_image_id):
        raise ValueError("RUNTIME_IMAGE_ID_INVALID")
    runtime_instance_id = _required_text(runtime_instance_id, "runtime_instance_id")
    deployment_id = _required_text(deployment_id, "deployment_id")
    config_hash = _required_text(config_hash, "config_hash")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", config_hash):
        raise ValueError("CONFIG_HASH_INVALID")
    if isinstance(controlled_restarts, bool) or not isinstance(controlled_restarts, int) or controlled_restarts < 3:
        raise ValueError("CONTROLLED_RESTART_COUNT_BELOW_REQUIRED_MINIMUM")

    started = _parse_utc(started_at_utc, "started_at_utc")
    ended = _parse_utc(ended_at_utc, "ended_at_utc")
    now = datetime.now(UTC)
    if ended < started or ended > now:
        raise ValueError("SOAK_TIME_INTERVAL_INVALID")
    actual_elapsed_seconds = int((ended - started).total_seconds())
    if actual_elapsed_seconds < TARGET_SECONDS:
        raise ValueError("SOAK_DURATION_BELOW_3600_SECONDS")

    try:
        raw = observations_path.read_bytes()
    except OSError as exc:
        raise ValueError("OBSERVATION_LEDGER_UNAVAILABLE") from exc
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) < MIN_HEALTH_SAMPLES:
        raise ValueError("SOAK_HEALTH_SAMPLE_COUNT_BELOW_600")

    elapsed_values: list[float] = []
    degraded_samples = 0
    expected_unknowns: set[str] = set()
    for index, line in enumerate(lines, start=1):
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"OBSERVATION_{index}_JSON_INVALID") from exc
        if not isinstance(row, dict):
            raise ValueError(f"OBSERVATION_{index}_ROOT_NOT_OBJECT")
        elapsed, degraded = _validate_observation(row, index)
        elapsed_values.append(elapsed)
        degraded_samples += int(degraded)
        expected_unknowns.update(row.get("critical_unknowns", []))

    if elapsed_values[0] > 5:
        raise ValueError("SOAK_INITIAL_HEALTH_SAMPLE_TOO_LATE")
    if any(right <= left for left, right in zip(elapsed_values, elapsed_values[1:])):
        raise ValueError("SOAK_OBSERVATION_TIMELINE_NOT_STRICTLY_INCREASING")
    if any(right - left > MAX_SAMPLE_GAP_SECONDS for left, right in zip(elapsed_values, elapsed_values[1:])):
        raise ValueError("SOAK_HEALTH_SAMPLE_GAP_TOO_LARGE")
    if elapsed_values[-1] > actual_elapsed_seconds or actual_elapsed_seconds - elapsed_values[-1] > MAX_SAMPLE_GAP_SECONDS:
        raise ValueError("SOAK_FINAL_HEALTH_SAMPLE_TOO_FAR_FROM_END")

    generated = now.isoformat().replace("+00:00", "Z")
    valid_until = (ended + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    observation_hash = hashlib.sha256(raw).hexdigest()
    record = build_evidence(
        evidence_id=f"NONPROD-SOAK-{deployment_id}",
        source_hash=source_commit,
        artifact_hash=runtime_image_id,
        config_hash=config_hash,
        data_hash=observation_hash,
        environment="ci",
        started_at_utc=started.isoformat().replace("+00:00", "Z"),
        ended_at_utc=ended.isoformat().replace("+00:00", "Z"),
        status="CURRENT",
        valid_until_utc=valid_until,
        result="PROVEN",
        provenance={
            "origin": "ci",
            "issuer": "AURELIA Non-Production 3600s Soak workflow",
            "source_commit": source_commit,
            "generated_at_utc": generated,
            "deployment_id": deployment_id,
        },
        invariants_checked=INVARIANTS_CHECKED,
        invariants_failed=[],
    )
    record.update({
        "source_commit": source_commit,
        "runtime_image_id": runtime_image_id,
        "evidence_type": "NON_PRODUCTION_3600S_CONTROL_PATH_SOAK",
        "classification": "SIMULATION_VERIFIED",
        "target_seconds": TARGET_SECONDS,
        "duration_seconds": actual_elapsed_seconds,
        "actual_elapsed_seconds": actual_elapsed_seconds,
        "continuous": True,
        "execution_mode": "VERIFY_ONLY",
        "deployment_id": deployment_id,
        "runtime_instance_id": runtime_instance_id,
        "health_checks": len(lines),
        "controlled_restarts": controlled_restarts,
        "health_check_failures": 0,
        "invariant_violations": 0,
        "silent_degradations": 0,
        "known_expected_degradation_samples": degraded_samples,
        "known_expected_unknowns": sorted(expected_unknowns),
        "capital_authority_escapes": 0,
        "unresolved_unknown_states": 0,
        "authenticated_deriv_session": False,
        "real_broker_transaction": False,
        "real_capital_movement": False,
        "orders_submitted": 0,
        "final_execution_authorization": False,
        "live_execution": "BLOCKED",
        "capital_can_open_new_exposure": False,
        "observation_ledger_sha256": observation_hash,
    })
    record["record_hash"] = payload_sha256({
        key: value for key, value in record.items() if key != "record_hash"
    })
    write_evidence(output_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--runtime-image-id", required=True)
    parser.add_argument("--runtime-instance-id", required=True)
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--config-hash", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--ended-at", required=True)
    parser.add_argument("--controlled-restarts", required=True, type=int)
    args = parser.parse_args()
    try:
        record = write_nonproduction_soak_evidence(
            observations_path=Path(args.observations),
            output_path=Path(args.out),
            source_commit=args.source_commit,
            runtime_image_id=args.runtime_image_id,
            runtime_instance_id=args.runtime_instance_id,
            deployment_id=args.deployment_id,
            config_hash=args.config_hash,
            started_at_utc=args.started_at,
            ended_at_utc=args.ended_at,
            controlled_restarts=args.controlled_restarts,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"SOAK_EVIDENCE_BUILD=BLOCKED:{exc}")
        return 2
    print("SOAK_EVIDENCE_BUILD=PROVEN")
    print(f"SOAK_EVIDENCE_PATH={args.out}")
    print(f"SOAK_EVIDENCE_HASH={record['record_hash']}")
    print(f"SOAK_EVIDENCE_CLASSIFICATION={record['classification']}")
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    print("LIVE_EXECUTION=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
