#!/usr/bin/env python3
"""Deprecated Deriv credential provisioner; account credentials are not provisioned."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

READONLY_FILE = Path("/etc/aurelia/aurelia-deriv-readonly-secrets.env")
FORBIDDEN_CREDENTIALS = (
    "DERIV_AUTH_TOKEN",
    "DERIV_PAT",
    "DERIV_OAUTH_ACCESS_TOKEN",
    "DERIV_OAUTH_REFRESH_TOKEN",
    "DERIV_REFRESH_TOKEN",
)


class ReadOnlyProvisioningError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def build_env_text(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ReadOnlyProvisioningError("INPUT_MUST_BE_JSON_OBJECT")
    for name in FORBIDDEN_CREDENTIALS:
        value = payload.get(name, "")
        if value not in ("", None):
            raise ReadOnlyProvisioningError(
                "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"
            )
    if any(payload.get(name) for name in (
        "DERIV_EXPECTED_LOGINID",
        "DERIV_AUTHORIZED_ACCOUNT_ID",
        "DERIV_APP_ID",
    )):
        raise ReadOnlyProvisioningError(
            "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"
        )
    return None


def provision(payload: dict[str, Any], destination: Path = READONLY_FILE) -> bool:
    build_env_text(payload)
    # Public market-data research does not need a credential file.
    # Existing credential files are deliberately not modified by this helper.
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        provision(payload, READONLY_FILE)
    except json.JSONDecodeError:
        print("AURELIA_DERIV_READONLY_PROVISIONING=BLOCKED", file=sys.stderr)
        print("REASON=INPUT_JSON_INVALID", file=sys.stderr)
        return 2
    except ReadOnlyProvisioningError as exc:
        print("AURELIA_DERIV_READONLY_PROVISIONING=BLOCKED", file=sys.stderr)
        print(f"REASON={exc.reason}", file=sys.stderr)
        return 2

    print("AURELIA_DERIV_READONLY_PROVISIONING=NOT_REQUIRED")
    print("PUBLIC_RESEARCH_AUTHENTICATION=NONE")
    print("ACCOUNT_EVIDENCE=BLOCKED_READ_ONLY_SCOPE_UNAVAILABLE")
    print("SECRET_VALUES_PRINTED=false")
    print("CAPITAL_AUTHORITY_GRANTED=false")
    print("ORDER_SUBMISSION_PERMITTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
