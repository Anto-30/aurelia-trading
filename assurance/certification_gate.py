"""Repository-level certification gate.

This gate reports whether the existing AURELIA architecture and its recorded
production evidence are complete enough for a separate capital-review/canary
decision. It never grants live authorization and never contacts a broker.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .certification_evidence import REQUIRED_RUNTIME_MARKERS, validate_evidence_bundle

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
)

HARDENING_MARKERS = (
    "assurance/aurelia_hardening.py",
    "assurance/adversarial_matrix.py",
    "assurance/evidence_writer.py",
    "assurance/research_quality.py",
    "assurance/soak_protocol.py",
    "assurance/operational_hardening.py",
)


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def evaluate_repository(root: Path) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    docs_missing = [p for p in MANDATORY_DOCUMENTS if not _exists(root, p)]
    results.append({
        "name": "ASSURANCE_DOCUMENTS",
        "status": "PASS" if not docs_missing else "FAIL",
        "detail": "All assurance documents present." if not docs_missing
        else f"Missing: {', '.join(docs_missing)}",
    })

    hardening_missing = [p for p in HARDENING_MARKERS if not _exists(root, p)]
    results.append({
        "name": "HARDENING_CONTRACTS",
        "status": "PASS" if not hardening_missing else "FAIL",
        "detail": "All hardening contracts present." if not hardening_missing
        else f"Missing: {', '.join(hardening_missing)}",
    })

    runtime_missing = [p for p in REQUIRED_RUNTIME_MARKERS if not _exists(root, p)]
    results.append({
        "name": "AURELIA_SOURCE_SYNC",
        "status": "PASS" if not runtime_missing else "BLOCKED",
        "detail": "Historical runtime markers are present."
        if not runtime_missing
        else "Authoritative runtime is not synced; "
             f"missing markers: {', '.join(runtime_missing)}",
    })

    evidence_status, evidence_detail = validate_evidence_bundle(root)
    results.append({
        "name": "PRODUCTION_EVIDENCE",
        "status": evidence_status,
        "detail": evidence_detail,
    })

    # This remains blocked deliberately. Repository certification is not a
    # capital-authority mechanism.
    results.append({
        "name": "LIVE_EXECUTION",
        "status": "BLOCKED",
        "detail": "Repository certification never grants live capital authority.",
    })
    return results


def _overall_status(results: list[dict[str, str]]) -> str:
    blocking = [
        r for r in results
        if r["status"] in {"FAIL", "BLOCKED"} and r["name"] != "LIVE_EXECUTION"
    ]
    return "READY_FOR_CAPITAL_REVIEW" if not blocking else "NOT_READY"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    results = evaluate_repository(root)
    overall = _overall_status(results)

    for result in results:
        print(f"[{result['status']}] {result['name']}: {result['detail']}")
    print(f"CERTIFICATION_RESULT={overall}")
    print("FINAL_EXECUTION_AUTHORIZATION=FALSE")
    print("LIVE_EXECUTION=BLOCKED")

    if args.json_out:
        payload: dict[str, Any] = {
            "repository": "Anto-30/aurelia-trading",
            "certification_result": overall,
            "final_execution_authorization": False,
            "live_execution": "BLOCKED",
            "results": results,
        }
        output = root / args.json_out
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"CERTIFICATION_REPORT={output}")

    return 0 if overall == "READY_FOR_CAPITAL_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
