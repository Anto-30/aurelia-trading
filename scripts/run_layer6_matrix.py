"""Run five mandatory Layer 6 cases and emit tamper-evident sandbox evidence.

This is not cryptographically signed, immutable storage or live-execution
authorization. Use a unique destination path; the script refuses to overwrite.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.core.layer6_risk_gate import Layer6RiskGate, RiskPolicy, RiskRequest


def canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _request(**overrides) -> RiskRequest:
    values = {
        "symbol": "R_100",
        "direction": "CALL",
        "stake": 1.0,
        "available_balance": 100.0,
        "daily_pnl": 0.0,
        "worst_case_loss": 1.0,
        "existing_exposure": 0.0,
        "pending_exposure": 0.0,
        "concurrent_exposure": 0.0,
        "correlated_exposure": 0.0,
        "account_verified": True,
        "state_verified": True,
        "kill_switch_active": False,
    }
    values.update(overrides)
    return RiskRequest(**values)


def run_matrix(timeout_ms: int = 50) -> list[dict]:
    risk_policy = RiskPolicy(
        max_daily_loss=5.0,
        max_position_size=2.0,
        max_total_exposure=5.0,
        timeout_ms=timeout_ms,
    )
    gate = Layer6RiskGate(risk_policy, enabled=True)

    class BrokenGate(Layer6RiskGate):
        def _evaluate_checks(self, candidate):
            raise RuntimeError("simulated failure injection")

    class SlowGate(Layer6RiskGate):
        def _evaluate_checks(self, candidate):
            time.sleep(0.1)
            return super()._evaluate_checks(candidate)

    cases = [
        ("HAPPY_PATH", gate, _request(), "RISK_PASS"),
        ("POSITION_BREACH", gate, _request(stake=2.01), "REJECT"),
        ("DAILY_LOSS_LIMIT_BREACH", gate, _request(daily_pnl=-4.5, worst_case_loss=0.5), "REJECT"),
        ("EXCEPTION_FAIL_CLOSED", BrokenGate(risk_policy, enabled=True), _request(), "REJECT"),
        ("TIMEOUT_FAIL_CLOSED", SlowGate(risk_policy, enabled=True), _request(), "REJECT"),
    ]
    results = []
    for name, evaluator, request, expected in cases:
        started = time.perf_counter()
        verdict = evaluator.evaluate(request)
        measured_ms = (time.perf_counter() - started) * 1000.0
        actual = "RISK_PASS" if verdict.risk_approved else "REJECT"
        passed = actual == expected
        results.append({
            "test_case": name,
            "expected_outcome": expected,
            "actual_outcome": actual,
            "status": "PASS" if passed else "FAIL",
            "reason": verdict.reason,
            "latency_ms": round(measured_ms, 3),
            "gate_latency_ms": verdict.latency_ms,
        })
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Unique output path; existing files are never overwritten")
    parser.add_argument("--source-commit", default=os.getenv("GITHUB_SHA", "UNRESOLVED_LOCAL_WORKTREE"))
    parser.add_argument("--timeout-ms", type=int, default=50)
    args = parser.parse_args()

    output = Path(args.out).expanduser().resolve()
    if output.exists():
        raise SystemExit("EVIDENCE_OUTPUT_ALREADY_EXISTS_REFUSING_OVERWRITE")
    gate_path = ROOT / "runtime/core/layer6_risk_gate.py"
    lock_path = ROOT / "config/LIVE_LOCK.yaml"
    gate_hash = sha256_bytes(gate_path.read_bytes())
    lock_hash = sha256_bytes(lock_path.read_bytes()) if lock_path.exists() else "UNAVAILABLE"
    dataset = {
        "matrix": "LAYER6_REQUIRED_FIVE_CASES_V1",
        "timeout_ms": args.timeout_ms,
        "test_inputs": "synthetic_only_no_broker_data",
    }
    data_hash = sha256_bytes(canonical_json(dataset).encode("utf-8"))
    started_at = utc_now()
    results = run_matrix(args.timeout_ms)
    ended_at = utc_now()
    aggregate = "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL"
    record = {
        "evidence_id": str(uuid.uuid4()),
        "gate_name": "LAYER_6_RISK_GATE",
        "timestamp_utc": ended_at,
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "system_state": "CANONICAL_AURELIA_VERIFY_ONLY",
        "test_environment": "ISOLATED_SANDBOX",
        "source_commit": args.source_commit,
        "artifact_hash": gate_hash,
        "config_hash": lock_hash,
        "data_hash": data_hash,
        "results": results,
        "aggregate_status": aggregate,
        "gate_passed": aggregate == "PASS",
        "authorization_granted": False,
        "final_execution_authorization": False,
        "live_execution": "BLOCKED",
        "signed_by_agent": "NONE_NOT_CRYPTOGRAPHICALLY_SIGNED",
        "signature_status": "NOT_SIGNED",
        "evidence_class": "SANDBOX_TEST_ONLY_NOT_RELEASE_CERTIFICATION",
    }
    record["hash"] = sha256_bytes(canonical_json(record).encode("utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
    except FileExistsError:
        raise SystemExit("EVIDENCE_OUTPUT_ALREADY_EXISTS_REFUSING_OVERWRITE")
    print(json.dumps({
        "output": str(output),
        "aggregate_status": aggregate,
        "authorization_granted": False,
        "record_hash": record["hash"],
        "results": results,
    }, indent=2))
    return 0 if aggregate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
