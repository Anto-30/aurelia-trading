from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.core.release_gate import LiveReleaseState, read_live_release

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

    token_present = bool(os.getenv("DERIV_AUTH_TOKEN"))
    login_present = bool(os.getenv("DERIV_EXPECTED_LOGINID"))
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
    railway = _flag("AURELIA_RAILWAY_WORKER_HEALTHY")

    gates = [
        Gate("DERIV_CREDENTIALS", "PASS" if credentials else "FAIL", "presence only; secret values are never emitted"),
        Gate("DERIV_SESSION", "PASS" if session else "UNKNOWN", "requires current PROVEN authenticated modern Options WS evidence"),
        Gate("BALANCE_FRESH", "PASS" if balance else "UNKNOWN", "requires current PROVEN broker balance evidence"),
        Gate("RAILWAY_WORKER", "PASS" if railway else "FAIL", "requires an actual healthy Railway worker"),
        Gate("STRATEGY_LIVE_ELIGIBLE", "PASS" if _flag("AURELIA_STRATEGY_LIVE_ELIGIBLE") else "FAIL", "requires current qualification evidence"),
        Gate("PROSPECTIVE_OOS", "PASS" if _flag("AURELIA_PROSPECTIVE_OOS_PASS") else "FAIL", "requires valid prospective OOS evidence"),
        Gate("CALIBRATION", "PASS" if _flag("AURELIA_CALIBRATION_PASS") else "FAIL", "requires calibration and drift evidence"),
        Gate("ECONOMICS", "PASS" if _flag("AURELIA_ECONOMICS_PASS") else "FAIL", "requires net execution economics"),
        Gate("SOAK_3600S", "PASS" if _flag("AURELIA_SOAK_3600S_PASS") else "FAIL", "requires actual 3600-second runtime evidence"),
        Gate("MARKET_DATA", "PASS" if _flag("AURELIA_MARKET_DATA_VALIDATED") else "FAIL", "requires validated decision-time market data"),
        Gate("PROBABILITY", "PASS" if _flag("AURELIA_PROBABILITY_VALID") else "FAIL", "requires valid, calibrated, fresh probability"),
        Gate("RISK_WARDEN", "PASS" if _flag("AURELIA_RISK_WARDEN_PASS") else "FAIL", "requires deterministic risk approval"),
        Gate("EXECUTION_FIREWALL", "PASS" if _flag("AURELIA_EXECUTION_FIREWALL_PASS") else "FAIL", "requires firewall approval"),
        Gate("EXPOSURE", "PASS" if _flag("AURELIA_EXPOSURE_PASS") else "FAIL", "requires exposure approval"),
        Gate("RECONCILIATION", "PASS" if _flag("AURELIA_RECONCILIATION_HEALTHY") else "FAIL", "requires healthy reconciliation"),
        Gate("WATCHDOG", "PASS" if _flag("AURELIA_WATCHDOG_HEALTHY") else "FAIL", "requires healthy watchdog"),
        Gate("IDEMPOTENCY", "PASS" if _flag("AURELIA_IDEMPOTENCY_HEALTHY") else "FAIL", "requires restart-safe exactly-once protection"),
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
        "railway": {
            "worker": "HEALTHY" if railway else "NOT_DEPLOYED",
            "deriv_connectivity": "PASS" if _flag("AURELIA_RAILWAY_DERIV_CONNECTED") else "UNKNOWN",
        },
        "strategy_live_eligible": _flag("AURELIA_STRATEGY_LIVE_ELIGIBLE"),
        "evidence": {
            "prospective_oos": _flag("AURELIA_PROSPECTIVE_OOS_PASS"),
            "calibration": _flag("AURELIA_CALIBRATION_PASS"),
            "economics": _flag("AURELIA_ECONOMICS_PASS"),
            "soak_3600s": _flag("AURELIA_SOAK_3600S_PASS"),
        },
        "capital": {
            "starting_stake": 1.0,
            "execution_minimum_stake": 1.0,
            "verified_balance": verified_balance,
            "stake_ceiling": verified_balance,
        },
        "controls": {
            "risk_warden": _flag("AURELIA_RISK_WARDEN_PASS"),
            "execution_firewall": _flag("AURELIA_EXECUTION_FIREWALL_PASS"),
            "exposure": _flag("AURELIA_EXPOSURE_PASS"),
            "reconciliation": _flag("AURELIA_RECONCILIATION_HEALTHY"),
            "watchdog": _flag("AURELIA_WATCHDOG_HEALTHY"),
            "idempotency": _flag("AURELIA_IDEMPOTENCY_HEALTHY"),
        },
        "live_lock": {
            "live_trading_enabled": release.live_trading_enabled,
            "final_execution_authorization": release.final_execution_authorization,
            "capital_plane_mode": release.capital_plane_mode,
        },
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
