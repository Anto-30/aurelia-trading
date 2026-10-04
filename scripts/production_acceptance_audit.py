#!/usr/bin/env python3
"""Static production acceptance audit for AURELIA.

This audit never grants live authorization. It verifies that the repository
contains the required control contracts and that the checked-in capital lock
remains fail-closed.
"""
from __future__ import annotations

import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "config/LIVE_LOCK.yaml",
    "docs/AURELIA_PRODUCTION_STANDARD.yaml",
    "docs/AURELIA_TEST_ORACLE_MATRIX.yaml",
    "docs/PRODUCTION_READINESS.md",
    "scripts/live_release_gate.py",
    "scripts/verify_deriv_session.py",
    "scripts/verify_deriv_transaction_lifecycle.py",
    ".github/workflows/aurelia-assurance.yml",
)

FORBIDDEN_LOCK_VALUES = {
    "live_trading_enabled": "true",
    "FINAL_EXECUTION_AUTHORIZATION": "true",
    "LIVE_EXECUTION": "ALLOWED",
}

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}"),
    re.compile(r"(?i)(DERIV_(?:AUTH_TOKEN|PAT))\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
)

REQUIRED_STANDARD_IDS = tuple(f"CERT-{i:03d}" for i in range(1, 36))


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    for rel in REQUIRED_FILES:
        if not (ROOT / rel).is_file():
            failures.append(f"MISSING_FILE:{rel}")

    if not failures:
        lock = read("config/LIVE_LOCK.yaml")
        for key, forbidden in FORBIDDEN_LOCK_VALUES.items():
            pattern = re.compile(rf"(?m)^\s*{re.escape(key)}\s*:\s*{re.escape(forbidden)}\s*$")
            if pattern.search(lock):
                failures.append(f"UNSAFE_LOCK:{key}={forbidden}")
        if "capital_plane_mode: VERIFY_ONLY" not in lock:
            failures.append("LOCK_NOT_VERIFY_ONLY")
        if "blind_resubmission: false" not in lock:
            failures.append("BLIND_RESUBMISSION_NOT_DISABLED")
        if "external_repositories_capital_forbidden: true" not in lock:
            failures.append("EXTERNAL_REPOS_NOT_CAPITAL_FORBIDDEN")

        standard = read("docs/AURELIA_PRODUCTION_STANDARD.yaml")
        for cert_id in REQUIRED_STANDARD_IDS:
            if f"id: {cert_id}" not in standard:
                failures.append(f"MISSING_STANDARD_REQUIREMENT:{cert_id}")

    # Scan text files for obvious credential material. This is deliberately
    # conservative: false positives are reported for human review rather than
    # suppressing a possible leak.
    skip_dirs = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", "node_modules"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in skip_dirs for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"POSSIBLE_SECRET:{path.relative_to(ROOT)}")
                break

    if failures:
        print("AURELIA_PRODUCTION_ACCEPTANCE=AUDIT_FAILED")
        for item in failures:
            print(item)
        return 1

    print("AURELIA_PRODUCTION_ACCEPTANCE=AUDIT_PASS")
    print("CAPITAL_MOVEMENT_PERMITTED=false")
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    print("LIVE_EXECUTION=BLOCKED")
    print("NOTE=Static repository audit only; this is not broker proof or live authorization.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
