#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.core.secrets import get_optional_secret
from runtime.core.events import sha256
from assurance.certification_evidence import validate_evidence_bundle
from runtime.ops.readiness_attestation import config_hash as readiness_config_hash
from runtime.ops.readiness_orchestrator import _current_evidence, evaluate as evaluate_readiness

LIVE_LOCK_PATH = ROOT / "config" / "LIVE_LOCK.yaml"
SESSION_EVIDENCE_PATH = Path(
    os.getenv("AURELIA_DERIV_EVIDENCE_PATH", "").strip()
    or os.getenv("DERIV_EVIDENCE_OUT", "").strip()
    or str(ROOT / "artifacts" / "deriv_authenticated_session.json")
)
LIFECYCLE_VERIFY_EVIDENCE_PATH = Path(
    os.getenv("AURELIA_DERIV_LIFECYCLE_EVIDENCE_PATH", "").strip()
    or os.getenv("DERIV_LIFECYCLE_EVIDENCE_OUT", "").strip()
    or str(ROOT / "artifacts" / "deriv_transaction_lifecycle.json")
)
BROKER_EVIDENCE_PATH = Path(
    os.getenv("AURELIA_DERIV_BROKER_EVIDENCE_PATH", "").strip()
    or os.getenv("DERIV_BROKER_EVIDENCE_OUT", "").strip()
    or str(ROOT / "artifacts" / "deriv_broker_account_evidence.json")
)
PUBLIC_TRANSPORT_EVIDENCE_PATH = Path(
    os.getenv("DERIV_PUBLIC_TRANSPORT_EVIDENCE_PATH", "").strip()
    or os.getenv("DERIV_PUBLIC_TRANSPORT_EVIDENCE_OUT", "").strip()
    or str(ROOT / "artifacts" / "deriv_public_transport.json")
)


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
        key = key.strip()
        if not key or key in values:
            raise RuntimeError("config/LIVE_LOCK.yaml contains an invalid or duplicate key")
        values[key] = value.strip()
    return values




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
    if not (get_optional_secret("DERIV_AUTH_TOKEN") or get_optional_secret("DERIV_PAT")):
        raise RuntimeError("missing required env var: DERIV_AUTH_TOKEN (or DERIV_PAT)")
    if not (os.getenv("DERIV_EXPECTED_LOGINID", "").strip() or os.getenv("DERIV_AUTHORIZED_ACCOUNT_ID", "").strip()):
        raise RuntimeError("missing required env var: DERIV_EXPECTED_LOGINID (or DERIV_AUTHORIZED_ACCOUNT_ID)")
    currency = _assert_env("DERIV_EXPECTED_CURRENCY").upper()
    if currency != "USD":
        raise RuntimeError("DERIV_EXPECTED_CURRENCY must be USD for the current AURELIA configuration")
    _assert_env("DERIV_ENVIRONMENT")
    auth_mode = _assert_env("DERIV_AUTH_MODE").lower()

    if auth_mode not in {"pat", "oauth"}:
        raise RuntimeError("DERIV_AUTH_MODE must be pat or oauth")
    if os.getenv("DERIV_ENVIRONMENT", "").strip().lower() != "real":
        raise RuntimeError("DERIV_ENVIRONMENT must be real for live trading")

    if auth_mode == "pat" and not get_optional_secret("DERIV_APP_ID"):
        raise RuntimeError("DERIV_APP_ID required when DERIV_AUTH_MODE=pat")


