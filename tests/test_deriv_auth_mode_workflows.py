from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SAFE_DERIV_AUTH_MODE_EXPRESSION = (
    "${{ vars.DERIV_AUTH_MODE == 'pat' && 'pat' "
    "|| vars.DERIV_AUTH_MODE == 'oauth' && 'oauth' "
    "|| 'invalid' }}"
)


def test_workflow_auth_mode_assignments_are_allowlisted() -> None:
    assignments: list[tuple[str, int, str]] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^\s*DERIV_AUTH_MODE\s*:", line):
                value = line.split(":", 1)[1].strip()
                assignments.append((str(path.relative_to(ROOT)), line_number, value))

    assert assignments, "Expected at least one Deriv auth-mode workflow assignment"
    unsafe = [
        f"{path}:{line}: {value}"
        for path, line, value in assignments
        if value != SAFE_DERIV_AUTH_MODE_EXPRESSION
    ]
    assert not unsafe, "Unallowlisted DERIV_AUTH_MODE workflow assignments:\n" + "\n".join(unsafe)


def test_workflows_never_read_auth_mode_from_a_secret() -> None:
    offenders = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        content = path.read_text(encoding="utf-8")
        if "secrets.DERIV_AUTH_MODE" in content:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, "DERIV_AUTH_MODE is non-secret configuration; secret fallback found in: " + ", ".join(offenders)

def test_manual_auth_mode_repair_workflow_is_protected_and_nonsecret() -> None:
    path = WORKFLOWS / "configure-deriv-auth-mode.yml"
    content = path.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in content
    assert "environment: production" in content
    assert "actions: write" in content
    assert "options:" in content and "- pat" in content and "- oauth" in content
    assert "DERIV_AUTH_MODE" in content
    assert "secrets." not in content
    assert "SECRET_VALUES_ACCESSED=false" in content
    assert "LIVE_EXECUTION=BLOCKED" in content
    assert "FINAL_EXECUTION_AUTHORIZATION=false" in content

def test_assurance_prerequisite_gate_does_not_default_missing_mode_to_pat() -> None:
    path = WORKFLOWS / "aurelia-assurance.yml"
    content = path.read_text(encoding="utf-8")
    line = next(line for line in content.splitlines() if "DERIV_AUTH_CONFIGURED:" in line)
    assert "vars.DERIV_AUTH_MODE == 'pat'" in line
    assert "vars.DERIV_AUTH_MODE == 'oauth'" in line
    assert "vars.DERIV_AUTH_MODE || 'pat'" not in line
    assert "vars.DERIV_AUTH_MODE ||" not in line
