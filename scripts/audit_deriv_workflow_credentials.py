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
    rf"^\s*(?:{_CREDENTIAL_NAMES})\s*:|"
    rf"^\s*[A-Za-z0-9_-]+\s*:\s*\{{[^#]*?\b(?:{_CREDENTIAL_NAMES})\s*:",
    re.IGNORECASE,
)
PRODUCTION_ENVIRONMENT = re.compile(
    r"^[ \t]{4}environment[ \t]*:[ \t]*(?:['\"]?production['\"]?|\{[ \t]*name[ \t]*:[ \t]*['\"]?production['\"]?)[ \t]*(?:#.*)?$|"
    r"^[ \t]{4}environment[ \t]*:[ \t]*\r?\n[ \t]{6}name[ \t]*:[ \t]*['\"]?production['\"]?[ \t]*(?:#.*)?$",
    re.IGNORECASE | re.MULTILINE,
)
PULL_REQUEST_TRIGGER = re.compile(r"(?m)^\s{2}pull_request(?:_target)?\s*:")
SCHEDULE_TRIGGER = re.compile(r"(?m)^\s{2}schedule\s*:")
DERIV_ACCOUNT_WORKFLOW = re.compile(r"(?i)^(?:deriv|account|broker)[-_]")


def audit_workflows(workflow_dir: Path) -> tuple[int, list[tuple[str, int, str]]]:
    if not workflow_dir.is_dir():
        return 0, [(workflow_dir.as_posix(), 0, "WORKFLOW_DIRECTORY_MISSING")]

    paths = sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")])
    if not paths:
        return 0, [(workflow_dir.as_posix(), 0, "NO_WORKFLOW_FILES")]

    findings: list[tuple[str, int, str]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        # A protected environment exposes its scoped secrets to the job even
        # when no explicit secrets.* expression appears in the YAML. General
        # PR/scheduled CI and Deriv account-verification workflows must not
        # select production.
        production_line = next(
            (
                i
                for i, line in enumerate(lines, 1)
                if re.match(r"^\s{4}environment\s*:", line, re.IGNORECASE)
            ),
            0,
        )
        if production_line and PRODUCTION_ENVIRONMENT.search(text):
            if PULL_REQUEST_TRIGGER.search(text):
                findings.append(
                    (path.name, production_line, "PULL_REQUEST_PRODUCTION_ENVIRONMENT_ACCESS")
                )
            if SCHEDULE_TRIGGER.search(text):
                findings.append(
                    (path.name, production_line, "SCHEDULED_PRODUCTION_ENVIRONMENT_ACCESS")
                )
            if DERIV_ACCOUNT_WORKFLOW.match(path.stem):
                findings.append(
                    (path.name, production_line, "DERIV_ACCOUNT_PRODUCTION_ENVIRONMENT_ACCESS")
                )

        for line_number, line in enumerate(lines, 1):
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
