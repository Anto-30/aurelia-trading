from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.broker.executor import CapitalPlaneExecutor
from runtime.core.authority import build_intent
from runtime.core.fencing import ExecutionFence
from runtime.core.idempotency import IdempotencyStore
from runtime.core.ledger import InMemoryLedger
from runtime.core.models import (
    AccountIdentity,
    AuthorizationContext,
    BrokerOutcome,
    BrokerResult,
    CapitalSnapshot,
    Decision,
)
from runtime.core.reconcile import ReconciliationResult
from runtime.core.reconcile import Reconciler
from runtime.core.state import RuntimeStateMachine

UTC = timezone.utc


def _account():
    return AccountIdentity("CRSOAK", "real", "USD", "real")


def _capital():
    return CapitalSnapshot(
        balance=10.0,
        currency="USD",
        available_balance=10.0,
        captured_at=datetime.now(UTC),
        source="deterministic-soak",
        account=_account(),
    )


def _context(issued_at=None, expired=False, sequence=0):
    now = datetime.now(UTC)
    issued = issued_at or (now - timedelta(seconds=1))
    expires = (now - timedelta(seconds=1)) if expired else (now + timedelta(seconds=30))
    return AuthorizationContext(
        decision=Decision(
            decision_id=f"SOAK-DECISION-{sequence}",
            strategy_id="SOAK",
            strategy_version="1",
            strategy_hash="strategy-hash",
            symbol="1",
            direction="CALL",
            probability=0.60,
            decision_time=now,
            market_snapshot_hash="market-hash",
            risk_requested_stake=1.0,
        ),
        account=_account(),
        capital=_capital(),
        config_hash="config-hash",
        authorization_id=f"SOAK-AUTH-{issued.timestamp()}",
        authorization_issued_at=issued,
        authorization_expires_at=expires,
        kill_switch_off=True,
        risk_approved=True,
        firewall_approved=True,
        reconciliation_healthy=True,
        final_execution_authorization=True,
    )


class DeterministicBroker:
    def __init__(self):
        self.calls = 0
        self.economic_effects = 0

    async def submit_authorized_order(self, payload):
        self.calls += 1
        proposal_id = str(payload["proposal_id"])
        try:
            cycle = int(proposal_id.rsplit("-", 1)[-1])
        except ValueError:
            cycle = -1
        await asyncio.sleep(0)
        if cycle > 0 and cycle % 29 == 0:
            return BrokerResult(BrokerOutcome.UNKNOWN, f"UNKNOWN-{cycle}", raw_class="SOAK_UNKNOWN")
        if cycle > 0 and cycle % 37 == 0:
            raise TimeoutError("SOAK_TIMEOUT")
        if cycle > 0 and cycle % 41 == 0:
            return BrokerResult(BrokerOutcome.REJECTED, f"REJECTED-{cycle}", raw_class="SOAK_REJECTED")
        self.economic_effects += 1
        return BrokerResult(
            BrokerOutcome.ACCEPTED,
            f"ACCEPTED-{cycle}",
            broker_transaction_id=f"TX-{proposal_id}",
            contract_id=f"C-{proposal_id}",
            raw_class="SOAK_ACCEPTED",
            broker_timestamp=datetime.now(UTC),
        )


def _executor(lock_path: Path, broker, root: Path, idempotency: IdempotencyStore, ledger: InMemoryLedger, fence):
    return CapitalPlaneExecutor(
        broker,
        journal=journal,
        ledger=ledger,
        idempotency=idempotency,
        fence=fence,
        state=RuntimeStateMachine(),
        reconciler=Reconciler(),
        source_hash="soak-source",
        config_hash="config-hash",
        live_lock_path=lock_path,
    )


