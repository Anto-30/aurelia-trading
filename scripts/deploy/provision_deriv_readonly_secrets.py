#!/usr/bin/env python3
"""Fail-closed compatibility shim for the retired Deriv read-only credential store.

Deriv's required account-list and authenticated OTP endpoints are trade-scoped.
No genuinely read-only account scope is documented, so this module must never
read stdin, inspect credential values, or create/overwrite an env file.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

READONLY_FILE = Path("/etc/aurelia/aurelia-deriv-readonly-secrets.env")
BLOCK_REASON = "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"


class ReadOnlyProvisioningError(ValueError):
    def __init__(self, reason: str = BLOCK_REASON) -> None:
        super().__init__(reason)
        self.reason = reason


def build_env_text(payload: dict[str, Any]) -> str | None:
    raise ReadOnlyProvisioningError()


def provision(payload: dict[str, Any], destination: Path = READONLY_FILE) -> bool:
    raise ReadOnlyProvisioningError()


def main() -> int:
    # Deliberately do not parse stdin: input may contain a trade-scoped token.
    print("AURELIA_DERIV_READONLY_PROVISIONING=BLOCKED")
    print(f"REASON={BLOCK_REASON}")
    print("SECRET_VALUES_READ=false")
    print("SECRET_VALUES_WRITTEN=false")
    print("CAPITAL_AUTHORITY_GRANTED=false")
    print("ORDER_SUBMISSION_PERMITTED=false")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
