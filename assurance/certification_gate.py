"""Repository-level AURELIA certification gate.

This gate checks repository, control, and evidence readiness only. It never
grants live authority and never contacts a broker.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .certification_evidence import runtime_source_status, validate_evidence_bundle

MANDATORY_DOCUMENTS = (
    "docs/AURELIA_PRODUCTION_STANDARD.yaml",
    "docs/AURELIA_CONSTITUTION.md",
    "docs/AURELIA_TEST_ORACLE_MATRIX.yaml",
    "docs/AURELIA_ASSURANCE_PROGRAM.md",
    "docs/AURELIA_SECURITY_THREAT_MODEL.md",
    "docs/AURELIA_COUNTERFACTUAL_NEARMISS.md",
    "docs/AURELIA_RESEARCH_GOVERNANCE.yaml",
    "docs/AURELIA_RELEASE_MANIFEST.yaml",
    "docs/AURELIA_STATUS_MODEL.yaml",
    "docs/AURELIA_CONTROL_HARDENING_2026-10-03.yaml",
    "docs/AURELIA_ADVERSARIAL_SOAK_PROTOCOL_2026-10-03.md",
    "docs/AURELIA_STAKE_POLICY_2026-10-03.md",
    "docs/AURELIA_RESEARCH_QUALITY_CONTROLS_2026-10-03.md",
    "docs/AURELIA_RUNTIME_BASELINE_2026-10-03.md",
)

HARDENING_MARKERS = (
    "assurance/aurelia_hardening.py",
    "assurance/adversarial_matrix.py",
    "assurance/evidence_writer.py",
    "assurance/research_quality.py",
    "assurance/soak_protocol.py",
    "assurance/operational_hardening.py",
)


def evaluate_repository(root: Path) -> list[dict]:
    results: list[dict] = []

    missing = [p for p in MANDATORY_DOCUMENTS if not (root / p).exists()]
    results.append({
        "name": "ASSURANCE_DOCUMENTS",
        "status": "PASS" if not missing else "FAIL",
        "detail": "All assurance documents present." if not missing else "Missing: " + ", ".join(missing),
    })

    missing = [p for p in HARDENING_MARKERS if not (root / p).exists()]
    results.append({
        "name": "HARDENING_CONTRACTS",
        "status": "PASS" if not missing else "FAIL",
        "detail": "All hardening contracts present." if not missing else "Missing: " + ", ".join(missing),
    })

    source, source_missing = runtime_source_status(root)
    if source == "HISTORICAL":
        source_status, detail = "PASS", "Historical v1.27 runtime markers are present."
    elif source == "NEW_BASELINE":
        source_status, detail = "PASS", "Explicit new AURELIA runtime baseline is present; historical v1.27 source is not inferred."
    else:
        source_status = "BLOCKED"
        detail = "Neither authoritative historical runtime nor complete new baseline is synced; missing baseline markers: " + ", ".join(source_missing)
    results.append({"name": "AURELIA_SOURCE_SYNC", "status": source_status, "detail": detail})

    evidence_status, evidence_detail = validate_evidence_bundle(root)
    results.append({"name": "PRODUCTION_EVIDENCE", "status": evidence_status, "detail": evidence_detail})

    results.append({
        "name": "LIVE_EXECUTION",
        "status": "BLOCKED",
        "detail": "Repository certification never grants live capital authority.",
    })
    return results


def overall(results: list[dict]) -> str:
    blocking = [
        r for r in results
        if r["status"] in {"FAIL", "BLOCKED"} and r["name"] != "LIVE_EXECUTION"
    ]
    return "READY_FOR_CAPITAL_REVIEW" if not blocking else "NOT_READY"


# Backward-compatible name used by the existing assurance test suite.
_overall_status = overall


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    results = evaluate_repository(root)
    status = overall(results)

    for result in results:
        print(f"[{result['status']}] {result['name']}: {result['detail']}")
    print(f"CERTIFICATION_RESULT={status}")
    print("FINAL_EXECUTION_AUTHORIZATION=FALSE")
    print("LIVE_EXECUTION=BLOCKED")

    if args.json_out:
        output = root / args.json_out
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "repository": "Anto-30/aurelia-trading",
                    "certification_result": status,
                    "final_execution_authorization": False,
                    "live_execution": "BLOCKED",
                    "results": results,
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        print(f"CERTIFICATION_REPORT={output}")

    return 0 if status == "READY_FOR_CAPITAL_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
