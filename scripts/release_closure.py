#!/usr/bin/env python3
"""Produce a current, non-authoritative release-closure report.

This command never enables live execution. It recomputes readiness from the
current source tree, environment, broker evidence, attestations, and evidence
bundle, then classifies remaining blockers by whether code can fix them.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assurance.certification_evidence import validate_evidence_bundle
from runtime.ops.readiness_orchestrator import evaluate

CODE_FIXABLE = {
    "STATIC_RELEASE_GATE",
    "STALE_READINESS_SNAPSHOT",
    "LEGACY_DEPLOYMENT_REFERENCE",
}
EXTERNAL = {
    "DERIV_CREDENTIALS",
    "DERIV_SESSION",
    "BALANCE_FRESH",
    "PERSISTENT_WORKER",
    "PROSPECTIVE_OOS",
    "CALIBRATION",
    "ECONOMICS",
    "SOAK_3600S",
}
CONTROL = {
    "MARKET_DATA",
    "PROBABILITY",
    "RISK_WARDEN",
    "EXECUTION_FIREWALL",
    "EXPOSURE",
    "RECONCILIATION",
    "WATCHDOG",
    "IDEMPOTENCY",
}

def classify(gate: str) -> str:
    if gate in CODE_FIXABLE:
        return "CODE"
    if gate in EXTERNAL:
        return "EXTERNAL_EVIDENCE"
    if gate in CONTROL:
        return "CONTROL_ATTESTATION"
    return "REVIEW"

def main() -> int:
    report = evaluate(ROOT)
    cert_status, cert_detail = validate_evidence_bundle(ROOT)
    blockers = []
    for item in report.get("blockers", []):
        gate = str(item.get("gate", "UNKNOWN"))
        category = "FINAL_AUTHORIZATION" if gate == "LIVE_RELEASE" else classify(gate)
        blockers.append({
            "gate": gate,
            "status": item.get("status"),
            "category": category,
            "reason": item.get("reason"),
        })
    payload = {
        "schema": "aurelia.release_closure.v1",
        "authoritative": False,
        "final_execution_authorization": bool(report.get("final_execution_authorization")),
        "live_execution": report.get("live_execution"),
        "source_sha": report.get("attestations", {}).get("source_sha"),
        "certification": {"status": cert_status, "detail": cert_detail},
        "blockers": blockers,
        "code_fixable_blockers": [x for x in blockers if x["category"] == "CODE"],
        "external_evidence_blockers": [x for x in blockers if x["category"] == "EXTERNAL_EVIDENCE"],
        "control_attestation_blockers": [x for x in blockers if x["category"] == "CONTROL_ATTESTATION"],
        "final_authorization_blockers": [x for x in blockers if x["category"] == "FINAL_AUTHORIZATION"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not blockers and cert_status == "PASS" else 2

if __name__ == "__main__":
    raise SystemExit(main())
