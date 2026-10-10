#!/usr/bin/env python3
"""Install LIVE-only runtime credentials received over the authenticated SSH channel.

The workflow passes a JSON object on stdin. Values are never printed. The
result is an atomically replaced, root-only env file separate from the
non-secret runtime configuration file.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

LIVE_SECRET_FILE = Path("/etc/aurelia/aurelia-live-secrets.env")

REQUIRED = (
    "DERIV_AUTH_TOKEN",
    "DERIV_EXPECTED_LOGINID",
    "DERIV_EXPECTED_CURRENCY",
    "DERIV_ENVIRONMENT",
    "DERIV_AUTH_MODE",
    "AURELIA_ATTESTATION_SIGNING_KEY",
    "AURELIA_RUNTIME_ID",
)
OPTIONAL = ("DERIV_APP_ID",)


class RuntimeSecretProvisioningError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _single_line_value(payload: dict[str, Any], name: str, *, required: bool) -> str:
    value = payload.get(name, "")
    if not isinstance(value, str):
        raise RuntimeSecretProvisioningError(f"INVALID_VALUE_TYPE_{name}")
    if any(ch in value for ch in ("\n", "\r", "\x00")):
        raise RuntimeSecretProvisioningError(f"MULTILINE_VALUE_REJECTED_{name}")
    if value != value.strip():
        raise RuntimeSecretProvisioningError(f"WHITESPACE_BOUNDARY_REJECTED_{name}")
    if required and not value:
        raise RuntimeSecretProvisioningError(f"REQUIRED_VALUE_MISSING_{name}")
    return value


def build_env_text(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise RuntimeSecretProvisioningError("INPUT_MUST_BE_JSON_OBJECT")

    values = {
        name: _single_line_value(payload, name, required=True)
        for name in REQUIRED
    }
    app_id = _single_line_value(payload, "DERIV_APP_ID", required=False)
    mode = values["DERIV_AUTH_MODE"].lower()
    if mode not in {"pat", "oauth"}:
        raise RuntimeSecretProvisioningError("DERIV_AUTH_MODE_INVALID")
    if values["DERIV_ENVIRONMENT"].lower() != "real":
        raise RuntimeSecretProvisioningError("LIVE_RUNTIME_REQUIRES_REAL_ACCOUNT")
    if mode == "pat" and not app_id:
        raise RuntimeSecretProvisioningError("DERIV_APP_ID_REQUIRED_FOR_PAT")

    ordered = [
        ("DERIV_AUTH_TOKEN", values["DERIV_AUTH_TOKEN"]),
        ("DERIV_EXPECTED_LOGINID", values["DERIV_EXPECTED_LOGINID"]),
        ("DERIV_EXPECTED_CURRENCY", values["DERIV_EXPECTED_CURRENCY"]),
        ("DERIV_ENVIRONMENT", "real"),
        ("DERIV_AUTH_MODE", mode),
        ("AURELIA_ATTESTATION_SIGNING_KEY", values["AURELIA_ATTESTATION_SIGNING_KEY"]),
        ("AURELIA_RUNTIME_ID", values["AURELIA_RUNTIME_ID"]),
    ]
    if mode == "pat":
        ordered.insert(1, ("DERIV_APP_ID", app_id))
    elif app_id:
        ordered.insert(1, ("DERIV_APP_ID", app_id))

    return "".join(f"{name}={value}\n" for name, value in ordered)


def provision(payload: dict[str, Any], destination: Path = LIVE_SECRET_FILE) -> None:
    """Validate and atomically install a private LIVE-only runtime env file."""
    content = build_env_text(payload)
    parent = destination.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(parent, 0o700)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=str(parent),
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
        directory_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        provision(payload, LIVE_SECRET_FILE)
    except json.JSONDecodeError:
        print("AURELIA_RUNTIME_SECRET_PROVISIONING=BLOCKED", file=sys.stderr)
        print("REASON=INPUT_JSON_INVALID", file=sys.stderr)
        return 2
    except RuntimeSecretProvisioningError as exc:
        print("AURELIA_RUNTIME_SECRET_PROVISIONING=BLOCKED", file=sys.stderr)
        print(f"REASON={exc.reason}", file=sys.stderr)
        return 2
    except OSError as exc:
        print("AURELIA_RUNTIME_SECRET_PROVISIONING=BLOCKED", file=sys.stderr)
        print(f"REASON=SECURE_FILE_WRITE_FAILED:{type(exc).__name__}", file=sys.stderr)
        return 2

    print("AURELIA_RUNTIME_SECRET_PROVISIONING=COMPLETE")
    print("SECRET_VALUES_PRINTED=false")
    print("SECRET_FILE_PERMISSIONS=0600")
    print("CAPITAL_AUTHORITY_GRANTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
