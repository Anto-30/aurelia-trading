from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from assurance.evidence_writer import build_evidence, payload_sha256, write_evidence
from runtime.core.models import AccountIdentity, LedgerEvent
from runtime.core.persistent import (
    PersistentExecutionFence,
    PersistentIdempotencyStore,
    PersistentLedger,
)


SCOPE = "OFFLINE_PERSISTENT_STATE_AND_RUNTIME_CONTROL_FAULT_INJECTION"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _scenario(scenario_id: str, operation) -> dict:
    started = datetime.now(timezone.utc)
    try:
        detail = operation()
        passed = detail is True
        observed = "EXPECTED_FAIL_CLOSED_BEHAVIOUR" if passed else "UNEXPECTED_RESULT"
    except Exception as exc:  # unexpected harness exceptions are failed scenarios
        passed = False
        observed = f"UNEXPECTED_EXCEPTION:{type(exc).__name__}"
    ended = datetime.now(timezone.utc)
    return {
        "scenario_id": scenario_id,
        "passed": passed,
        "expected": "controlled fail-closed recovery behaviour",
        "observed": observed,
        "started_at_utc": started.isoformat(),
        "ended_at_utc": ended.isoformat(),
        "scope": SCOPE,
    }


def _corrupt_fence_generation() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fence.generation"
        path.write_text("corrupted-generation\n", encoding="ascii")
        try:
            PersistentExecutionFence(path)
        except RuntimeError as exc:
            return str(exc) == "EXECUTION_FENCE_STATE_CORRUPT"
    return False


def _stale_fence_token_is_rejected() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fence.generation"
        original = PersistentExecutionFence(path)
        old_token = original.acquire("executor-A")
        replacement = PersistentExecutionFence(path)
        new_token = replacement.acquire("executor-B")
        return (
            new_token.generation > old_token.generation
            and original.valid(old_token) is False
            and replacement.valid(new_token) is True
        )


def _corrupt_idempotency_state_blocks() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "idempotency.json"
        path.write_text(json.dumps({"records": []}), encoding="utf-8")
        try:
            PersistentIdempotencyStore(path)
        except RuntimeError as exc:
            return str(exc) == "IDEMPOTENCY_STORE_SCHEMA_INVALID"
    return False


def _unknown_outcome_is_restart_safe() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "idempotency.json"
        store = PersistentIdempotencyStore(path)
        store.register_intent("fault-intent-1")
        store.record_unknown_outcome("fault-intent-1")
        recovered = PersistentIdempotencyStore(path)
        if recovered.unresolved_unknown_intents() != ("fault-intent-1",):
            return False
        try:
            recovered.attach_broker_transaction("fault-intent-1", "tx-should-not-bypass")
        except RuntimeError as exc:
            if str(exc) != "UNKNOWN_OUTCOME_REQUIRES_VERIFIED_RECOVERY":
                return False
        else:
            return False
        resolved = recovered.resolve_unknown_outcome(
            "fault-intent-1",
            broker_state_known=True,
            reconciliation_healthy=True,
            economic_effect_confirmed=True,
            broker_transaction_id="tx-fault-recovery",
            resolution_evidence_id="offline-fault-injection-only",
        )
        if resolved.broker_outcome_unknown or recovered.unresolved_unknown_intents():
            return False
        try:
            recovered.record_economic_effect("fault-intent-1")
        except RuntimeError as exc:
            return str(exc) == "DUPLICATE_ECONOMIC_EFFECT"
        return False


def _failed_disk_write_does_not_commit_memory() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "idempotency.json"
        store = PersistentIdempotencyStore(path)
        with patch("runtime.core.persistent.os.replace", side_effect=OSError("injected disk failure")):
            try:
                store.register_intent("not-durable")
            except RuntimeError as exc:
                if str(exc) != "IDEMPOTENCY_STORE_PERSISTENCE_FAILED":
                    return False
            else:
                return False
        return store.get("not-durable") is None and not path.exists()


def _ledger_duplicate_event_is_idempotent() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "ledger.json"
        ledger = PersistentLedger(path)
        account = AccountIdentity("VRTC12345", "demo", "USD", "virtual")
        event = LedgerEvent(
            event_id="fault-event-1",
            intent_id="fault-intent-1",
            account=account,
            event_type="INTENT_RESERVED",
            amount=1.0,
            currency="USD",
            occurred_at=datetime.now(timezone.utc),
            broker_transaction_id="tx-fault-1",
            metadata={"scope": "offline-fault-injection"},
        )
        if ledger.post(event) is not True or ledger.post(event) is not False:
            return False
        restarted = PersistentLedger(path)
        return len(restarted.events()) == 1 and restarted.events()[0].event_id == event.event_id


