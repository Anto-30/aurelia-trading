from __future__ import annotations

"""Fail CI if a GitHub Actions workflow exposes any Deriv account-plane input."""

import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from runtime.security.deriv_auth_gate import ACCOUNT_CREDENTIAL_ENV_NAMES

DERIV_SECRET_REFERENCE = re.compile(
    r"\bsecrets\s*(?:\.\s*DERIV_[A-Z0-9_]+|\[\s*['\"]DERIV_[A-Z0-9_]+['\"]\s*\])",
    re.IGNORECASE,
)
DERIV_DYNAMIC_SECRET_REFERENCE = re.compile(
    r"\bsecrets\s*\[[^]\n]*\bDERIV_[A-Z0-9_]+\b[^]\n]*\]",
    re.IGNORECASE,
)
_CREDENTIAL_NAMES = "|".join(
    re.escape(name)
    for name in sorted(ACCOUNT_CREDENTIAL_ENV_NAMES, key=len, reverse=True)
)
CREDENTIAL_ENV_KEY = re.compile(
    rf"(?:^\s*|[{{,]\s*)(?:{_CREDENTIAL_NAMES})\s*:",
    re.IGNORECASE,
)


def audit_workflows(workflow_dir: Path) -> tuple[int, list[tuple[str, int, str]]]:
    if not workflow_dir.is_dir():
        return 0, [(workflow_dir.as_posix(), 0, "WORKFLOW_DIRECTORY_MISSING")]

    paths = sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")])
    if not paths:
        return 0, [(workflow_dir.as_posix(), 0, "NO_WORKFLOW_FILES")]

    findings: list[tuple[str, int, str]] = []
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # Ignore YAML comments; never print matched workflow text or values.
            source = line.split("#", 1)[0]
            if (
                DERIV_SECRET_REFERENCE.search(source)
                or DERIV_DYNAMIC_SECRET_REFERENCE.search(source)
            ):
                findings.append((path.name, line_number, "DERIV_SECRET_REFERENCE"))
            if CREDENTIAL_ENV_KEY.search(source):
                findings.append((path.name, line_number, "DERIV_ACCOUNT_INPUT_BINDING"))
    return len(paths), findings


def main() -> int:
    workflow_dir = REPOSITORY_ROOT / ".github" / "workflows"
    workflow_count, findings = audit_workflows(workflow_dir)
    print(f"DERIV_WORKFLOW_AUDIT_FILES={workflow_count}")
    if findings:
        for path, line_number, code in sorted(set(findings)):
            print(f"FAIL {path}:{line_number} {code}")
        print(f"DERIV_WORKFLOW_CREDENTIAL_AUDIT=FAIL findings={len(set(findings))}")
        return 1
    print("DERIV_WORKFLOW_CREDENTIAL_AUDIT=PASS")
    print("DERIV_ACCOUNT_CREDENTIAL_INJECTION=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