def check_live_lock() -> None:
    cfg = _read_live_lock(LIVE_LOCK_PATH)
    if not cfg:
        raise RuntimeError("missing config/LIVE_LOCK.yaml")
    if cfg.get("schema", "").strip() != "aurelia.live_lock.v1":
        raise RuntimeError("config/LIVE_LOCK.yaml schema is invalid")
    if cfg.get("live_trading_enabled", "").strip().lower() != "true":
        raise RuntimeError("config/LIVE_LOCK.yaml disables live trading")
    if cfg.get("FINAL_EXECUTION_AUTHORIZATION", "").strip().lower() != "true":
        raise RuntimeError("config/LIVE_LOCK.yaml does not authorize final execution")
    if cfg.get("LIVE_EXECUTION", "").strip().upper() != "ENABLED":
        raise RuntimeError("config/LIVE_LOCK.yaml does not enable live execution")
    if cfg.get("capital_plane_mode", "").strip().upper() != "LIVE":
        raise RuntimeError("config/LIVE_LOCK.yaml capital_plane_mode is not LIVE")
    if cfg.get("research_capital_authority", "").strip().lower() != "false":
        raise RuntimeError("config/LIVE_LOCK.yaml permits research capital authority")
    if cfg.get("external_repositories_capital_forbidden", "").strip().lower() != "true":
        raise RuntimeError("config/LIVE_LOCK.yaml does not forbid external-repository capital authority")
    if cfg.get("blind_resubmission", "").strip().lower() != "false":
        raise RuntimeError("config/LIVE_LOCK.yaml permits blind resubmission")
    if cfg.get("kill_switch_independent", "").strip().lower() != "true":
        raise RuntimeError("config/LIVE_LOCK.yaml does not require an independent kill switch")


def check_readiness() -> None:
    # Never trust a persisted readiness snapshot for release authorization.
    # Recompute from live inputs, then validate source/config identity and every
    # literal control/qualification field.
    report = evaluate_readiness(ROOT)
    if not isinstance(report, dict):
        raise RuntimeError("dynamic readiness evaluation returned an invalid payload")
    if report.get("final_execution_authorization") is not True:
        raise RuntimeError("dynamic readiness final_execution_authorization is false or not literal true")
    if not isinstance(report.get("live_execution"), str) or report["live_execution"].strip().upper() != "ENABLED":
        raise RuntimeError("dynamic readiness live_execution is not ENABLED")
    blockers = report.get("blockers")
    if not isinstance(blockers, list) or blockers:
        raise RuntimeError(f"dynamic readiness blockers present or malformed: {blockers}")

    try:
        max_age = float(os.getenv("AURELIA_READINESS_MAX_AGE_SECONDS", "30"))
        generated = datetime.fromisoformat(str(report["generated_at_utc"]).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - generated).total_seconds()
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("dynamic readiness timestamp is invalid") from exc
    if not math.isfinite(max_age) or max_age <= 0 or generated.tzinfo is None or age < 0 or age > max_age:
        raise RuntimeError("dynamic readiness is stale or from the future")

    expected_source = os.getenv("GITHUB_SHA", "").strip() or os.getenv("AURELIA_SOURCE_SHA", "").strip()
    expected_loginid = os.getenv("DERIV_EXPECTED_LOGINID", "").strip() or os.getenv("DERIV_AUTHORIZED_ACCOUNT_ID", "").strip()
    expected_currency = os.getenv("DERIV_EXPECTED_CURRENCY", "").strip().upper()
    attestations = report.get("attestations")
    if not isinstance(attestations, dict):
        raise RuntimeError("dynamic readiness attestations are missing")
    if not expected_source or attestations.get("source_sha") != expected_source:
        raise RuntimeError("dynamic readiness source revision mismatch")
    if not attestations.get("config_hash") or attestations.get("config_hash") != readiness_config_hash(ROOT):
        raise RuntimeError("dynamic readiness configuration hash mismatch")
    if not isinstance(attestations.get("runtime_id"), str) or not attestations["runtime_id"].strip():
        raise RuntimeError("dynamic readiness runtime identity is missing")
    if attestations.get("all_passed") is not True or attestations.get("failures") != {}:
        raise RuntimeError("dynamic readiness attestation verification is incomplete")

    required = {
        "MARKET_DATA", "PROBABILITY", "RISK_WARDEN", "EXECUTION_FIREWALL",
        "EXPOSURE", "RECONCILIATION", "WATCHDOG", "IDEMPOTENCY", "PERSISTENT_WORKER",
    }
    verified = attestations.get("verified")
    if not isinstance(verified, dict) or set(verified) != required:
        raise RuntimeError("dynamic readiness attestation capability set is incomplete")
    for capability, item in verified.items():
        if not isinstance(item, dict) or item.get("status") != "PASS" or not all(
            isinstance(item.get(k), str) and item[k].strip()
            for k in ("issuer", "subject", "evidence_hash", "provenance", "expires_at_utc")
        ):
            raise RuntimeError(f"dynamic readiness attestation invalid: {capability}")
        try:
            expiry = datetime.fromisoformat(item["expires_at_utc"].replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"dynamic readiness attestation expiry invalid: {capability}") from exc
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise RuntimeError(f"dynamic readiness attestation expired: {capability}")

    controls = report.get("controls")
    if not isinstance(controls, dict) or any(
        controls.get(k) is not True
        for k in ("risk_warden", "execution_firewall", "exposure", "reconciliation", "watchdog", "idempotency")
    ):
        raise RuntimeError("dynamic readiness controls are incomplete or not literal true")
    evidence = report.get("evidence")
    if not isinstance(evidence, dict) or any(
        evidence.get(k) is not True
        for k in ("market_data", "prospective_oos", "calibration", "economics", "soak_3600s")
    ):
        raise RuntimeError("dynamic readiness qualification evidence is incomplete")
    if report.get("strategy_live_eligible") is not True or report.get("live_orders") != 0:
        raise RuntimeError("dynamic readiness strategy eligibility/zero-order invariant is invalid")

    lock = report.get("live_lock")
    if not isinstance(lock, dict) or not (
        lock.get("live_trading_enabled") is True
        and lock.get("final_execution_authorization") is True
        and str(lock.get("capital_plane_mode", "")).upper() == "LIVE"
    ):
        raise RuntimeError("dynamic readiness does not match canonical LIVE lock")
    deriv = report.get("deriv")
    if not isinstance(deriv, dict) or not expected_loginid or deriv.get("account_loginid") != expected_loginid:
        raise RuntimeError("dynamic readiness Deriv account identity mismatch")
    if (
        not expected_currency
        or str(deriv.get("currency", "")).strip().upper() != expected_currency
        or str(deriv.get("account_type", "")).strip().lower() != "real"
        or str(deriv.get("environment", "")).strip().lower() != "real"
        or deriv.get("balance_fresh") is not True
    ):
        raise RuntimeError("dynamic readiness Deriv account/currency/environment/balance is not verified")
    balance = deriv.get("balance")
    if isinstance(balance, bool) or not isinstance(balance, (int, float)) or not math.isfinite(float(balance)) or balance <= 0:
        raise RuntimeError("dynamic readiness verified available balance is invalid")


