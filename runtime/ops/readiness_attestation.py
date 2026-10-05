from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from runtime.ops.attestations import AttestationError, verify_attestation

REQUIRED_CAPABILITIES = (
    "MARKET_DATA",
    "PROBABILITY",
    "RISK_WARDEN",
    "EXECUTION_FIREWALL",
    "EXPOSURE",
    "RECONCILIATION",
    "WATCHDOG",
    "IDEMPOTENCY",
    "PERSISTENT_WORKER",
)


class ReadinessAttestationError(ValueError):
    pass


def current_source_sha(root: Path) -> str:
    for name in ("GITHUB_SHA", "AURELIA_SOURCE_SHA"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def config_hash(root: Path) -> str:
    paths = (
        root / "config" / "LIVE_LOCK.yaml",
        root / "config" / "agent_capability_boundary.json",
    )
    digest = hashlib.sha256()
    for path in paths:
        if not path.exists():
            return ""
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\\0")
        digest.update(path.read_bytes())
        digest.update(b"\\0")
    return digest.hexdigest()


def verify_readiness_attestations(
    root: Path,
    *,
    runtime_id: str,
    expected_source_sha: str | None = None,
    expected_config_hash: str | None = None,
    signing_key: str | None = None,
    attestation_dir: Path | None = None,
) -> dict[str, Any]:
    runtime_id = runtime_id.strip()
    signing_key = (signing_key if signing_key is not None else os.getenv("AURELIA_ATTESTATION_SIGNING_KEY", "")).strip()
    source_sha = (expected_source_sha or current_source_sha(root)).strip()
    cfg_hash = (expected_config_hash or config_hash(root)).strip()
    directory = attestation_dir or Path(
        os.getenv(
            "AURELIA_ATTESTATION_DIR",
            str(root / "artifacts" / "attestations"),
        )
    )

    if not runtime_id or not source_sha or not signing_key:
        missing = {}
        if not runtime_id:
            missing["runtime_id"] = "RUNTIME_ID_UNAVAILABLE"
        if not source_sha:
            missing["source_sha"] = "SOURCE_SHA_UNAVAILABLE"
        if not signing_key:
            missing["signing_key"] = "SIGNING_KEY_UNAVAILABLE"
        return {
            "all_passed": False,
            "source_sha": source_sha,
            "config_hash": cfg_hash,
            "runtime_id": runtime_id,
            "verified": {},
            "failures": missing,
        }

    verified: dict[str, Any] = {}
    failures: dict[str, str] = {}
    for capability in REQUIRED_CAPABILITIES:
        path = directory / f"{capability.lower()}.json"
        if not path.exists():
            failures[capability] = "MISSING_ATTESTATION"
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            attestation = verify_attestation(
                record,
                signing_key=signing_key,
                expected_source_sha=source_sha,
                expected_runtime_id=runtime_id,
                expected_config_hash=cfg_hash,
            )
            if attestation.capability != capability:
                raise AttestationError("capability mismatch")
            verified[capability] = {
                "status": attestation.status,
                "issuer": attestation.issuer,
                "subject": attestation.subject,
                "expires_at_utc": attestation.expires_at_utc,
                "evidence_hash": attestation.evidence_hash,
                "provenance": attestation.provenance,
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError, AttestationError) as exc:
            failures[capability] = str(exc)

    if failures:
        return {
            "all_passed": False,
            "source_sha": source_sha,
            "config_hash": cfg_hash,
            "runtime_id": runtime_id,
            "verified": verified,
            "failures": failures,
        }

    return {
        "all_passed": True,
        "source_sha": source_sha,
        "config_hash": cfg_hash,
        "runtime_id": runtime_id,
        "verified": verified,
        "failures": {},
    }
