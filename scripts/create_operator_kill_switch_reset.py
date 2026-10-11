#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from runtime.core.operator_reset import create_operator_reset_record


def _read_private_env_value(path: Path, name: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise SystemExit("Secure runtime secret file is unavailable; reset denied")
    matches = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = raw.partition("=")
            if sep and key.strip() == name:
                matches.append(value)
    except (OSError, UnicodeError):
        raise SystemExit("Secure runtime secret file is unreadable; reset denied") from None
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one {name} entry in secure runtime secret file")
    value = matches[0]
    if "\n" in value or "\r" in value or "\x00" in value or value != value.strip():
        raise SystemExit(f"{name} is malformed; reset denied")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a short-lived, signed AURELIA kill-switch reset request. "
            "This does not itself enable trading."
        )
    )
    parser.add_argument("--account-loginid", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--operator-id", required=True)
    parser.add_argument(
        "--state-path",
        default="/var/lib/aurelia/kill-switch-state.json",
    )
    parser.add_argument(
        "--deployed-source-sha-path",
        default="/var/lib/aurelia/DEPLOYED_SOURCE_SHA",
    )
    parser.add_argument(
        "--secret-env-file",
        default="/etc/aurelia/aurelia-live-secrets.env",
    )
    parser.add_argument(
        "--output",
        default=os.getenv(
            "AURELIA_OPERATOR_RESET_OUTPUT_PATH",
            "/var/lib/aurelia/operator-kill-switch-reset.json",
        ),
    )
    args = parser.parse_args()

    secret_file = Path(args.secret_env_file)
    signing_key = os.getenv("AURELIA_OPERATOR_RESET_SIGNING_KEY", "").strip()
    if not signing_key:
        signing_key = _read_private_env_value(
            secret_file, "AURELIA_OPERATOR_RESET_SIGNING_KEY"
        )
    if len(signing_key) < 32:
        raise SystemExit("Operator reset signing key is too short; reset denied")

    configured_loginid = (
        os.getenv("DERIV_EXPECTED_LOGINID", "").strip()
        or os.getenv("DERIV_AUTHORIZED_ACCOUNT_ID", "").strip()
    )
    if not configured_loginid:
        try:
            configured_loginid = _read_private_env_value(secret_file, "DERIV_EXPECTED_LOGINID")
        except SystemExit:
            configured_loginid = _read_private_env_value(
                secret_file, "DERIV_AUTHORIZED_ACCOUNT_ID"
            )
    if args.account_loginid.strip() != configured_loginid:
        raise SystemExit("Requested account does not match the configured Deriv account; reset denied")

    deployed_path = Path(args.deployed_source_sha_path)
    try:
        deployed_sha = deployed_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise SystemExit("Deployed source SHA is unavailable; reset denied") from None
    if not deployed_sha or args.source_sha.strip() != deployed_sha:
        raise SystemExit("Source revision does not match the deployed runtime; reset denied")

    state_path = Path(args.state_path)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise SystemExit("Kill-switch state unavailable or invalid; reset denied") from None
    if not isinstance(state, dict) or state.get("schema") != "aurelia.kill_switch_state.v1":
        raise SystemExit("Kill-switch state schema invalid; reset denied")
    if state.get("state") != "TRIPPED":
        raise SystemExit("Kill switch is not in TRIPPED state; reset denied")
    generation = state.get("generation")
    reason = state.get("reason")
    fault_source_sha = str(state.get("fault_source_sha") or state.get("source_sha") or "").strip()
    if not fault_source_sha:
        raise SystemExit("Fault source revision is missing from persisted state; reset denied")

    record = create_operator_reset_record(
        signing_key=signing_key,
        operator_id=args.operator_id,
        reason=str(reason or ""),
        source_sha=deployed_sha,
        fault_source_sha=fault_source_sha,
        account_loginid=args.account_loginid.strip(),
        kill_switch_generation=generation,
    )
    output = Path(args.output)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if output.exists() or output.is_symlink():
        raise SystemExit("A reset request already exists; inspect/consume it before issuing another")
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(output)
    os.chmod(output, 0o600)
    print(json.dumps({
        "status": "RESET_REQUEST_CREATED",
        "output": str(output),
        "operator_id": args.operator_id,
        "account_loginid": args.account_loginid,
        "source_sha": deployed_sha,
        "fault_source_sha": fault_source_sha,
        "kill_switch_generation": generation,
        "expires_at_utc": record["expires_at_utc"],
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
