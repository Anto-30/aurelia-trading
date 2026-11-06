from __future__ import annotations

"""Fail CI if any GitHub Actions workflow injects a Deriv account secret."""

import re
import sys
from pathlib import Path

SECRET_REFERENCE = re.compile(r"\bsecrets\s*\.\s*DERIV_[A-Z0-9_]+\b", re.IGNORECASE)
CREDENTIAL_ENV_KEY = re.compile(
    r"^\s*DERIV_(?:AUTH_TOKEN|PAT|OAUTH_ACCESS_TOKEN|OAUTH_REFRESH_TOKEN|REFRESH_TOKEN)\s*:",
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
            # Ignore YAML comments, but never print the matched line or value.
            source = line.split("#", 1)[0]
            if SECRET_REFERENCE.search(source):
                findings.append((path.name, line_number, "DERIV_SECRET_REFERENCE"))
            if CREDENTIAL_ENV_KEY.match(source):
                findings.append((path.name, line_number, "DERIV_CREDENTIAL_ENV_BINDING"))
    return len(paths), findings


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    workflow_dir = repository_root / ".github" / "workflows"
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
