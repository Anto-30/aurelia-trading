#!/usr/bin/env python3
"""Run a verifier without echoing potentially identifying stdout/stderr to CI logs."""
from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Sequence

_SAFE_LINES = (
    re.compile(r"^DERIV_AUTH_SESSION=(?:VERIFIED|FAILED|NOT_CONFIGURED|BLOCKED)$"),
    re.compile(r"^DERIV_AUTH_SESSION_REASON=[A-Z0-9_]+$"),
    re.compile(r"^DERIV_BROKER_EVIDENCE=(?:PROVEN|FAILED)$"),
    re.compile(r"^REASON=[A-Z0-9_]+$"),
)


def redacted_status_lines(output: str) -> list[str]:
    """Keep only a strict status/reason allowlist; never forward arbitrary output."""
    safe: list[str] = []
    seen: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if any(pattern.fullmatch(line) for pattern in _SAFE_LINES) and line not in seen:
            safe.append(line)
            seen.add(line)
    return safe


def run_redacted(command: Sequence[str]) -> int:
    if not command:
        print("VERIFIER_STATUS=INVALID_COMMAND")
        return 2

    result = subprocess.run(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        check=False,
    )
    for line in redacted_status_lines(result.stdout or ""):
        print(line)

    if result.returncode == 0:
        print("VERIFIER_DIAGNOSTICS=REDACTED")
        return 0

    if not redacted_status_lines(result.stdout or ""):
        print("VERIFIER_STATUS=FAILED")
    print(f"VERIFIER_EXIT_CODE={result.returncode}")
    print("VERIFIER_DIAGNOSTICS=REDACTED")
    return result.returncode if result.returncode > 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_redacted(sys.argv[1:]))
