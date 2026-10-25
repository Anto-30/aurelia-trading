#!/usr/bin/env python3
"""Create a privacy-minimised attestation from private, runner-local evidence files.

Raw evidence can contain account identifiers, balances and transaction identifiers.
Only hashes and allowlisted control outcomes are emitted to the downloadable artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40,64}$")
_ALLOWED_SESSION = {
    "exact_real_account_binding",
    "authenticated_websocket_environment",
    "auth_mode_pat",
    "auth_mode_oauth",
    "account_identity_match",
    "currency_match",
    "fresh_balance_snapshot",
    "no_order_submission",
    "capital_authority_not_granted",
}
_ALLOWED_BROKER = {
    "real_account_binding",
    "fresh_authenticated_balance",
    "authenticated_statement_read",
    "buy_transaction_inventory",
    "authenticated_portfolio_read",
    "no_order_submission",
    "no_capital_authority_grant",
    "broker_account_level_attribution_only",
}


class AttestationError(ValueError):
    """Raised when private evidence cannot be safely attested."""


def build_attestation(
    raw_path: Path,
    *,
    evidence_type: str,
    source_commit: str,
    workflow_run_id: str,
    workflow_run_attempt: str,
) -> dict[str, Any]:
    raw = raw_path.read_bytes()
    try:
        record = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttestationError("INVALID_EVIDENCE_JSON") from exc
    if not isinstance(record, dict):
        raise AttestationError("INVALID_EVIDENCE_SHAPE")

    if not _COMMIT.fullmatch(source_commit):
        raise AttestationError("INVALID_WORKFLOW_SOURCE_COMMIT")
    if record.get("source_hash") != source_commit:
        raise AttestationError("EVIDENCE_SOURCE_COMMIT_MISMATCH")

    record_hash = record.get("record_hash")
    if not isinstance(record_hash, str) or not _SHA256.fullmatch(record_hash):
        raise AttestationError("INVALID_EVIDENCE_RECORD_HASH")
    if record.get("result") != "PROVEN" or record.get("status") != "CURRENT":
        raise AttestationError("EVIDENCE_NOT_CURRENT_AND_PROVEN")
    if record.get("environment") != "real":
        raise AttestationError("UNEXPECTED_EVIDENCE_ENVIRONMENT")
    if type(record.get("orders_submitted")) is not int or record["orders_submitted"] != 0:
        raise AttestationError("ORDER_SUBMISSION_INVARIANT_FAILED")
    if record.get("capital_authority_granted") is not False:
        raise AttestationError("CAPITAL_AUTHORITY_INVARIANT_FAILED")
    if record.get("order_submission_permitted") is not False:
        raise AttestationError("ORDER_PERMISSION_INVARIANT_FAILED")

    scope = record.get("verification_scope")
    expected_scope = {
        "session": "AUTHENTICATED_DERIV_REAL_SESSION",
        "broker": "REAL_DERIV_BROKER_ACCOUNT_READ_ONLY",
    }.get(evidence_type)
    if expected_scope is None or scope != expected_scope:
        raise AttestationError("UNEXPECTED_VERIFICATION_SCOPE")

    expected_invariants = _ALLOWED_SESSION if evidence_type == "session" else _ALLOWED_BROKER
    observed_invariants = record.get("invariants_checked")
    if (
        not isinstance(observed_invariants, list)
        or not all(isinstance(item, str) for item in observed_invariants)
        or not set(observed_invariants).issubset(expected_invariants)
        or not expected_invariants.intersection(observed_invariants)
    ):
        raise AttestationError("UNEXPECTED_INVARIANT_LIST")
    failed = record.get("invariants_failed")
    if not isinstance(failed, list) or failed:
        raise AttestationError("FAILED_EVIDENCE_INVARIANTS")

    evidence_id = record.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id.startswith("DERIV_"):
        raise AttestationError("INVALID_EVIDENCE_ID")

    # Explicit allowlist only. In particular, do not copy record['observed'].
    return {
        "evidence_type": (
            "AUTHENTICATED_DERIV_SESSION_READ_ONLY"
            if evidence_type == "session"
            else "DERIV_BROKER_ACCOUNT_READ_ONLY"
        ),
        "evidence_id": evidence_id,
        "raw_evidence_sha256": hashlib.sha256(raw).hexdigest(),
        "record_hash": record_hash,
        "source_commit": source_commit,
        "workflow_run_id": workflow_run_id,
        "workflow_run_attempt": workflow_run_attempt,
        "generated_at_utc": record.get("ended_at_utc"),
        "status": record.get("status"),
        "result": record.get("result"),
        "environment": record.get("environment"),
        "verification_scope": scope,
        "invariants_checked": sorted(set(observed_invariants)),
        "invariants_failed": [],
        "orders_submitted": 0,
        "capital_authority_granted": False,
        "order_submission_permitted": False,
        "raw_account_fields_persisted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--broker", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source_commit = os.getenv("GITHUB_SHA", "").strip()
    run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "").strip()
    if not source_commit or not run_id or not run_attempt:
        print("READ_ONLY_ATTESTATION=FAILED")
        print("READ_ONLY_ATTESTATION_REASON=WORKFLOW_PROVENANCE_MISSING")
        return 2

    entries: list[dict[str, Any]] = []
    for kind, path in (("session", args.session), ("broker", args.broker)):
        if not path.is_file():
            print(f"READ_ONLY_ATTESTATION_SOURCE_MISSING={kind.upper()}")
            print("READ_ONLY_ATTESTATION=FAILED")
            return 2
        try:
            entries.append(
                build_attestation(
                    path,
                    evidence_type=kind,
                    source_commit=source_commit,
                    workflow_run_id=run_id,
                    workflow_run_attempt=run_attempt,
                )
            )
        except (OSError, AttestationError) as exc:
            print("READ_ONLY_ATTESTATION=FAILED")
            print(f"READ_ONLY_ATTESTATION_REASON={str(exc) if isinstance(exc, AttestationError) else 'EVIDENCE_FILE_READ_FAILED'}")
            return 2

    attestation = {
        "schema": "aurelia.deriv.read_only_attestation.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "workflow_run_id": run_id,
        "workflow_run_attempt": run_attempt,
        "execution_boundary": {
            "live_execution": "BLOCKED",
            "final_execution_authorization": False,
            "capital_plane_mode": "VERIFY_ONLY",
            "orders_submitted": 0,
            "capital_authority_granted": False,
        },
        "attestations": entries,
        "privacy": {
            "raw_evidence_in_artifact": False,
            "account_identifiers_in_artifact": False,
            "financial_amounts_in_artifact": False,
            "transaction_identifiers_in_artifact": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(attestation, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print("READ_ONLY_ATTESTATION=CREATED")
    print(f"READ_ONLY_ATTESTATION_PATH={args.output}")
    print("READ_ONLY_ATTESTATION_CONTENT=ALLOWLISTED_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
