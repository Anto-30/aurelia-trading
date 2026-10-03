"""Repository-level certification gate.

This gate is deliberately conservative. It reports evidence status and exits
non-zero when mandatory source/evidence prerequisites are absent. It never
grants live authorization and never contacts a broker.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


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
)

IMPLEMENTATION_MARKERS = (
    "research/r100_prospective_oos_archiver.py",
    "capital",
    "execution",
)


@dataclass(frozen=True)
class GateResult:
    name: str
    status: str
    detail: str


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def evaluate_repository(root: Path) -> list[GateResult]:
    results: list[GateResult] = []

    docs_missing = [p for p in MANDATORY_DOCUMENTS if not _exists(root, p)]
    results.append(
        GateResult(
            "ASSURANCE_DOCUMENTS",
            "PASS" if not docs_missing else "FAIL",
            "All assurance documents present." if not docs_missing
            else f"Missing: {', '.join(docs_missing)}",
        )
    )

    source_missing = [p for p in IMPLEMENTATION_MARKERS if not _exists(root, p)]
    results.append(
        GateResult(
            "AURELIA_SOURCE_SYNC",
            "PASS" if not source_missing else "BLOCKED",
            "Core implementation markers present."
            if not source_missing
            else "Actual AURELIA implementation is not synced; "
                 f"missing markers: {', '.join(source_missing)}",
        )
    )

    results.append(
        GateResult(
            "LIVE_EXECUTION",
            "BLOCKED",
            "This assurance gate never grants live authorization.",
        )
    )
    return results


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    results = evaluate_repository(root)
    for result in results:
        print(f"[{result.status}] {result.name}: {result.detail}")

    blocked = any(r.status in {"FAIL", "BLOCKED"} for r in results)
    if blocked:
        print("CERTIFICATION_RESULT=NOT_READY")
        return 1

    print("CERTIFICATION_RESULT=EVIDENCE_BASELINE_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
