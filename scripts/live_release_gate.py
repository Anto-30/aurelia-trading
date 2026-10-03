#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from assurance.certification_evidence import validate_evidence_bundle
from runtime.ops.readiness_orchestrator import _current_evidence

ROOT = Path(__file__).resolve().parents[1]
LIVE_LOCK_PATH = ROOT / "config" / "LIVE_LOCK.yaml"
READINESS_PATH = ROOT / "data" / "runtime" / "AURELIA_READINESS.json"
SESSION_EVIDENCE_PATH = ROOT / "artifacts" / "deriv_authenticated_session.json"


def _as_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "enabled",
        "verified",
        "pass",
    }


def _read_live_lock(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"missing required artifact: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON in {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"artifact {path} must be a JSON object")
    return data


def fail(reason: str) -> int:
    print("LIVE_RELEASE_GATE=BLOCKED")
    print(f"REASON={reason}")
    return 2


def _assert_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required env var: {name}")
    return value


def check_environment() -> None:
    _assert_env("DERIV_AUTH_TOKEN")
    _assert_env("DERIV_EXPECTED_LOGINID")
    _assert_env("DERIV_EXPECTED_CURRENCY")
    _assert_env("DERIV_ENVIRONMENT")
    _assert_env("DERIV_AUTH_MODE")

    if os.getenv("DERIV_ENVIRONMENT", "").strip().lower() != "real":
        raise RuntimeError("DERIV_ENVIRONMENT must be real for live trading")

    if (
        os.getenv("DERIV_AUTH_MODE", "pat").strip().lower() == "pat"
        and not os.getenv("DERIV_APP_ID")
    ):
        raise RuntimeError("DERIV_APP_ID required when DERIV_AUTH_MODE=pat")


def check_live_lock() -> None:
    cfg = _read_live_lock(LIVE_LOCK_PATH)
    if not cfg:
        raise RuntimeError("missing config/LIVE_LOCK.yaml")
    if cfg.get("live_trading_enabled", "").strip().lower() != "true":
        raise RuntimeError("config/LIVE_LOCK.yaml disables live trading")
    if cfg.get("FINAL_EXECUTION_AUTHORIZATION", "").strip().lower() != "true":
        raise RuntimeError("config/LIVE_LOCK.yaml does not authorize final execution")
    if cfg.get("LIVE_EXECUTION", "").strip().upper() != "ENABLED":
        raise RuntimeError("config/LIVE_LOCK.yaml does not enable live execution")
    if cfg.get("capital_plane_mode", "").strip().upper() != "LIVE":
        raise RuntimeError("config/LIVE_LOCK.yaml capital_plane_mode is not LIVE")


def check_readiness() -> None:
    report = _read_json(READINESS_PATH)
    if not report.get("final_execution_authorization"):
        raise RuntimeError("readiness report final_execution_authorization is false")
    if str(report.get("live_execution", "")).upper() != "ENABLED":
        raise RuntimeError("readiness report live_execution is not ENABLED")
    blockers = report.get("blockers")
    if blockers:
        raise RuntimeError(f"readiness blockers present: {blockers}")


def check_certification_evidence() -> None:
    status, detail = validate_evidence_bundle(ROOT)
    if status != "PASS":
        raise RuntimeError(f"strict certification evidence block: {detail}")


def check_session_evidence() -> None:
    evidence = _current_evidence(SESSION_EVIDENCE_PATH)
    if evidence is None:
        raise RuntimeError(
            "session evidence is missing, expired, tampered, non-real, or otherwise invalid"
        )
    if evidence.get("capital_authority_granted") is True:
        raise RuntimeError("live gate cannot approve capital authority during verification")
    if int(evidence.get("orders_submitted", 0)) != 0:
        raise RuntimeError("verification evidence cannot show submitted orders")


def check_runtime_verification_flags() -> None:
    if not _as_bool(os.getenv("AURELIA_VERIFY_DERIV_PUBLIC")):
        raise RuntimeError("AURELIA_VERIFY_DERIV_PUBLIC must be true")
    if not _as_bool(os.getenv("AURELIA_VERIFY_DERIV_AUTH")):
        raise RuntimeError("AURELIA_VERIFY_DERIV_AUTH must be true")
    if not _as_bool(os.getenv("AURELIA_RUN_ONCE")):
        raise RuntimeError(
            "AURELIA_RUN_ONCE must be true during live gate verification"
        )


def main() -> int:
    try:
        check_environment()
        check_live_lock()
        check_readiness()
        check_certification_evidence()
        check_session_evidence()
        check_runtime_verification_flags()
    except Exception as exc:
        return fail(str(exc))

    print("LIVE_RELEASE_GATE=ALLOW")
    print("STATUS=READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
