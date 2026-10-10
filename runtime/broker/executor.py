from __future__ import annotations

import asyncio
from time import perf_counter
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
    utc_now,
)
from runtime.core.reconcile import Reconciler, ReconciliationResult
from runtime.core.trade_certificate import TradeCertificate
from runtime.core.trade_counter import count_accepted_trades
from runtime.ops.latency import LatencyMetrics
from runtime.core.release_gate import read_live_release
from runtime.core.production_controls import CircuitBreaker
from runtime.core.state import RuntimeStateMachine


@dataclass
class ExecutionOutcome:
    allowed: bool
    status: str
    reasons: tuple[str, ...]
    intent_id: str | None = None
    broker_transaction_id: str | None = None
    contract_id: str | None = None


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
        daily_risk_guard=None,
        max_trade_risk_pct: float = 0.01,
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
        if not 0 < float(max_trade_risk_pct) <= 0.02:
            raise ValueError("MAX_TRADE_RISK_PCT_MUST_BE_IN_(0,0.02]")
        self.max_trade_risk_pct = float(max_trade_risk_pct)
        self.daily_risk_guard = daily_risk_guard
        self.kill_switch = True
        self._kill_switch_activated_at = utc_now()
        self._execution_lock = asyncio.Lock()
        self.latency = LatencyMetrics()
        self.circuit_breaker = CircuitBreaker()

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
        probability_calibrated: bool = False,
        probability_fresh: bool = False,
        probability_drift_ok: bool = False,
        market_data_validated: bool = False,
        exposure_approved: bool = False,
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
            probability_calibrated=probability_calibrated,
            probability_fresh=probability_fresh,
            probability_drift_ok=probability_drift_ok,
            market_data_validated=market_data_validated,
            exposure_approved=exposure_approved,
            execution_mode=mode,
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

    async def preflight_authorization(
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
        probability_calibrated: bool = False,
        probability_fresh: bool = False,
        probability_drift_ok: bool = False,
        market_data_validated: bool = False,
        exposure_approved: bool = False,
    ) -> tuple[GateResult, AuthorizationContext | None]:
        """Evaluate a fresh live control chain before clearing the startup kill switch."""
        release = read_live_release(self.live_lock_path)
        if not release.may_move_capital:
            return GateResult(
                False,
                ("LIVE_RELEASE_NOT_ENABLED", "CAPITAL_PLANE_VERIFY_ONLY"),
            ), None

        gate, context = authorization_gate(
            decision=decision,
            account=account,
            capital=capital,
            config_hash=self.config_hash,
            runtime_config_hash=runtime_config_hash,
            kill_switch_off=True,
            risk_approved=risk_approved,
            firewall_approved=firewall_approved,
            reconciliation_healthy=reconciliation_healthy,
            final_execution_authorization=final_execution_authorization,
            live_trading_enabled=live_trading_enabled,
            probability_calibrated=probability_calibrated,
            probability_fresh=probability_fresh,
            probability_drift_ok=probability_drift_ok,
            market_data_validated=market_data_validated,
            exposure_approved=exposure_approved,
        )
        self._log(
            "PREFLIGHT_AUTHORIZATION",
            {
                "decision_id": decision.decision_id,
                "allowed": gate.allowed,
                "reasons": gate.reason_codes,
            },
        )
        return gate, context

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

        # Re-read authoritative broker capital immediately before submission.
        # Cached/dashboard state is never sufficient for a capital boundary.
        try:
            fresh_balance = await self.broker.get_balance()
        except Exception as exc:
            self.circuit_breaker.record_broker_failure()
            if self.daily_risk_guard is not None:
                risk = self.daily_risk_guard.record_broker_failure("BROKER_BALANCE_UNKNOWN")
                if not risk.get("allowed"):
                    self.activate_kill_switch(str(risk.get("reason") or "BROKER_FAILURE_LIMIT"))
            self._log(
                "PRE_SUBMISSION_BLOCKED",
                {"intent_id": intent.intent_id, "reasons": ("BROKER_STATE_UNKNOWN", type(exc).__name__)},
            )
            return ExecutionOutcome(False, "RECOVERY_REQUIRED", ("BROKER_STATE_UNKNOWN",), intent.intent_id)
        if not fresh_balance.is_valid():
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip("BROKER_BALANCE_STALE_OR_INVALID")
                self.activate_kill_switch("BROKER_BALANCE_STALE_OR_INVALID")
            self._log(
                "PRE_SUBMISSION_BLOCKED",
                {"intent_id": intent.intent_id, "reasons": ("BROKER_BALANCE_STALE_OR_INVALID",)},
            )
            return ExecutionOutcome(False, "BLOCKED", ("BROKER_BALANCE_STALE_OR_INVALID",), intent.intent_id)
        if fresh_balance.account != context.account:
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip("BROKER_ACCOUNT_IDENTITY_CHANGED")
                self.activate_kill_switch("BROKER_ACCOUNT_IDENTITY_CHANGED")
            self._log(
                "PRE_SUBMISSION_BLOCKED",
                {"intent_id": intent.intent_id, "reasons": ("BROKER_ACCOUNT_IDENTITY_CHANGED",)},
            )
            return ExecutionOutcome(False, "BLOCKED", ("BROKER_ACCOUNT_IDENTITY_CHANGED",), intent.intent_id)
        # A low verified balance is a hard Layer 6 survival halt. Check the
        # broker snapshot before comparing it with the cached authorization so
        # low capital always trips the same durable recovery path.
        if fresh_balance.balance <= 1.50 or fresh_balance.available_balance <= 1.50:
            reason = "BALANCE_AT_OR_BELOW_MINIMUM_CAPITAL"
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip(reason)
            self._log(
                "PRE_SUBMISSION_BLOCKED",
                {
                    "intent_id": intent.intent_id,
                    "reasons": (reason,),
                    "verified_balance": fresh_balance.balance,
                    "verified_available_balance": fresh_balance.available_balance,
                },
            )
            self.activate_kill_switch(reason)
            return ExecutionOutcome(False, "BLOCKED", (reason,), intent.intent_id)

        # The authorization snapshot is the capital state against which this
        # intent was approved. Any balance, available-balance, currency, or
        # account change at the final capital boundary may indicate an external
        # transaction or an un-reconciled contract. Never reinterpret it as
        # harmless drift: require a fresh authorization and reconciliation.
        if (
            fresh_balance.balance != context.capital.balance
            or fresh_balance.available_balance != context.capital.available_balance
            or fresh_balance.currency != context.capital.currency
            or fresh_balance.account != context.capital.account
        ):
            reason = "STATE_MISMATCH"
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip(reason)
            self.circuit_breaker.record_reconciliation_failure()
            self._log(
                "STATE_MISMATCH",
                {
                    "intent_id": intent.intent_id,
                    "reason": "PRE_SUBMISSION_CAPITAL_DIFFERS_FROM_AUTHORIZATION_SNAPSHOT",
                },
            )
            self.activate_kill_switch(reason)
            return ExecutionOutcome(
                False,
                "RECOVERY_REQUIRED",
                (reason,),
                intent.intent_id,
            )

        # A purchased Deriv contract's stake is its contractual maximum loss.
        permitted_loss = fresh_balance.balance * self.max_trade_risk_pct
        if intent.stake > permitted_loss + 1e-12:
            self._log("PRE_SUBMISSION_BLOCKED", {
                "intent_id": intent.intent_id,
                "reasons": ("TRADE_RISK_BUDGET_EXCEEDED",),
                "balance": fresh_balance.balance,
                "stake": intent.stake,
                "max_trade_risk_pct": self.max_trade_risk_pct,
            })
            return ExecutionOutcome(False, "BLOCKED", ("TRADE_RISK_BUDGET_EXCEEDED",), intent.intent_id)
        if fresh_balance.available_balance < intent.stake:
            self._log(
                "PRE_SUBMISSION_BLOCKED",
                {"intent_id": intent.intent_id, "reasons": ("STAKE_NO_LONGER_AFFORDABLE",)},
            )
            return ExecutionOutcome(False, "BLOCKED", ("STAKE_NO_LONGER_AFFORDABLE",), intent.intent_id)
        if self.daily_risk_guard is not None:
            risk = self.daily_risk_guard.permit(
                account_loginid=fresh_balance.account.loginid,
                currency=fresh_balance.currency,
                current_balance=fresh_balance.balance,
                captured_at=fresh_balance.captured_at,
            )
            if not risk.get("allowed"):
                reason = str(risk.get("reason") or "DAILY_RISK_DENIED")
                self._log("DAILY_RISK_BLOCKED", {"intent_id": intent.intent_id, "reason": reason})
                self.activate_kill_switch(reason)
                return ExecutionOutcome(False, "BLOCKED", (reason,), intent.intent_id)
        if not self.circuit_breaker.permit():
            self._log(
                "PRE_SUBMISSION_BLOCKED",
                {"intent_id": intent.intent_id, "reasons": ("CIRCUIT_BREAKER_TRIPPED", self.circuit_breaker.reason)},
            )
            return ExecutionOutcome(False, "BLOCKED", ("CIRCUIT_BREAKER_TRIPPED",), intent.intent_id)

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

        try:
            certificate = TradeCertificate.from_authorization(
                intent=intent,
                authorization=context,
                fence_token=fence_token,
            )
        except (TypeError, ValueError) as exc:
            self._log(
                "PRE_SUBMISSION_BLOCKED",
                {
                    "intent_id": intent.intent_id,
                    "reasons": ("TRADE_CERTIFICATE_INVALID", type(exc).__name__),
                },
            )
            return ExecutionOutcome(
                False,
                "BLOCKED",
                ("TRADE_CERTIFICATE_INVALID",),
                intent.intent_id,
            )

        self._log("TRADE_CERTIFICATE_ISSUED", certificate.as_payload())

        existing = self.idempotency.register_intent(intent.intent_id)
        if existing.broker_transaction_id:
            return ExecutionOutcome(
                True,
                "ALREADY_ACCEPTED",
                (),
                intent.intent_id,
                existing.broker_transaction_id,
            )
        if existing.broker_outcome_unknown:
            return ExecutionOutcome(
                False,
                "RECOVERY_REQUIRED",
                ("BROKER_OUTCOME_UNKNOWN_REQUIRES_RECONCILIATION",),
                intent.intent_id,
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

        broker_started = perf_counter()
        try:
            result = await self.broker.submit_authorized_order(
                {"proposal_id": intent.proposal_id, "stake": intent.stake}
            )
            self.latency.observe(
                "broker_submission",
                (perf_counter() - broker_started) * 1000.0,
            )
            self._log(
                "EXECUTION_LATENCY",
                {
                    "intent_id": intent.intent_id,
                    "stage": "broker_submission",
                    "metrics": self.latency.summary("broker_submission"),
                },
            )
        except Exception as exc:
            self.idempotency.record_unknown_outcome(intent.intent_id)
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip("BROKER_SUBMISSION_OUTCOME_UNKNOWN")
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
            self.circuit_breaker.record_broker_failure()
            self.idempotency.record_unknown_outcome(intent.intent_id)
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip("BROKER_OUTCOME_UNKNOWN")
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
            self.circuit_breaker.record_success()
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.record_broker_success()
            self.idempotency.record_economic_effect(intent.intent_id)
            ledger_reservation_posted = False
            try:
                ledger_reservation_posted = bool(self.ledger.post(
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
                ))
            except Exception:
                ledger_reservation_posted = False
            if not ledger_reservation_posted:
                # Broker acceptance has already occurred. Persist a halt, but
                # return the known broker IDs so the caller can still monitor
                # and settle the open contract instead of abandoning exposure.
                if self.daily_risk_guard is not None:
                    self.daily_risk_guard.trip("BROKER_ACCEPTED_LEDGER_RESERVATION_FAILED")
                self.activate_kill_switch("BROKER_ACCEPTED_LEDGER_RESERVATION_FAILED")
            self._log(
                "BROKER_ACCEPTED",
                {
                    "intent_id": intent.intent_id,
                    "broker_transaction_id": result.broker_transaction_id,
                    "contract_id": result.contract_id,
                    "aurelia_trade_number": count_accepted_trades(self.journal.read_all()) + 1,
                },
            )
            return ExecutionOutcome(
                True,
                "ACCEPTED",
                () if ledger_reservation_posted else ("BROKER_ACCEPTED_LEDGER_RESERVATION_FAILED",),
                intent.intent_id,
                result.broker_transaction_id,
                result.contract_id,
            )

        self.circuit_breaker.record_broker_failure()
        if self.daily_risk_guard is not None:
            risk = self.daily_risk_guard.record_broker_failure("BROKER_REJECTED")
            if not risk.get("allowed"):
                self.activate_kill_switch(str(risk.get("reason") or "BROKER_FAILURE_LIMIT"))
        if self.circuit_breaker.tripped:
            self.activate_kill_switch(self.circuit_breaker.reason or "BROKER_FAILURE_THRESHOLD")
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
        if not result.healthy:
            self.circuit_breaker.record_reconciliation_failure()
            self.activate_kill_switch("POST_TRADE_RECONCILIATION_FAILED")
        return result
