#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from runtime.core.operator_reset import create_operator_reset_record


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a short-lived, signed AURELIA kill-switch reset request. This does not itself enable trading."
    )
    parser.add_argument("--account-loginid", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--operator-id", required=True)
    parser.add_argument(
        "--state-path",
        default=os.getenv("AURELIA_KILL_SWITCH_STATE_PATH", "/var/lib/aurelia/kill-switch-state.json"),
    )
    parser.add_argument(
        "--output",
        default=os.getenv("AURELIA_OPERATOR_RESET_PATH", "/run/aurelia/operator-kill-switch-reset.json"),
    )
    args = parser.parse_args()

    signing_key = os.getenv("AURELIA_OPERATOR_RESET_SIGNING_KEY", "").strip()
    if len(signing_key) < 32:
        raise SystemExit("AURELIA_OPERATOR_RESET_SIGNING_KEY must be configured in the operator's secure environment")
    state_path = Path(args.state_path)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Kill-switch state unavailable: {type(exc).__name__}") from None
    if not isinstance(state, dict) or state.get("schema") != "aurelia.kill_switch_state.v1":
        raise SystemExit("Kill-switch state schema invalid; reset denied")
    if state.get("state") != "TRIPPED":
        raise SystemExit("Kill switch is not in TRIPPED state; reset denied")
    persisted_source_sha = str(state.get("source_sha") or "").strip()
    if not persisted_source_sha or args.source_sha != persisted_source_sha:
        raise SystemExit("Source revision does not match the persisted kill-switch event; reset denied")
    generation = state.get("generation")
    reason = state.get("reason")
    record = create_operator_reset_record(
        signing_key=signing_key,
        operator_id=args.operator_id,
        reason=str(reason or ""),
        source_sha=args.source_sha,
        account_loginid=args.account_loginid,
        kill_switch_generation=generation,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.is_symlink():
        raise SystemExit("A reset request already exists; inspect/consume it before issuing another")
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({
        "status": "RESET_REQUEST_CREATED",
        "output": str(output),
        "operator_id": args.operator_id,
        "account_loginid": args.account_loginid,
        "source_sha": args.source_sha,
        "kill_switch_generation": generation,
        "expires_at_utc": record["expires_at_utc"],
        "capital_authority_granted": False,
        "order_submission_permitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