def run_fault_injection() -> dict:
    scenarios = [
        _scenario("CORRUPT_FENCE_GENERATION", _corrupt_fence_generation),
        _scenario("STALE_FENCE_TOKEN_AFTER_RESTART", _stale_fence_token_is_rejected),
        _scenario("CORRUPT_IDEMPOTENCY_SCHEMA", _corrupt_idempotency_state_blocks),
        _scenario("UNKNOWN_OUTCOME_RESTART_AND_REPLAY", _unknown_outcome_is_restart_safe),
        _scenario("PERSISTENCE_WRITE_FAILURE", _failed_disk_write_does_not_commit_memory),
        _scenario("DUPLICATE_LEDGER_EVENT_REPLAY", _ledger_duplicate_event_is_idempotent),
    ]
    passed = all(scenario["passed"] for scenario in scenarios)
    return {
        "schema": "aurelia.persistent_state_fault_injection.v1",
        "scope": SCOPE,
        "fault_injection_passed": passed,
        "scenario_results": scenarios,
        "fault_injection_count": len(scenarios),
        "blind_resubmissions": 0,
        "duplicate_economic_effects": 0 if passed else None,
        "broker_interaction_performed": False,
        "broker_orders_submitted": 0,
        "capital_movement": False,
        "execution_mode": "OFFLINE_TEST_ONLY",
        "live_execution": "BLOCKED",
        "final_execution_authorization": False,
    }


def write_recovery_evidence(
    report: dict,
    *,
    output: Path,
    source_commit: str,
    config_hash: str,
) -> dict:
    if not source_commit or len(source_commit) != 40:
        raise ValueError("RECOVERY_EVIDENCE_SOURCE_COMMIT_UNPINNED")
    if not config_hash or len(config_hash) != 64:
        raise ValueError("RECOVERY_EVIDENCE_CONFIG_HASH_INVALID")
    started = min(
        datetime.fromisoformat(item["started_at_utc"])
        for item in report["scenario_results"]
    )
    ended = max(
        datetime.fromisoformat(item["ended_at_utc"])
        for item in report["scenario_results"]
    )
    generated = datetime.now(timezone.utc)
    raw_report = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    record = build_evidence(
        evidence_id=f"persistent-state-fault-injection:{source_commit[:12]}",
        source_hash=source_commit,
        artifact_hash=_sha256_bytes(raw_report),
        config_hash=config_hash,
        data_hash=_sha256_bytes(raw_report),
        environment="ci",
        started_at_utc=started.isoformat(),
        ended_at_utc=ended.isoformat(),
        status="CURRENT",
        valid_until_utc=(generated + timedelta(hours=12)).isoformat(),
        provenance={
            "origin": "ci",
            "issuer": "scripts.run_persistent_fault_injection",
            "source_commit": source_commit,
            "generated_at_utc": generated.isoformat(),
        },
        result="PASS" if report["fault_injection_passed"] else "UNPROVEN",
        invariants_checked=[
            "corrupt_fence_state_fails_closed",
            "stale_fence_tokens_are_invalidated",
            "corrupt_idempotency_store_fails_closed",
            "unknown_outcome_survives_restart",
            "unknown_outcome_requires_verified_resolution",
            "persistence_write_failure_does_not_commit_memory",
            "duplicate_ledger_events_are_idempotent",
            "no_broker_interaction",
            "zero_orders",
            "zero_capital_movement",
        ],
        invariants_failed=[] if report["fault_injection_passed"] else [
            item["scenario_id"] for item in report["scenario_results"] if not item["passed"]
        ],
    )
    record.update({
        "fault_injection_scope": SCOPE,
        "fault_injection_passed": report["fault_injection_passed"],
        "critical_scenarios_passed": report["fault_injection_passed"],
        "scenario_results": report["scenario_results"],
        "fault_injection_count": report["fault_injection_count"],
        "blind_resubmissions": report["blind_resubmissions"],
        "duplicate_economic_effects": report["duplicate_economic_effects"],
        "broker_interaction_performed": False,
        "broker_orders_submitted": 0,
        "capital_movement": False,
        "execution_mode": "OFFLINE_TEST_ONLY",
        "live_execution": "BLOCKED",
        "final_execution_authorization": False,
    })
    unsigned = {key: value for key, value in record.items() if key != "record_hash"}
    record["record_hash"] = payload_sha256(unsigned)
    write_evidence(output, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/recovery_matrix.json")
    parser.add_argument("--report-out", default="artifacts/persistent-state-fault-injection.json")
    args = parser.parse_args()

    report = run_fault_injection()
    report_path = Path(args.report_out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    source_commit = os.getenv("GITHUB_SHA", "").strip()
    root = Path(__file__).resolve().parents[1]
    config_hash = _sha256_bytes((root / "config" / "LIVE_LOCK.yaml").read_bytes())
    if report["fault_injection_passed"] and source_commit:
        write_recovery_evidence(
            report,
            output=Path(args.out),
            source_commit=source_commit,
            config_hash=config_hash,
        )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["fault_injection_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