def check_certification_evidence() -> None:
    status, detail = validate_evidence_bundle(ROOT)
    if status != "PASS":
        raise RuntimeError(f"strict certification evidence block: {detail}")


def _expected_deriv_evidence_binding() -> dict[str, str]:
    return {
        "expected_loginid": (
            os.getenv("DERIV_EXPECTED_LOGINID", "").strip()
            or os.getenv("DERIV_AUTHORIZED_ACCOUNT_ID", "").strip()
        ),
        "expected_currency": os.getenv("DERIV_EXPECTED_CURRENCY", "").strip().upper(),
        "expected_source_sha": (
            os.getenv("GITHUB_SHA", "").strip()
            or os.getenv("AURELIA_SOURCE_SHA", "").strip()
        ),
    }


def check_session_evidence() -> None:
    evidence = _current_evidence(
        SESSION_EVIDENCE_PATH,
        **_expected_deriv_evidence_binding(),
    )
    if evidence is None:
        raise RuntimeError(
            "session evidence is missing, expired, tampered, non-real, or otherwise invalid"
        )
    if evidence.get("capital_authority_granted") is True:
        raise RuntimeError("live gate cannot approve capital authority during verification")
    if int(evidence.get("orders_submitted", 0)) != 0:
        raise RuntimeError("verification evidence cannot show submitted orders")