async def run_control_path_soak(iterations: int = 3600) -> dict[str, int | bool]:
    """Deterministic non-live control-path soak using a local broker stub only.

    The executor stays in LIVE mode because the capital executor deliberately
    forbids alternate broker-submission modes. No network or real capital is used.
    Idempotency/ledger stores are in-memory here to keep 3,600 cycles fast; their
    persistence/reload semantics are covered by dedicated tests. Persistent fencing
    remains active across executor recreation. This proves repeated control-path
    invariants, not elapsed-time production SLOs.
    """
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        lock = root / "LIVE_LOCK.yaml"
        lock.write_text(
            "live_trading_enabled: true\n"
            "FINAL_EXECUTION_AUTHORIZATION: true\n"
            "LIVE_EXECUTION: ENABLED\n"
            "capital_plane_mode: LIVE\n",
            encoding="utf-8",
        )
        broker = DeterministicBroker()
        idempotency = IdempotencyStore()
        ledger = InMemoryLedger()
        fence = ExecutionFence()
        executor = _executor(lock, broker, root, idempotency, ledger, fence)
        blocked = 0
        recovered = 0
        rejected = 0
        accepted = 0
        for second in range(iterations):
            if second and second % 211 == 0:
                executor = _executor(lock, broker, root, idempotency, ledger, fence)
                executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
                restart_auth = _context(sequence=second)
                if not executor.clear_kill_switch_with_fresh_authorization(restart_auth):
                    return {"passed": False, "reason": "RESTART_AUTH_FAILED"}

            if executor.kill_switch:
                executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
                auth = _context(sequence=second)
                if not executor.clear_kill_switch_with_fresh_authorization(auth):
                    return {"passed": False, "reason": "FRESH_AUTH_FAILED"}
            else:
                auth = _context(sequence=second)

            if second and second % 127 == 0:
                stale = _context(
                    issued_at=datetime.now(UTC) - timedelta(seconds=60),
                    expired=True,
                )
                stale_intent = build_intent(
                    _context(sequence=second, issued_at=datetime.now(UTC) - timedelta(seconds=1)),
                    proposal_id=f"P-ST-{second}",
                    mode="LIVE",
                )
                token = executor.fence.acquire(f"stale-{second}")
                before_calls = broker.calls
                result = await executor.execute(stale_intent, stale, token)
                blocked += int(not result.allowed)
                if result.allowed or broker.calls != before_calls:
                    return {"passed": False, "reason": "STALE_AUTH_ESCAPED"}

            if second and second % 149 == 0:
                executor.activate_kill_switch(f"SOAK_KILL_{second}")
                killed_intent = build_intent(auth, proposal_id=f"P-KILL-{second}", mode="LIVE")
                before_calls = broker.calls
                result = await executor.execute(killed_intent, auth, executor.fence.acquire(f"kill-{second}"))
                blocked += int(not result.allowed)
                if result.allowed or broker.calls != before_calls:
                    return {"passed": False, "reason": "KILL_SWITCH_ESCAPED"}
                executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
                auth = _context(sequence=second)
                if not executor.clear_kill_switch_with_fresh_authorization(auth):
                    return {"passed": False, "reason": "POST_KILL_AUTH_FAILED"}

            intent = build_intent(auth, proposal_id=f"P-{second}", mode="LIVE")
            token = executor.fence.acquire(f"owner-{second}")

            if second and second % 113 == 0:
                before_calls = broker.calls
                first, second_result = await asyncio.gather(
                    executor.execute(intent, auth, token),
                    executor.execute(intent, auth, token),
                )
                if first.allowed and second_result.allowed:
                    return {"passed": False, "reason": "CONCURRENT_DUPLICATE_EFFECT"}
                if broker.calls != before_calls + 1:
                    return {"passed": False, "reason": "CONCURRENT_SUBMISSION_COUNT"}
                accepted += int(first.status == "ACCEPTED") + int(second_result.status == "ACCEPTED")
                recovered += int(first.status == "RECOVERY_REQUIRED") + int(second_result.status == "RECOVERY_REQUIRED")
                rejected += int(first.status == "REJECTED") + int(second_result.status == "REJECTED")
            else:
                before_calls = broker.calls
                result = await executor.execute(intent, auth, token)
                if broker.calls != before_calls + 1:
                    return {"passed": False, "reason": "SUBMISSION_COUNT_DRIFT"}
                accepted += int(result.status == "ACCEPTED")
                recovered += int(result.status == "RECOVERY_REQUIRED")
                rejected += int(result.status == "REJECTED")

            if second and second % 29 == 0:
                before_calls = broker.calls
                retry = await executor.execute(intent, auth, token)
                if retry.status != "RECOVERY_REQUIRED" or broker.calls != before_calls:
                    return {"passed": False, "reason": "UNKNOWN_RETRY_ESCAPED"}

            if second and second % 181 == 0:
                mismatch = _capital()
                mismatch = CapitalSnapshot(
                    balance=9.0,
                    currency=mismatch.currency,
                    available_balance=9.0,
                    captured_at=datetime.now(UTC),
                    source="soak-mismatch",
                    account=mismatch.account,
                )
                reconciliation: ReconciliationResult = await executor.reconcile(
                    broker_capital=mismatch,
                    prior_authoritative_balance=10.0,
                )
                if reconciliation.healthy:
                    return {"passed": False, "reason": "RECONCILIATION_FAILURE_ACCEPTED"}

        total_effects = sum(r.economic_effect_count for r in idempotency._records.values())
        unknown_records = sum(1 for r in idempotency._records.values() if r.broker_outcome_unknown)
        passed = total_effects == broker.economic_effects and unknown_records >= 1
        return {
            "passed": passed,
            "iterations": iterations,
            "broker_calls": broker.calls,
            "economic_effects": broker.economic_effects,
            "idempotent_effects_recorded": total_effects,
            "unknown_records": unknown_records,
            "blocked": blocked,
            "recovered": recovered,
            "rejected": rejected,
            "accepted": accepted,
        }
