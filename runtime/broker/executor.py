from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from runtime.core.authority import GateResult, authorization_gate, build_intent
from runtime.core.events import event_envelope
from runtime.core.fencing import ExecutionFence
from runtime.core.invariants import check_pre_submission_invariants
from runtime.core.idempotency import IdempotencyStore
from runtime.core.journal import AppendOnlyJournal
from runtime.core.ledger import InMemoryLedger
from runtime.core.models import (
    AuthorizationContext,
    BrokerOutcome,
    CapitalSnapshot,
    Decision,
    LedgerEvent,
    OrderIntent,
    RuntimeState,
    AuthorizationContext,
    utc_now,
)
from runtime.core.reconcile import Reconciler, ReconciliationResult
from runtime.core.release_gate import read_live_release
from runtime.core.state import RuntimeStateMachine


@dataclass
class ExecutionOutcome:
    allowed: bool
    status: str
    reasons: tuple[str, ...]
    intent_id: str | None = None
    broker_transaction_id: str | None = None


class CapitalPlaneExecutor:
    '''Single capital-moving orchestration point.

    A strategy or AI agent may propose a Decision. This class applies the
    existing deterministic control chain and is the only caller allowed to
    invoke the broker submission adapter. The repository's LIVE_LOCK remains
    authoritative; parameters cannot override it.
    '''

    def __init__(
        self,
        broker,
        *,
        journal: AppendOnlyJournal,
        ledger: InMemoryLedger,
        idempotency: IdempotencyStore,
        fence: ExecutionFence,
        state: RuntimeStateMachine,
        reconciler: Reconciler,
        source_hash: str,
        config_hash: str,
        live_lock_path: Path | str = "config/LIVE_LOCK.yaml",
    ):
        self.broker = broker
        self.journal = journal
        self.ledger = ledger
        self.idempotency = idempotency
        self.fence = fence
        self.state = state
        self.reconciler = reconciler
        self.source_hash = source_hash
        self.config_hash = config_hash
        self.live_lock_path = Path(live_lock_path)
        self.kill_switch = True
        self._kill_switch_activated_at = utc_now()
        self._execution_lock = asyncio.Lock()

    def _log(self, event_type: str, payload: dict) -> None:
        event_id = f"{event_type}:{len(self.journal.read_all()) + 1}"
        self.journal.append(
            event_envelope(
                event_type=event_type,
                event_id=event_id,
                correlation_id=payload.get("intent_id")
                or payload.get("decision_id")
                or event_type,
                payload=payload,
                source_hash=self.source_hash,
                config_hash=self.config_hash,
            )
        )

    def activate_kill_switch(self, reason: str) -> None:
        self.kill_switch = True
        self._kill_switch_activated_at = utc_now()
        self.fence.revoke()
        if self.state.state not in {RuntimeState.CAPITAL_PROTECTED, RuntimeState.SHUTDOWN}:
            try:
                self.state.transition(RuntimeState.CAPITAL_PROTECTED)
            except ValueError:
                pass
        self._log("KILL_SWITCH_ACTIVATED", {"reason": reason})

    def clear_kill_switch_with_fresh_authorization(
        self,
        authorization: AuthorizationContext | bool,
    ) -> bool:
        """Clear only with a fresh, currently valid full authorization issued after the kill."""
        if not isinstance(authorization, AuthorizationContext):
            self._log(
                "KILL_SWITCH_CLEAR_BLOCKED",
                {"reason": "FRESH_AUTHORIZATION_OBJECT_REQUIRED"},
            )
            return False
        if not self.kill_switch:
            return False
        if not self.release_allows_live():
            self._log(
                "KILL_SWITCH_CLEAR_BLOCKED",
                {"reason": "LIVE_RELEASE_NOT_ENABLED"},
            )
            return False
        if not authorization.final_execution_authorization or not authorization.is_current():
            self._log(
                "KILL_SWITCH_CLEAR_BLOCKED",
                {"reason": "AUTHORIZATION_INVALID_OR_EXPIRED"},
            )
            return False
        if not all(
            (
                authorization.account.account_type == "real",
                authorization.capital.is_valid(),
                authorization.risk_approved,
                authorization.firewall_approved,
                authorization.reconciliation_healthy,
            )
        ):
            self._log(
                "KILL_SWITCH_CLEAR_BLOCKED",
                {"reason": "AUTHORIZATION_CONTROL_CHAIN_INCOMPLETE"},
            )
            return False
        if self._kill_switch_activated_at is None:
            self._log(
                "KILL_SWITCH_CLEAR_BLOCKED",
                {"reason": "KILL_SWITCH_ACTIVATION_TIME_UNKNOWN"},
            )
            return False
        if authorization.authorization_issued_at <= self._kill_switch_activated_at:
            self._log(
                "KILL_SWITCH_CLEAR_BLOCKED",
                {"reason": "AUTHORIZATION_PREDATES_KILL_SWITCH"},
            )
            return False

        self.kill_switch = False
        self._log(
            "KILL_SWITCH_CLEARED",
            {"authorization_id": authorization.authorization_id},
        )
        return True

    def release_allows_live(self) -> bool:
        return read_live_release(self.live_lock_path).may_move_capital

    async def prepare_proposal(self, parameters: dict) -> str:
        request_proposal = getattr(self.broker, "request_proposal", None)
        if request_proposal is None:
            raise RuntimeError("BROKER_PROPOSAL_INTERFACE_MISSING")
        proposal_id = await request_proposal(parameters)
        if not proposal_id:
            raise RuntimeError("PROPOSAL_ID_MISSING_FROM_BROKER")
        return proposal_id

    async def authorize_and_build_intent(
        self,
        *,
        decision: Decision,
        capital: CapitalSnapshot,
        runtime_config_hash: str,
        account,
        risk_approved: bool,
        firewall_approved: bool,
        reconciliation_healthy: bool,
        final_execution_authorization: bool,
        live_trading_enabled: bool,
        proposal_id: str | None = None,
        mode: str = "LIVE",
    ) -> tuple[GateResult, AuthorizationContext | None, OrderIntent | None]:
        release = read_live_release(self.live_lock_path)
        if mode == "LIVE" and not release.may_move_capital:
            gate = GateResult(
                False,
                (
                    "LIVE_LOCK_OR_FINAL_AUTHORIZATION_DISABLED",
                    "CAPITAL_PLANE_VERIFY_ONLY",
                ),
            )
            self._log(
                "AUTHORIZATION_DECISION",
                {
                    "decision_id": decision.decision_id,
                    "allowed": False,
                    "reasons": gate.reason_codes,
                },
            )
            return gate, None, None

        gate, ctx = authorization_gate(
            decision=decision,
            account=account,
            capital=capital,
            config_hash=self.config_hash,
            runtime_config_hash=runtime_config_hash,
            kill_switch_off=not self.kill_switch,
            risk_approved=risk_approved,
            firewall_approved=firewall_approved,
            reconciliation_healthy=reconciliation_healthy,
            final_execution_authorization=final_execution_authorization,
            live_trading_enabled=live_trading_enabled,
        )
        self._log(
            "AUTHORIZATION_DECISION",
            {
                "decision_id": decision.decision_id,
                "allowed": gate.allowed,
                "reasons": gate.reason_codes,
            },
        )
        if not gate.allowed or ctx is None:
            return gate, None, None
        return gate, ctx, build_intent(ctx, proposal_id=proposal_id, mode=mode)

    async def execute(
        self,
        intent: OrderIntent,
        context: AuthorizationContext,
        fence_token,
    ) -> ExecutionOutcome:
        async with self._execution_lock:
            return await self._execute_serialized(intent, context, fence_token)

    async def _execute_serialized(
        self,
        intent: OrderIntent,
        context: AuthorizationContext,
        fence_token,
    ) -> ExecutionOutcome:
        if intent.execution_mode != "LIVE":
            self._log(
                "PRE_SUBMISSION_BLOCKED",
                {
                    "intent_id": intent.intent_id,
                    "reasons": ("NON_LIVE_BROKER_SUBMISSION_FORBIDDEN",),
                },
            )
            return ExecutionOutcome(
                False,
                "BLOCKED",
                ("NON_LIVE_BROKER_SUBMISSION_FORBIDDEN",),
                intent.intent_id,
            )

        if not self.release_allows_live():
            self._log(
                "PRE_SUBMISSION_BLOCKED",
                {"intent_id": intent.intent_id, "reasons": ("LIVE_LOCK_ACTIVE",)},
            )
            return ExecutionOutcome(False, "BLOCKED", ("LIVE_LOCK_ACTIVE",), intent.intent_id)

        violations = check_pre_submission_invariants(
            context=context,
            intent=intent,
            kill_switch_off=not self.kill_switch,
            broker_state_unknown=False,
            single_writer_token_valid=self.fence.valid(fence_token),
        )
        if violations:
            reasons = tuple(v.code for v in violations)
            self._log(
                "PRE_SUBMISSION_BLOCKED",
                {"intent_id": intent.intent_id, "reasons": reasons},
            )
            return ExecutionOutcome(False, "BLOCKED", reasons, intent.intent_id)

        existing = self.idempotency.register_intent(intent.intent_id)
        if existing.broker_transaction_id:
            return ExecutionOutcome(
                True,
                "ALREADY_ACCEPTED",
                (),
                intent.intent_id,
                existing.broker_transaction_id,
            )

        self._log(
            "INTENT_CREATED",
            {
                "intent_id": intent.intent_id,
                "decision_id": intent.decision_id,
                "stake": intent.stake,
                "proposal_id": intent.proposal_id,
            },
        )

        try:
            result = await self.broker.submit_authorized_order(
                {"proposal_id": intent.proposal_id, "stake": intent.stake}
            )
        except Exception as exc:
            try:
                self.state.transition(RuntimeState.RECOVERY)
            except ValueError:
                self.state = RuntimeStateMachine(RuntimeState.RECOVERY)
            self._log(
                "BROKER_SUBMISSION_EXCEPTION",
                {
                    "intent_id": intent.intent_id,
                    "error_class": type(exc).__name__,
                },
            )
            return ExecutionOutcome(
                False,
                "RECOVERY_REQUIRED",
                ("BROKER_SUBMISSION_EXCEPTION",),
                intent.intent_id,
            )

        if result.outcome == BrokerOutcome.UNKNOWN:
            try:
                self.state.transition(RuntimeState.RECOVERY)
            except ValueError:
                pass
            self._log("BROKER_OUTCOME_UNKNOWN", {"intent_id": intent.intent_id})
            return ExecutionOutcome(
                False,
                "RECOVERY_REQUIRED",
                ("BROKER_OUTCOME_UNKNOWN",),
                intent.intent_id,
            )

        if result.broker_transaction_id:
            self.idempotency.attach_broker_transaction(
                intent.intent_id, result.broker_transaction_id
            )

        if result.outcome == BrokerOutcome.ACCEPTED:
            self.idempotency.record_economic_effect(intent.intent_id)
            self.ledger.post(
                LedgerEvent(
                    event_id=f"broker:{result.broker_transaction_id or result.request_id}",
                    intent_id=intent.intent_id,
                    account=intent.account,
                    event_type="INTENT_RESERVED",
                    amount=intent.stake,
                    currency=intent.account.currency,
                    occurred_at=result.broker_timestamp or intent.created_at,
                    broker_transaction_id=result.broker_transaction_id,
                )
            )
            self._log(
                "BROKER_ACCEPTED",
                {
                    "intent_id": intent.intent_id,
                    "broker_transaction_id": result.broker_transaction_id,
                    "contract_id": result.contract_id,
                },
            )
            return ExecutionOutcome(
                True,
                "ACCEPTED",
                (),
                intent.intent_id,
                result.broker_transaction_id,
            )

        return ExecutionOutcome(
            False,
            "REJECTED",
            ("BROKER_REJECTED",),
            intent.intent_id,
        )

    async def reconcile(
        self,
        *,
        broker_capital,
        prior_authoritative_balance,
        explainable_delta: float = 0.0,
    ) -> ReconciliationResult:
        result = self.reconciler.compare(
            broker=broker_capital,
            prior_authoritative_balance=prior_authoritative_balance,
            explainable_delta=explainable_delta,
        )
        self._log(
            "RECONCILIATION",
            {
                "healthy": result.healthy,
                "difference": result.difference,
                "reason": result.reason,
            },
        )
        if not result.healthy and self.state.state != RuntimeState.CAPITAL_PROTECTED:
            try:
                self.state.transition(RuntimeState.CAPITAL_PROTECTED)
            except ValueError:
                pass
        return result
