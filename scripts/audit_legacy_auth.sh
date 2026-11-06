#!/usr/bin/env bash
# Static audit for credential exposure in GitHub Actions workflow definitions.
# Prints file/line identifiers only; never prints matched credential text.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT_DIR" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
workflow_dir = root / ".github" / "workflows"
files = sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")])
if not files:
    print("AUTH_AUDIT=FAIL reason=NO_WORKFLOW_FILES")
    raise SystemExit(2)

failures: list[str] = []
warnings: list[str] = []
deriv_ref = re.compile(
    r"secrets[.](?:DERIV_AUTH_TOKEN|DERIV_PAT|DERIV_OAUTH_ACCESS_TOKEN|DERIV_OAUTH_REFRESH_TOKEN|DERIV_REFRESH_TOKEN)(?:[^A-Za-z0-9_]|$)"
)
hardcoded_patterns = [
    ("GITHUB_TOKEN_LITERAL", re.compile(r"(?:^|[^A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})(?:$|[^A-Za-z0-9_])")),
    ("AWS_ACCESS_KEY_LITERAL", re.compile(r"(?:^|[^A-Za-z0-9_])AKIA[0-9A-Z]{16}(?:$|[^A-Za-z0-9_])")),
    ("GOOGLE_API_KEY_LITERAL", re.compile(r"(?:^|[^A-Za-z0-9_])AIza[0-9A-Za-z_-]{35}(?:$|[^A-Za-z0-9_])")),
    ("PRIVATE_KEY_BLOCK", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("BEARER_TOKEN_LITERAL", re.compile(r"(?i)(?:^|[^A-Za-z0-9_])Bearer[ ]+[A-Za-z0-9._~+/-]{24,}")),
]
manual_auth_files: list[str] = []
scheduled_auth_files: list[str] = []
pr_auth_files: list[str] = []

for path in files:
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    is_scheduled = bool(re.search(r"(?m)^[ ]{2}schedule[ ]*:", text))
    has_pr_trigger = bool(re.search(r"(?m)^[ ]{2}pull_request(?:_target)?[ ]*:", text))
    auth_line_numbers = [
        str(i) for i, line in enumerate(lines, 1) if deriv_ref.search(line)
    ]
    for i, line in enumerate(lines, 1):
        for code, pattern in hardcoded_patterns:
            if pattern.search(line):
                failures.append(f"{code} {rel}:{i}")
        if re.search(r"(?i)^[ ]*(?:DERIV_AUTH_TOKEN|DERIV_PAT|DERIV_OAUTH_ACCESS_TOKEN|DERIV_OAUTH_REFRESH_TOKEN)[ ]*:", line):
            rhs = line.split(":", 1)[1].strip()
            if rhs and not rhs.startswith("$") and rhs not in ('""', "''", "null"):
                failures.append(f"LITERAL_DERIV_CREDENTIAL_ASSIGNMENT {rel}:{i}")
        if re.search(r"(?i)(?:^|[ ;])set[ ]+-x(?:$|[ ;])|bash[ ]+-x", line):
            warnings.append(f"TRACE_MODE_REVIEW {rel}:{i}")
        if re.search(r"(?i)(?:echo|printf).*?(?:DERIV_AUTH_TOKEN|DERIV_PAT|DERIV_OAUTH_ACCESS_TOKEN)", line):
            failures.append(f"POSSIBLE_CREDENTIAL_LOGGING {rel}:{i}")
        if re.search(r"(?i)printenv[ ]+(?:DERIV_AUTH_TOKEN|DERIV_PAT|DERIV_OAUTH_ACCESS_TOKEN)", line):
            failures.append(f"POSSIBLE_CREDENTIAL_LOGGING {rel}:{i}")

    if is_scheduled and auth_line_numbers:
        scheduled_auth_files.append(rel)
        failures.append(
            f"SCHEDULED_DERIV_CREDENTIAL_INJECTION {rel}:lines={','.join(auth_line_numbers)}"
        )
    elif has_pr_trigger and auth_line_numbers:
        pr_auth_files.append(rel)
        failures.append(
            f"PULL_REQUEST_DERIV_CREDENTIAL_INJECTION {rel}:lines={','.join(auth_line_numbers)}"
        )
    elif auth_line_numbers:
        manual_auth_files.append(rel)
        if not re.search(r"(?m)^[ ]{4}environment[ ]*:[ ]*production[ ]*$", text):
            warnings.append(f"MANUAL_AUTH_WORKFLOW_ENVIRONMENT_REVIEW {rel}")

    if not re.search(r"(?m)^permissions[ ]*:", text):
        warnings.append(f"WORKFLOW_PERMISSIONS_NOT_EXPLICIT {rel}")
    if re.search(r"(?mi)^[ ]*(?:permissions[ ]*:[ ]*write-all|[A-Za-z_-]+[ ]*:[ ]*write-all)[ ]*$", text):
        failures.append(f"OVERBROAD_GITHUB_TOKEN_PERMISSION {rel}")

print(f"AUTH_AUDIT_FILES={len(files)}")
print(f"AUTH_AUDIT_SCHEDULED_DERIV_WORKFLOWS={len(scheduled_auth_files)}")
print(f"AUTH_AUDIT_PULL_REQUEST_DERIV_WORKFLOWS={len(pr_auth_files)}")
print(f"AUTH_AUDIT_MANUAL_DERIV_WORKFLOWS={len(manual_auth_files)}")
for item in sorted(set(warnings)):
    print("WARN " + item)
for item in sorted(set(failures)):
    print("FAIL " + item)
if failures:
    print(f"AUTH_AUDIT=FAIL findings={len(set(failures))}")
    raise SystemExit(1)
print(f"AUTH_AUDIT=PASS warnings={len(set(warnings))}")
PY
