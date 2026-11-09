from __future__ import annotations

"""Deterministic research-evidence completeness gate.

This gate is deliberately incapable of authorizing live execution. It evaluates
research qualification, quoted economics, calibration, a verify-only broker
lifecycle, and a protected deployment. A real-money transaction is NOT a
prerequisite for evidence completeness and must never be required to pass this
gate while LIVE_LOCK is blocked.
"""

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED_R100_STATUS = {"RESEARCH_QUALIFIED"}
REQUIRED_LIFECYCLE_SCOPE = "REAL_DERIV_LIFECYCLE_VERIFY_ONLY"


def sha256_json(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(str(path))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"INVALID_JSON_OBJECT:{path}")
    return value


def gate(r100: dict, lifecycle: dict, deployment: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if r100.get("qualification_status") not in REQUIRED_R100_STATUS:
        reasons.append(f"STRATEGY_NOT_QUALIFIED:{r100.get('qualification_status')}")
    if int(r100.get("oos_observations", 0)) < 100:
        reasons.append("OOS_SAMPLE_LT_100")
    if (r100.get("oos_mean_strategy_return") is None or
            float(r100["oos_mean_strategy_return"]) <= 0):
        reasons.append("OOS_EXPECTANCY_NOT_POSITIVE")

    economics = r100.get("execution_economics", {})
    quoted = economics.get("quoted_contract_economics", {})
    if int(quoted.get("sample_count", 0)) < 100:
        reasons.append("QUOTED_ECONOMICS_SAMPLE_LT_100")
    if quoted.get("mean_net_return_per_stake") is None or float(
        quoted["mean_net_return_per_stake"]
    ) <= 0:
        reasons.append("QUOTED_ECONOMICS_NOT_POSITIVE")
    if r100.get("probability", {}).get("calibration_status") != "VALIDATED_RESEARCH":
        reasons.append("PROBABILITY_CALIBRATION_INCOMPLETE")
    if bool(r100.get("probability", {}).get("drift_detected", True)):
        reasons.append("PROBABILITY_DRIFT_DETECTED")
    if not bool(r100.get("campaign_complete", False)):
        reasons.append("RESEARCH_CAMPAIGN_NOT_COMPLETE")

    # This evidence scope proves authenticated broker controls and
    # reconciliation without submitting an order or moving capital.
    if lifecycle.get("verification_scope") != REQUIRED_LIFECYCLE_SCOPE:
        reasons.append("VERIFY_ONLY_LIFECYCLE_EVIDENCE_MISSING")
    if lifecycle.get("orders_submitted") != 0:
        reasons.append("VERIFY_ONLY_LIFECYCLE_SUBMITTED_ORDERS")
    if lifecycle.get("capital_authority_granted") is not False:
        reasons.append("VERIFY_ONLY_LIFECYCLE_GRANTED_CAPITAL_AUTHORITY")
    observed = lifecycle.get("observed", {})
    if not isinstance(observed, dict) or observed.get("reconciliation_healthy") is not True:
        reasons.append("VERIFY_ONLY_RECONCILIATION_NOT_PROVEN")
    if not isinstance(observed, dict) or observed.get("broker_submission_performed") is not False:
        reasons.append("VERIFY_ONLY_BROKER_SUBMISSION_NOT_EXCLUDED")
    if not isinstance(observed, dict) or observed.get("capital_movement") is not False:
        reasons.append("VERIFY_ONLY_CAPITAL_MOVEMENT_NOT_EXCLUDED")

    if deployment.get("status") != "DEPLOYED_AND_HEALTHCHECKED":
        reasons.append("PROTECTED_DEPLOYMENT_NOT_VERIFIED")
    if deployment.get("capital_protection") is not True:
        reasons.append("DEPLOYMENT_CAPITAL_PROTECTION_NOT_PROVEN")

    return ("EVIDENCE_COMPLETE_VERIFY_ONLY" if not reasons else "NOT_READY"), reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r100", required=True)
    parser.add_argument("--lifecycle", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--out", default="artifacts/release_evidence_gate.json")
    args = parser.parse_args()

    try:
        r100 = load(Path(args.r100))
        lifecycle = load(Path(args.lifecycle))
        deployment = load(Path(args.deployment))
        status, reasons = gate(r100, lifecycle, deployment)
    except Exception as exc:
        status, reasons = "NOT_READY", [f"EVIDENCE_LOAD_ERROR:{type(exc).__name__}"]

    result = {
        "schema": "aurelia.release.evidence.gate.v2",
        "status": status,
        "reasons": reasons,
        "evidence_scope": "RESEARCH_AND_VERIFY_ONLY",
        "final_execution_authorization": False,
        "live_execution": "BLOCKED",
        "orders_submitted": 0,
        "capital_authority_granted": False,
    }
    result["evidence_hash"] = sha256_json(result)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"RELEASE_EVIDENCE_GATE={status}")
    for reason in reasons:
        print(f"BLOCKER={reason}")
    return 0 if status == "EVIDENCE_COMPLETE_VERIFY_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
