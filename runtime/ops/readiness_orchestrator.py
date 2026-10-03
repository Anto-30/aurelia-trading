from __future__ import annotations

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

    session = _flag("AURELIA_DERIV_SESSION_VERIFIED")
    balance = _flag("AURELIA_BALANCE_VERIFIED")
    railway = _flag("AURELIA_RAILWAY_WORKER_HEALTHY")

    gates = [
        Gate("DERIV_CREDENTIALS", "PASS" if credentials else "FAIL", "presence only; secret values are never emitted"),
        Gate("DERIV_SESSION", "PASS" if session else "UNKNOWN", "requires fresh authenticated modern Options WS evidence"),
        Gate("BALANCE_FRESH", "PASS" if balance else "UNKNOWN", "requires fresh broker balance evidence"),
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

    verified_balance = _float_env("AURELIA_VERIFIED_AVAILABLE_BALANCE") if balance else None
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
            "rest": "PASS" if _flag("AURELIA_DERIV_REST_VERIFIED") else "UNKNOWN",
            "session": "VERIFIED" if session else "UNKNOWN",
            "endpoint": "api.derivws.com",
            "balance": verified_balance,
            "balance_fresh": balance,
            "balance_source": "DERIV_MODERN_OPTIONS_API" if balance else "UNKNOWN",
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
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["final_execution_authorization"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
