#!/usr/bin/env python3
"""Install optional Deriv verification credentials for the sealed VERIFY_ONLY runtime.

This credential store intentionally excludes the attestation signing key and any
capital-authority flag. Missing inputs are a non-fatal no-op; invalid partial
configuration is rejected without overwriting the existing file.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

READONLY_FILE = Path("/etc/aurelia/aurelia-deriv-readonly-secrets.env")


class ReadOnlyProvisioningError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _value(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name, "")
    if not isinstance(value, str):
        raise ReadOnlyProvisioningError(f"INVALID_VALUE_TYPE_{name}")
    if any(ch in value for ch in ("\n", "\r", "\x00")):
        raise ReadOnlyProvisioningError(f"MULTILINE_VALUE_REJECTED_{name}")
    if value != value.strip():
        raise ReadOnlyProvisioningError(f"WHITESPACE_BOUNDARY_REJECTED_{name}")
    return value


def build_env_text(payload: dict[str, Any]) -> str | None:
    if not isinstance(payload, dict):
        raise ReadOnlyProvisioningError("INPUT_MUST_BE_JSON_OBJECT")
    names = (
        "DERIV_AUTH_TOKEN",
        "DERIV_APP_ID",
        "DERIV_EXPECTED_LOGINID",
        "DERIV_EXPECTED_CURRENCY",
        "DERIV_ENVIRONMENT",
        "DERIV_AUTH_MODE",
    )
    values = {name: _value(payload, name) for name in names}
    # No credential/account binding means public-data-only VERIFY_ONLY mode.
    # Currency may be configured independently and is not sufficient to attempt auth.
    if not values["DERIV_AUTH_TOKEN"] and not values["DERIV_EXPECTED_LOGINID"]:
        return None
    required = ("DERIV_AUTH_TOKEN", "DERIV_EXPECTED_LOGINID", "DERIV_EXPECTED_CURRENCY", "DERIV_ENVIRONMENT", "DERIV_AUTH_MODE")
    missing = [name for name in required if not values[name]]
    if missing:
        raise ReadOnlyProvisioningError("PARTIAL_READ_ONLY_CONFIG_MISSING:" + ",".join(missing))
    mode = values["DERIV_AUTH_MODE"].lower()
    if mode not in {"pat", "oauth"}:
        raise ReadOnlyProvisioningError("DERIV_AUTH_MODE_INVALID")
    if values["DERIV_ENVIRONMENT"].lower() not in {"real", "demo"}:
        raise ReadOnlyProvisioningError("DERIV_ENVIRONMENT_INVALID")
    if mode == "pat" and not values["DERIV_APP_ID"]:
        raise ReadOnlyProvisioningError("DERIV_APP_ID_REQUIRED_FOR_PAT")

    ordered = [
        ("DERIV_AUTH_TOKEN", values["DERIV_AUTH_TOKEN"]),
        ("DERIV_EXPECTED_LOGINID", values["DERIV_EXPECTED_LOGINID"]),
        ("DERIV_EXPECTED_CURRENCY", values["DERIV_EXPECTED_CURRENCY"]),
        ("DERIV_ENVIRONMENT", values["DERIV_ENVIRONMENT"].lower()),
        ("DERIV_AUTH_MODE", mode),
    ]
    if values["DERIV_APP_ID"]:
        ordered.insert(1, ("DERIV_APP_ID", values["DERIV_APP_ID"]))
    return "".join(f"{name}={value}\n" for name, value in ordered)


def provision(payload: dict[str, Any], destination: Path = READONLY_FILE) -> bool:
    content = build_env_text(payload)
    if content is None:
        return False
    parent = destination.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(parent, 0o700)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(parent), text=True
    )
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, destination)
        os.chmod(destination, 0o600)
        dirfd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        written = provision(payload, READONLY_FILE)
    except json.JSONDecodeError:
        print("AURELIA_DERIV_READONLY_PROVISIONING=BLOCKED", file=sys.stderr)
        print("REASON=INPUT_JSON_INVALID", file=sys.stderr)
        return 2
    except ReadOnlyProvisioningError as exc:
        print("AURELIA_DERIV_READONLY_PROVISIONING=BLOCKED", file=sys.stderr)
        print(f"REASON={exc.reason}", file=sys.stderr)
        return 2
    except OSError as exc:
        print("AURELIA_DERIV_READONLY_PROVISIONING=BLOCKED", file=sys.stderr)
        print(f"REASON=SECURE_FILE_WRITE_FAILED:{type(exc).__name__}", file=sys.stderr)
        return 2

    print("AURELIA_DERIV_READONLY_PROVISIONING=" + ("COMPLETE" if written else "NOT_CONFIGURED"))
    print("SECRET_VALUES_PRINTED=false")
    print("CAPITAL_AUTHORITY_GRANTED=false")
    print("ORDER_SUBMISSION_PERMITTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
