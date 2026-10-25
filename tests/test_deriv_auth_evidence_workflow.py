from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
LEGACY_WORKFLOWS = (
    ".github/workflows/deriv-auth-evidence.yml",
    ".github/workflows/deriv-session-verification.yml",
    ".github/workflows/deriv-verify-only-lifecycle.yml",
)


def test_legacy_deriv_workflows_are_retired_without_secret_or_network_access() -> None:
    for relative_path in LEGACY_WORKFLOWS:
        workflow_path = ROOT / relative_path
        workflow = workflow_path.read_text(encoding="utf-8")

        assert "workflow_dispatch:" in workflow, relative_path
        assert "LEGACY_DERIV_WORKFLOW=RETIRED" in workflow, relative_path
        assert "exit 1" in workflow, relative_path
        assert "permissions: {}" in workflow, relative_path

        # Legacy workflows must not expose protected credentials to branch code,
        # schedule recurring account access, download source, or run a verifier.
        assert not re.search(r"\$\{\{[^}]*\bsecrets\s*\.", workflow), relative_path
        assert not re.search(r"(?m)^\s*environment:\s*production\s*$", workflow), relative_path
        assert "schedule:" not in workflow, relative_path
        assert "actions/checkout@" not in workflow, relative_path
        assert "python scripts/verify_deriv_" not in workflow, relative_path
        assert "Upload" not in workflow, relative_path