def check_verify_only_lifecycle_evidence() -> None:
    evidence = _current_evidence(
        LIFECYCLE_VERIFY_EVIDENCE_PATH,
        **_expected_deriv_evidence_binding(),
    )
    if evidence is None:
        raise RuntimeError(
            "verify-only Deriv transaction lifecycle evidence is missing, expired, tampered, non-real, or otherwise invalid"
        )
    if evidence.get("verification_scope") != "REAL_DERIV_LIFECYCLE_VERIFY_ONLY":
        raise RuntimeError("invalid Deriv verify-only lifecycle evidence scope")
    if evidence.get("capital_authority_granted") is True:
        raise RuntimeError("verify-only lifecycle evidence cannot grant capital authority")
    if int(evidence.get("orders_submitted", 0)) != 0:
        raise RuntimeError("verify-only lifecycle evidence cannot contain submitted orders")


def check_broker_account_evidence() -> None:
    evidence = _current_evidence(
        BROKER_EVIDENCE_PATH,
        **_expected_deriv_evidence_binding(),
    )
    if evidence is None:
        raise RuntimeError(
            "read-only Deriv broker account evidence is missing, expired, tampered, non-real, or otherwise invalid"
        )
    if evidence.get("verification_scope") != "REAL_DERIV_BROKER_ACCOUNT_READ_ONLY":
        raise RuntimeError("invalid Deriv broker evidence scope")
    if evidence.get("capital_authority_granted") is True:
        raise RuntimeError("broker evidence verifier cannot grant capital authority")
    if int(evidence.get("orders_submitted", 0)) != 0:
        raise RuntimeError("broker evidence verifier cannot submit orders")


def check_runtime_verification_flags() -> None:
    """Check current, source-bound read-only transport evidence instead of booleans."""
    if not PUBLIC_TRANSPORT_EVIDENCE_PATH.exists():
        raise RuntimeError("public Deriv transport evidence is missing")
    try:
        evidence = json.loads(PUBLIC_TRANSPORT_EVIDENCE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("public Deriv transport evidence is invalid JSON") from exc
    if not isinstance(evidence, dict):
        raise RuntimeError("public Deriv transport evidence must be a JSON object")
    if evidence.get("schema") != "aurelia.deriv_public_transport.v1":
        raise RuntimeError("public Deriv transport evidence schema is invalid")
    expected_source = (
        os.getenv("GITHUB_SHA", "").strip()
        or os.getenv("AURELIA_SOURCE_SHA", "").strip()
    )
    if not expected_source or evidence.get("source_sha") != expected_source:
        raise RuntimeError("public Deriv transport source revision mismatch")
    unsigned = {key: value for key, value in evidence.items() if key != "record_hash"}
    if not isinstance(evidence.get("record_hash"), str) or sha256(unsigned) != evidence["record_hash"]:
        raise RuntimeError("public Deriv transport evidence hash mismatch")
    try:
        generated = datetime.fromisoformat(
            str(evidence["generated_at_utc"]).replace("Z", "+00:00")
        )
        max_age = float(os.getenv("AURELIA_PUBLIC_TRANSPORT_MAX_AGE_SECONDS", "900"))
        age = (datetime.now(timezone.utc) - generated).total_seconds()
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("public Deriv transport evidence timestamp is invalid") from exc
    if (
        generated.tzinfo is None or not math.isfinite(max_age) or max_age <= 0
        or age < 0 or age > max_age
    ):
        raise RuntimeError("public Deriv transport evidence is stale or from the future")
    count = evidence.get("active_symbol_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise RuntimeError("public Deriv transport reports no active symbols")
    if (
        evidence.get("capital_authority_granted") is not False
        or evidence.get("order_submission_permitted") is not False
    ):
        raise RuntimeError("public Deriv transport probe is not read-only")


def main() -> int:
    try:
        check_live_lock()
        check_environment()
        check_readiness()
        check_certification_evidence()
        check_session_evidence()
        check_verify_only_lifecycle_evidence()
        check_broker_account_evidence()
        check_runtime_verification_flags()
    except Exception as exc:
        return fail(str(exc))

    print("LIVE_RELEASE_GATE=ALLOW")
    print("STATUS=READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
