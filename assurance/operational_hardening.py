"""Execution-neutral operational hardening contracts."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Sequence

def canonical_state_hash(state: Mapping[str, Any]) -> str:
    payload = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def decision_replay_matches(original: Mapping[str, Any], replay: Mapping[str, Any]) -> bool:
    return canonical_state_hash(original) == canonical_state_hash(replay)

def backup_restore_reconciled(
    broker_balance: float | None,
    ledger_balance: float | None,
    broker_transaction_ids: Sequence[str],
    ledger_transaction_ids: Sequence[str],
) -> bool:
    if broker_balance is None or ledger_balance is None:
        return False
    if not all(isfinite(v) for v in (broker_balance, ledger_balance)):
        return False
    return broker_balance == ledger_balance and set(broker_transaction_ids) == set(ledger_transaction_ids)

@dataclass(frozen=True)
class DeploymentEvidence:
    approved_commit: str
    build_hash: str
    artifact_hash: str
    deployment_id: str
    runtime_hash: str
    config_hash: str

def deployment_chain_complete(x: DeploymentEvidence) -> bool:
    return all(isinstance(v, str) and v.strip() for v in (
        x.approved_commit, x.build_hash, x.artifact_hash,
        x.deployment_id, x.runtime_hash, x.config_hash,
    ))

def deployment_matches_approval(x: DeploymentEvidence, *, expected_commit: str, expected_config_hash: str) -> bool:
    return (
        deployment_chain_complete(x)
        and x.approved_commit == expected_commit
        and x.config_hash == expected_config_hash
        and x.runtime_hash == x.artifact_hash
    )

def invariants_hold(violations: Sequence[str]) -> bool:
    return len(violations) == 0

def no_silent_degradation(*, subsystem_states: Mapping[str, str]) -> bool:
    healthy = {"HEALTHY", "AVAILABLE", "VALID", "PROVEN", "MATCHED", "CURRENT", "WITHIN_LIMIT", "EQUIVALENT"}
    return bool(subsystem_states) and all(state in healthy for state in subsystem_states.values())

def canary_stops_on_unknown_or_mismatch(*, broker_unknown: bool, reconciliation_mismatch: bool, config_mismatch: bool) -> bool:
    return broker_unknown or reconciliation_mismatch or config_mismatch
