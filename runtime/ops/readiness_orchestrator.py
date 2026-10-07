from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.core.release_gate import LiveReleaseState, read_live_release
from assurance.certification_evidence import validate_evidence_file
from runtime.ops.readiness_attestation import REQUIRED_CAPABILITIES, verify_readiness_attestations

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Gate:
    name: str
    status: str
    reason: str

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {
        "1", "true", "yes", "pass", "verified", "healthy", "ready"
    }


def _float_env(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def _evidence_payload_hash(record: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in record.items() if key != "record_hash"}
    canonical = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _current_evidence(path: Path) -> dict[str, Any] | None:
    """Load and cryptographically validate broker evidence before readiness can use it."""
    required = (
        "evidence_id",
        "source_hash",
        "artifact_hash",
        "config_hash",
        "data_hash",
        "environment",
        "started_at_utc",
        "ended_at_utc",
        "status",
        "result",
        "record_hash",
    )
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            return None
        if any(not isinstance(record.get(key), str) or not record[key].strip() for key in required):
            return None
        if str(record["status"]).upper() not in {"CURRENT", "EXPIRING"}:
            return None
        if str(record["result"]).upper() not in {"PASS", "PROVEN", "VALIDATED"}:
            return None

        started = datetime.fromisoformat(str(record["started_at_utc"]).replace("Z", "+00:00"))
        ended = datetime.fromisoformat(str(record["ended_at_utc"]).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if started.tzinfo is None or ended.tzinfo is None or ended < started or ended > now:
            return None

        valid_until = record.get("valid_until_utc")
        if valid_until:
            expires = datetime.fromisoformat(str(valid_until).replace("Z", "+00:00"))
            if expires.tzinfo is None or expires <= now:
                return None

        if record.get("invariants_failed"):
            return None

        provenance = record.get("provenance")
        if not isinstance(provenance, dict):
            return None
        for key in ("origin", "issuer", "source_commit", "generated_at_utc"):
            value = provenance.get(key)
            if not isinstance(value, str) or not value.strip():
                return None
        if str(provenance.get("origin")).lower() not in {"ci", "research", "runtime"}:
            return None
        provenance_generated = datetime.fromisoformat(
            str(provenance["generated_at_utc"]).replace("Z", "+00:00")
        )
        if provenance_generated.tzinfo is None or provenance_generated > now:
            return None

        if record["record_hash"] != _evidence_payload_hash(record):
            return None

        observed = record.get("observed")
        if not isinstance(observed, dict):
            return None
        if str(observed.get("account_loginid", "")).strip() == "":
            return None
        if str(observed.get("environment", "")).lower() != "real":
            return None
        if str(observed.get("currency", "")).strip() == "":
            return None
        available_balance = observed.get("available_balance")
        if (
            isinstance(available_balance, bool)
            or not isinstance(available_balance, (int, float))
            or available_balance < 0
            or not __import__("math").isfinite(float(available_balance))
        ):
            return None
        if record.get("capital_authority_granted") is True:
            return None
        if int(record.get("orders_submitted", 0)) != 0:
            return None
        return record
    except (OSError, ValueError, TypeError, json.JSONDecodeError, OverflowError):
        return None


def evaluate(root: Path = ROOT) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    release: LiveReleaseState = read_live_release(root / "config" / "LIVE_LOCK.yaml")

    token_present = bool(os.getenv("DERIV_AUTH_TOKEN") or os.getenv("DERIV_PAT"))
    login_present = bool(
        os.getenv("DERIV_EXPECTED_LOGINID")
        or os.getenv("DERIV_AUTHORIZED_ACCOUNT_ID")
    )
    auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower()
    app_present = bool(os.getenv("DERIV_APP_ID"))
    credentials = token_present and login_present and (
        auth_mode != "pat" or app_present
    )

    deriv_evidence_path = Path(
        os.getenv(
            "AURELIA_DERIV_EVIDENCE_PATH",
            str(root / "artifacts" / "deriv_authenticated_session.json"),
        )
    )
    deriv_evidence = _current_evidence(deriv_evidence_path)
    # The broker verifier writes a current PROVEN evidence envelope. Readiness
    # must consume that evidence directly; ambient environment flags are not
    # themselves evidence and therefore cannot upgrade session/balance state.
    session = bool(deriv_evidence)
    balance = bool(deriv_evidence)
    runtime_id = os.getenv("AURELIA_RUNTIME_ID", "").strip()
    attestations = verify_readiness_attestations(root, runtime_id=runtime_id)
    attestation_status = {capability: capability in attestations["verified"] for capability in REQUIRED_CAPABILITIES}
    persistent_worker = attestation_status["PERSISTENT_WORKER"]

    evidence_specs = {
        "STRATEGY_LIVE_ELIGIBLE": "evidence/strategy_eligibility.json",
        "PROSPECTIVE_OOS": "evidence/prospective_oos.json",
        "CALIBRATION": "evidence/calibration.json",
        "ECONOMICS": "evidence/execution_economics.json",
        "SOAK_3600S": "evidence/soak_3600s.json",
    }
    evidence_gates: dict[str, Gate] = {}
    for name, relative in evidence_specs.items():
        status, detail = validate_evidence_file(root, relative)
        evidence_gates[name] = Gate(name, status, detail)

    gates = [
        Gate("DERIV_CREDENTIALS", "PASS" if credentials else "FAIL", "presence only; secret values are never emitted"),
        Gate("DERIV_SESSION", "PASS" if session else "UNKNOWN", "requires current PROVEN authenticated modern Options WS evidence"),
        Gate("BALANCE_FRESH", "PASS" if balance else "UNKNOWN", "requires current PROVEN broker balance evidence"),
        Gate("PERSISTENT_WORKER", "PASS" if persistent_worker else "FAIL", "requires an actual healthy persistent execution worker"),
        evidence_gates["STRATEGY_LIVE_ELIGIBLE"],
        evidence_gates["PROSPECTIVE_OOS"],
        evidence_gates["CALIBRATION"],
        evidence_gates["ECONOMICS"],
        evidence_gates["SOAK_3600S"],
        Gate("MARKET_DATA", "PASS" if attestation_status["MARKET_DATA"] else "FAIL", "requires a current provenance-bound market-data attestation"),
        Gate("PROBABILITY", "PASS" if attestation_status["PROBABILITY"] else "FAIL", "requires a current provenance-bound probability attestation"),
        Gate("RISK_WARDEN", "PASS" if attestation_status["RISK_WARDEN"] else "FAIL", "requires a current provenance-bound risk attestation"),
        Gate("EXECUTION_FIREWALL", "PASS" if attestation_status["EXECUTION_FIREWALL"] else "FAIL", "requires a current provenance-bound execution-firewall attestation"),
        Gate("EXPOSURE", "PASS" if attestation_status["EXPOSURE"] else "FAIL", "requires a current provenance-bound exposure attestation"),
        Gate("RECONCILIATION", "PASS" if attestation_status["RECONCILIATION"] else "FAIL", "requires a current provenance-bound reconciliation attestation"),
        Gate("WATCHDOG", "PASS" if attestation_status["WATCHDOG"] else "FAIL", "requires a current provenance-bound watchdog attestation"),
        Gate("IDEMPOTENCY", "PASS" if attestation_status["IDEMPOTENCY"] else "FAIL", "requires a current provenance-bound idempotency attestation"),
    ]

    observed = deriv_evidence.get("observed", {}) if isinstance(deriv_evidence, dict) else {}
    observed_balance = observed.get("available_balance") if isinstance(observed, dict) else None
    verified_balance = (
        float(observed_balance)
        if balance and isinstance(observed_balance, (int, float)) and observed_balance >= 0
        else None
    )
    blockers = [
        {"gate": g.name, "status": g.status, "reason": g.reason}
        for g in gates if not g.passed
    ]

    release_pass = release.may_move_capital
    if not release_pass:
        blockers.insert(0, {
            "gate": "LIVE_RELEASE",
            "status": "FAIL",
            "reason": "LIVE_LOCK does not permit capital movement",
        })

    final_auth = release_pass and all(g.passed for g in gates)

    return {
        "schema": "aurelia.readiness.v1",
        "generated_at_utc": now.isoformat(),
        "mode": "AUTONOMOUS_EXECUTION_MODE" if final_auth else "AUTONOMOUS_EXECUTION_PREPARATION",
        "final_execution_authorization": final_auth,
        "live_execution": "ENABLED" if final_auth else "BLOCKED",
        "live_orders": 0,
        "deriv": {
            "credentials_present": credentials,
            "rest": "PASS" if deriv_evidence else "UNKNOWN",
            "session": "VERIFIED" if session else "UNKNOWN",
            "endpoint": "api.derivws.com",
            "balance": verified_balance,
            "balance_fresh": balance,
            "balance_source": "DERIV_MODERN_OPTIONS_API" if balance else "UNKNOWN",
            "evidence_path": str(deriv_evidence_path),
            "evidence_record_hash": (
                str(deriv_evidence.get("record_hash"))
                if deriv_evidence
                else None
            ),
            "evidence_valid_until_utc": (
                deriv_evidence.get("valid_until_utc")
                if deriv_evidence
                else None
            ),
        },
        "worker": {
            "persistent": "HEALTHY" if persistent_worker else "NOT_DEPLOYED",
            "legacy_railway": "HEALTHY" if attestation_status["PERSISTENT_WORKER"] else "NOT_CONFIGURED",
            "deriv_connectivity": "PASS" if attestation_status["PERSISTENT_WORKER"] else "UNKNOWN",
        },
        "strategy_live_eligible": evidence_gates["STRATEGY_LIVE_ELIGIBLE"].passed,
        "evidence": {
            "market_data": attestation_status["MARKET_DATA"],
            "prospective_oos": evidence_gates["PROSPECTIVE_OOS"].passed,
            "calibration": evidence_gates["CALIBRATION"].passed,
            "economics": evidence_gates["ECONOMICS"].passed,
            "soak_3600s": evidence_gates["SOAK_3600S"].passed,
        },
        "capital": {
            "starting_stake": 1.0,
            "execution_minimum_stake": 1.0,
            "verified_balance": verified_balance,
            "stake_ceiling": verified_balance,
        },
        "controls": {
            "risk_warden": attestation_status["RISK_WARDEN"],
            "execution_firewall": attestation_status["EXECUTION_FIREWALL"],
            "exposure": attestation_status["EXPOSURE"],
            "reconciliation": attestation_status["RECONCILIATION"],
            "watchdog": attestation_status["WATCHDOG"],
            "idempotency": attestation_status["IDEMPOTENCY"],
        },
        "live_lock": {
            "live_trading_enabled": release.live_trading_enabled,
            "final_execution_authorization": release.final_execution_authorization,
            "capital_plane_mode": release.capital_plane_mode,
        },
        "attestations": attestations,
        "blockers": blockers,
        "next_action": blockers[0] if blockers else None,
        "continue_hunting": True,
    }


def main() -> int:
    report = evaluate()
    output = Path(
        os.getenv(
            "AURELIA_READINESS_OUT",
            str(ROOT / "data" / "runtime" / "AURELIA_READINESS.json"),
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    print(f"READINESS_ARTIFACT={output}")
    return 0 if report["final_execution_authorization"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
