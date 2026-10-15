from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any, Protocol

from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.adapters.deriv_lifecycle import monitor_contract
from runtime.broker.executor import CapitalPlaneExecutor, ExecutionOutcome
from runtime.core.events import canonical_json, sha256
from runtime.core.fencing import FenceToken
from runtime.core.models import (
    AccountIdentity,
    AuthorizationContext,
    CapitalSnapshot,
    Decision,
    MarketTick,
    RuntimeState,
    utc_now,
)
from runtime.core.release_gate import read_live_release
from runtime.core.paths import state_path
from runtime.ops.readiness_attestation import config_hash as readiness_config_hash
from runtime.core.stake_sizing import size_stake_for_balance
from runtime.strategy.registry import StrategyQualificationRegistry


class AutonomousDecisionProvider(Protocol):
    async def next_decision(
        self,
        *,
        tick: Any,
        capital: CapitalSnapshot,
        account: AccountIdentity,
    ) -> Decision | None: ...

    def proposal_parameters(
        self,
        *,
        decision: Decision,
        capital: CapitalSnapshot,
        account: AccountIdentity,
    ) -> dict[str, Any]: ...

    def control_snapshot(
        self,
        *,
        decision: Decision,
        tick: Any,
        capital: CapitalSnapshot,
    ) -> dict[str, bool]: ...


@dataclass(frozen=True)
class LifecycleResult:
    intent_id: str
    outcome: str
    broker_transaction_id: str | None
    contract_id: str | None
    settled: bool
    reconciliation_healthy: bool
    post_balance: float | None


# Decision.direction is a forecast direction; the broker operation always buys
# the purchased contract. Unsupported mappings are refused until a strategy has
# a separately qualified instrument-specific execution model.
_DIRECTION_TO_DERIV_CONTRACT = {
    "CALL": "CALL",
    "UP": "CALL",
    "RISE": "CALL",
    "BUY": "CALL",
    "LONG": "CALL",
    "PUT": "PUT",
    "DOWN": "PUT",
    "FALL": "PUT",
    "SELL": "PUT",
    "SHORT": "PUT",
}


def _expected_deriv_contract_type(direction: Any) -> str | None:
    if not isinstance(direction, str):
        return None
    return _DIRECTION_TO_DERIV_CONTRACT.get(direction.strip().upper())


def _decision_symbol_error(decision: Decision, tick: MarketTick, allowed_symbols: tuple[str, ...]) -> str | None:
    if decision.symbol != tick.symbol:
        return "DECISION_TICK_SYMBOL_MISMATCH"
    if allowed_symbols and decision.symbol not in allowed_symbols:
        return "DECISION_SYMBOL_NOT_ALLOWLISTED"
    return None


def validate_incoming_tick(
    tick: MarketTick,
    *,
    expected_symbol: str,
    now: datetime,
    previous_epoch: int | None = None,
    max_age_seconds: float = 5.0,
    future_tolerance_seconds: float = 1.0,
) -> str | None:
    """Return a fail-closed rejection reason for a stale, misrouted, or reordered tick."""
    if not tick.valid():
        return "MARKET_DATA_INVALID"
    if tick.symbol != expected_symbol:
        return "MARKET_DATA_SYMBOL_MISMATCH"
    if tick.received_at.tzinfo is None or now.tzinfo is None:
        return "MARKET_DATA_TIMESTAMP_NAIVE"
    received_age = (now - tick.received_at).total_seconds()
    if not 0 <= received_age <= max_age_seconds:
        return "MARKET_DATA_RECEIVE_AGE_INVALID"
    try:
        source_time = datetime.fromtimestamp(int(tick.epoch), tz=now.tzinfo)
    except (OverflowError, OSError, TypeError, ValueError):
        return "MARKET_DATA_EPOCH_INVALID"
    source_age = (now - source_time).total_seconds()
    if source_age > max_age_seconds or source_age < -future_tolerance_seconds:
        return "MARKET_DATA_SOURCE_AGE_INVALID"
    if previous_epoch is not None and int(tick.epoch) < previous_epoch:
        return "MARKET_DATA_OUT_OF_ORDER"
    return None


def _extract_net_delta(contract: dict[str, Any], stake: float) -> float | None:
    def number(key: str) -> float | None:
        value = contract.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    profit = number("profit")
    if profit is not None:
        return profit

    payout = number("payout")
    buy_price = number("buy_price")
    if payout is not None and buy_price is not None:
        return payout - buy_price

    sell_price = number("sell_price")
    if sell_price is not None and buy_price is not None:
        return sell_price - buy_price

    return None


class AutonomousExecutionLoop:
    """Connects market/strategy proposals to the existing capital executor.

    This is orchestration only. No new trading logic is embedded here.
    Strategy agents publish Decisions; deterministic controls remain the
    authority for capital movement.
    """

    def __init__(
        self,
        *,
        adapter: DerivAdapter,
        executor: CapitalPlaneExecutor,
        decision_provider: AutonomousDecisionProvider,
        runtime_config_hash: str,
        fence_owner: str = "aurelia-runtime",
        symbols: tuple[str, ...] = (),
        lifecycle_timeout_seconds: float = 600.0,
        tick_timeout_seconds: float = 30.0,
        daily_risk_guard=None,
    ) -> None:
        self.adapter = adapter
        self.executor = executor
        self.decision_provider = decision_provider
        self.runtime_config_hash = runtime_config_hash
        self.fence_owner = fence_owner
        self.symbols = symbols
        self.lifecycle_timeout_seconds = lifecycle_timeout_seconds
        self.tick_timeout_seconds = tick_timeout_seconds
        self.daily_risk_guard = daily_risk_guard if daily_risk_guard is not None else executor.daily_risk_guard
        self._stop = asyncio.Event()
        self._fence: FenceToken | None = None
        self.trades_attempted = 0
        self.trades_accepted = 0
        self._last_tick_epoch: dict[str, int] = {}
        # Optional health hook, invoked only after a source-fresh, symbol-bound
        # tick has passed local validation.
        self.on_validated_tick = None

    async def _fresh_authorization(
        self,
        *,
        decision: Decision,
        capital: CapitalSnapshot,
        account: AccountIdentity,
        controls: dict[str, bool],
        proposal_id: str | None = None,
        mode: str = "LIVE",
    ) -> tuple[AuthorizationContext | None, Any | None]:
        release = read_live_release(self.executor.live_lock_path)
        if mode == "LIVE" and not release.may_move_capital:
            return None, None

        gate, ctx, intent = await self.executor.authorize_and_build_intent(
            decision=decision,
            capital=capital,
            runtime_config_hash=self.runtime_config_hash,
            account=account,
            risk_approved=controls.get("risk_approved", False),
            firewall_approved=controls.get("firewall_approved", False),
            reconciliation_healthy=controls.get("reconciliation_healthy", False),
            final_execution_authorization=controls.get("final_execution_authorization", False),
            live_trading_enabled=controls.get("live_trading_enabled", False),
            probability_calibrated=controls.get("probability_calibrated", False),
            probability_fresh=controls.get("probability_fresh", False),
            probability_drift_ok=controls.get("probability_drift_ok", False),
            market_data_validated=controls.get("market_data_validated", False),
            exposure_approved=controls.get("exposure_approved", False),
            proposal_id=proposal_id,
            mode=mode,
        )
        if gate.allowed and ctx and intent:
            return ctx, intent
        return None, None

    async def _prepare_live_intent(
        self,
        *,
        decision: Decision,
        capital: CapitalSnapshot,
        account: AccountIdentity,
        controls: dict[str, bool],
        proposal_id: str,
    ) -> tuple[AuthorizationContext | None, Any | None]:
        # The startup latch must be cleared once, then normal decision cycles
        # should proceed through a fresh final authorization without trying to
        # clear a switch that is already off.
        if not self.executor.kill_switch:
            return await self._fresh_authorization(
                decision=decision,
                capital=capital,
                account=account,
                controls=controls,
                proposal_id=proposal_id,
                mode="LIVE",
            )

        # If the switch is on, this path is for initial startup authorization
        # or an explicit recovery attempt. The executor independently decides
        # whether the current latch is eligible to be cleared.
        pre_gate, pre_ctx = await self.executor.preflight_authorization(
            decision=decision,
            capital=capital,
            runtime_config_hash=self.runtime_config_hash,
            account=account,
            risk_approved=controls.get("risk_approved", False),
            firewall_approved=controls.get("firewall_approved", False),
            reconciliation_healthy=controls.get("reconciliation_healthy", False),
            final_execution_authorization=controls.get("final_execution_authorization", False),
            live_trading_enabled=controls.get("live_trading_enabled", False),
            probability_calibrated=controls.get("probability_calibrated", False),
            probability_fresh=controls.get("probability_fresh", False),
            probability_drift_ok=controls.get("probability_drift_ok", False),
            market_data_validated=controls.get("market_data_validated", False),
            exposure_approved=controls.get("exposure_approved", False),
        )
        if not pre_gate.allowed or pre_ctx is None:
            return None, None
        if not self.executor.clear_kill_switch_with_fresh_authorization(pre_ctx):
            return None, None

        return await self._fresh_authorization(
            decision=decision,
            capital=capital,
            account=account,
            controls=controls,
            proposal_id=proposal_id,
            mode="LIVE",
        )

    async def _settle_and_reconcile(
        self,
        *,
        intent: Any,
        prior_capital: CapitalSnapshot,
        contract_id: str,
        broker_transaction_id: str,
    ) -> LifecycleResult:
        final_contract: dict[str, Any] | None = None
        try:
            async with asyncio.timeout(self.lifecycle_timeout_seconds):
                async for status in monitor_contract(self.adapter, contract_id):
                    final_contract = status
        except TimeoutError:
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip("CONTRACT_SETTLEMENT_TIMEOUT")
            self.executor.activate_kill_switch("CONTRACT_SETTLEMENT_TIMEOUT")
            return LifecycleResult(
                intent.intent_id,
                "RECOVERY_REQUIRED",
                None,
                contract_id,
                False,
                False,
                None,
            )

        except Exception:
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip("CONTRACT_STATUS_UNRESOLVED")
            self.executor.activate_kill_switch("CONTRACT_STATUS_UNRESOLVED")
            return LifecycleResult(
                intent.intent_id, "RECOVERY_REQUIRED", broker_transaction_id,
                contract_id, False, False, None,
            )

        if final_contract is None:
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip("CONTRACT_STATUS_UNRESOLVED")
            self.executor.activate_kill_switch("CONTRACT_STATUS_UNRESOLVED")
            return LifecycleResult(
                intent.intent_id,
                "RECOVERY_REQUIRED",
                None,
                contract_id,
                False,
                False,
                None,
            )

        net_delta = _extract_net_delta(final_contract, intent.stake)
        if net_delta is None:
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip("BROKER_SETTLEMENT_ECONOMICS_UNRESOLVED")
            self.executor.activate_kill_switch("BROKER_SETTLEMENT_ECONOMICS_UNRESOLVED")
            return LifecycleResult(
                intent.intent_id,
                "RECOVERY_REQUIRED",
                None,
                contract_id,
                True,
                False,
                None,
            )

        try:
            post_balance = await self.adapter.get_balance()
            reconciliation = await self.executor.reconcile(
                broker_capital=post_balance,
                prior_authoritative_balance=prior_capital.available_balance,
                explainable_delta=net_delta,
            )
        except Exception:
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip("POST_TRADE_BALANCE_OR_RECONCILIATION_UNKNOWN")
            self.executor.activate_kill_switch("POST_TRADE_BALANCE_OR_RECONCILIATION_UNKNOWN")
            return LifecycleResult(
                intent.intent_id, "RECOVERY_REQUIRED", broker_transaction_id,
                contract_id, True, False, None,
            )

        from runtime.core.models import LedgerEvent
        event = LedgerEvent(
            event_id=f"settlement:{intent.intent_id}",
            intent_id=intent.intent_id,
            account=intent.account,
            event_type="CONTRACT_SETTLED",
            amount=net_delta,
            currency=intent.account.currency,
            occurred_at=utc_now(),
            broker_transaction_id=broker_transaction_id,
            metadata={
                "contract_id": contract_id,
                "post_balance": post_balance.available_balance,
                "broker_profit": final_contract.get("profit"),
                "broker_payout": final_contract.get("payout"),
            },
        )
        posted = self.executor.ledger.post(event)
        if not posted:
            if self.daily_risk_guard is not None:
                self.daily_risk_guard.trip("SETTLEMENT_LEDGER_DUPLICATE_OR_UNPOSTED")
            self.executor.activate_kill_switch("SETTLEMENT_LEDGER_DUPLICATE_OR_UNPOSTED")
            return LifecycleResult(
                intent.intent_id, "RECOVERY_REQUIRED", broker_transaction_id,
                contract_id, True, False, post_balance.available_balance,
            )

        status_value = str(final_contract.get("status") or "").lower()
        terminal = bool(final_contract.get("is_sold")) or status_value in {
            "sold", "closed", "won", "lost", "expired"
        }
        if self.daily_risk_guard is not None:
            risk = self.daily_risk_guard.record_closed_trade(
                intent_id=intent.intent_id,
                contract_id=contract_id,
                broker_transaction_id=broker_transaction_id,
                account_loginid=intent.account.loginid,
                currency=intent.account.currency,
                net_pnl=net_delta,
                post_balance=post_balance.balance,
                closed_at=utc_now(),
                terminal=terminal,
                reconciled=reconciliation.healthy,
            )
            if not risk.get("allowed"):
                self.executor.activate_kill_switch(str(risk.get("reason") or "DAILY_RISK_TRIPPED"))

        if not reconciliation.healthy:
            self.executor.activate_kill_switch("POST_TRADE_RECONCILIATION_MISMATCH")

        return LifecycleResult(
            intent.intent_id,
            "SETTLED" if reconciliation.healthy else "RECOVERY_REQUIRED",
            broker_transaction_id,
            contract_id,
            terminal,
            reconciliation.healthy,
            post_balance.available_balance,
        )

    async def execute_decision(
        self,
        *,
        decision: Decision,
        capital: CapitalSnapshot,
        account: AccountIdentity,
        controls: dict[str, bool],
    ) -> LifecycleResult | ExecutionOutcome:
        self.trades_attempted += 1
        if self.symbols and decision.symbol not in self.symbols:
            reason = "DECISION_SYMBOL_NOT_ALLOWLISTED"
            self.executor._log("DECISION_SYMBOL_REJECTED", {
                "decision_id": decision.decision_id,
                "reason": reason,
                "decision_symbol": decision.symbol,
                "allowed_symbols": self.symbols,
                "capital_authority_granted": False,
                "order_submission_permitted": False,
            })
            return ExecutionOutcome(
                False, "BLOCKED", (reason,), f"intent:{decision.decision_id}"
            )

        # A direct caller must not submit a broker proposal from an un-sized
        # agent decision. The risk/exposure approval must refer to this exact
        # deterministic stake; never resize after those approvals were made.
        sizing = size_stake_for_balance(capital.available_balance)
        if not sizing.allowed:
            reason = sizing.reason
            self.executor._log("STAKE_SIZING_BLOCKED", {
                "decision_id": decision.decision_id,
                "reason": reason,
                "capital_authority_granted": False,
                "order_submission_permitted": False,
            })
            return ExecutionOutcome(
                False, "BLOCKED", (reason,), f"intent:{decision.decision_id}"
            )
        try:
            requested_stake = float(decision.risk_requested_stake)
        except (TypeError, ValueError, OverflowError):
            requested_stake = float("nan")
        if not __import__("math").isfinite(requested_stake) or abs(requested_stake - float(sizing.stake)) > 1e-9:
            reason = "LIVE_STAKE_NOT_POLICY_SIZED"
            self.executor._log("STAKE_SIZING_BLOCKED", {
                "decision_id": decision.decision_id,
                "reason": reason,
                "requested_stake": decision.risk_requested_stake,
                "policy_stake": sizing.stake,
                "capital_authority_granted": False,
                "order_submission_permitted": False,
            })
            return ExecutionOutcome(
                False, "BLOCKED", (reason,), f"intent:{decision.decision_id}"
            )
        if self.daily_risk_guard is not None:
            risk = self.daily_risk_guard.permit(
                account_loginid=account.loginid,
                currency=capital.currency,
                current_balance=capital.balance,
                captured_at=capital.captured_at,
            )
            if not risk.get("allowed"):
                reason = str(risk.get("reason") or "DAILY_RISK_DENIED")
                self.executor.activate_kill_switch(reason)
                self.executor._log("DAILY_RISK_BLOCKED", {
                    "decision_id": decision.decision_id, "reason": reason,
                })
                return ExecutionOutcome(False, "BLOCKED", (reason,), f"intent:{decision.decision_id}")
        # Check the canonical release lock before making even a quote/proposal
        # request. A proposal does not buy a contract, but a blocked release
        # must not initiate the broker trading workflow at all.
        release = read_live_release(self.executor.live_lock_path)
        if not release.may_move_capital:
            reason = "LIVE_RELEASE_NOT_ENABLED"
            self.executor._log("LIVE_RELEASE_GATE_BLOCKED", {
                "decision_id": decision.decision_id,
                "reason": reason,
                "live_execution_enabled": release.live_execution_enabled,
                "capital_plane_mode": release.capital_plane_mode,
                "proposal_requested": False,
                "order_submission_permitted": False,
            })
            return ExecutionOutcome(
                False, "BLOCKED", (reason,), f"intent:{decision.decision_id}"
            )

        unresolved = self.executor.unresolved_unknown_intents()
        if unresolved is None or unresolved:
            reason = "UNRESOLVED_BROKER_OUTCOME" if unresolved is not None else "IDEMPOTENCY_STATE_UNKNOWN"
            self.executor._log("BROKER_RECOVERY_GATE_BLOCKED", {
                "decision_id": decision.decision_id,
                "reason": reason,
                "unresolved_count": len(unresolved) if unresolved is not None else None,
                "proposal_requested": False,
                "order_submission_permitted": False,
            })
            if not self.executor.kill_switch:
                self.executor.activate_kill_switch(reason)
            return ExecutionOutcome(
                False, "RECOVERY_REQUIRED", (reason,), f"intent:{decision.decision_id}"
            )

        # A fault-latched switch is not the ordinary startup lock. Do not even
        # request another quote until the explicit signed operator proof has
        # been processed by the canonical executor recovery path.
        if getattr(self.executor, "_fault_latched", False):
            reason = str(getattr(self.executor, "_kill_switch_reason", "FAULT_LATCHED"))
            self.executor._log("KILL_SWITCH_FAULT_LATCHED", {
                "decision_id": decision.decision_id,
                "reason": reason,
                "proposal_requested": False,
                "capital_authority_granted": False,
                "order_submission_permitted": False,
            })
            return ExecutionOutcome(
                False, "RECOVERY_REQUIRED", ("KILL_SWITCH_FAULT_LATCHED", reason),
                f"intent:{decision.decision_id}"
            )

        portfolio_block = await self.executor.verify_no_open_positions()
        if portfolio_block:
            self.executor._log("PORTFOLIO_EXPOSURE_GATE_BLOCKED", {
                "decision_id": decision.decision_id,
                "reason": portfolio_block,
                "proposal_requested": False,
                "order_submission_permitted": False,
            })
            if portfolio_block != "OPEN_POSITIONS_PRESENT" and not self.executor.kill_switch:
                self.executor.activate_kill_switch(portfolio_block)
            status = "BLOCKED" if portfolio_block == "OPEN_POSITIONS_PRESENT" else "RECOVERY_REQUIRED"
            return ExecutionOutcome(
                False, status, (portfolio_block,), f"intent:{decision.decision_id}"
            )

        if self._fence is None or not self.executor.fence.valid(self._fence):
            self._fence = self.executor.fence.acquire(self.fence_owner)

        parameters = dict(self.decision_provider.proposal_parameters(
            decision=decision,
            capital=capital,
            account=account,
        ))
        expected_contract = _expected_deriv_contract_type(decision.direction)
        supplied_contract = str(parameters.get("contract_type", "")).strip().upper()
        if expected_contract is None or supplied_contract != expected_contract:
            reason = "PROPOSAL_CONTRACT_DIRECTION_MISMATCH"
            self.executor._log("PROPOSAL_PREFLIGHT_BLOCKED", {
                "decision_id": decision.decision_id,
                "reason": reason,
                "decision_direction": str(decision.direction),
                "contract_type": supplied_contract,
                "proposal_requested": False,
                "order_submission_permitted": False,
            })
            return ExecutionOutcome(
                False, "BLOCKED", (reason,), f"intent:{decision.decision_id}"
            )
        # Only stake-basis purchased contracts have a known max-loss bound in
        # this execution model. Other basis modes require a separately tested
        # instrument-specific risk model and may not pass this path.
        requested_basis = str(parameters.get("basis", "stake")).strip().lower()
        if requested_basis != "stake":
            reason = "PROPOSAL_BASIS_MUST_BE_STAKE"
            self.executor._log("PROPOSAL_PREFLIGHT_BLOCKED", {
                "decision_id": decision.decision_id,
                "reason": reason,
                "basis": requested_basis,
                "proposal_requested": False,
                "order_submission_permitted": False,
            })
            return ExecutionOutcome(
                False, "BLOCKED", (reason,), f"intent:{decision.decision_id}"
            )
        # Deriv's proposal captures stake/basis. Bind the proposal itself to
        # the same policy-sized stake later certified by the capital plane;
        # never inherit amount/basis from an external strategy/agent payload.
        parameters["basis"] = "stake"
        parameters["amount"] = float(sizing.stake)
        if str(parameters.get("currency", "")).upper() != account.currency.upper():
            raise RuntimeError("PROPOSAL_CURRENCY_MISMATCH")
        if str(parameters.get("underlying_symbol", "")) != decision.symbol:
            raise RuntimeError("PROPOSAL_SYMBOL_MISMATCH")
        proposal_id = await self.executor.prepare_proposal(parameters)
        ctx, intent = await self._prepare_live_intent(
            decision=decision,
            capital=capital,
            account=account,
            controls=controls,
            proposal_id=proposal_id,
        )
        if ctx is None or intent is None:
            return ExecutionOutcome(False, "BLOCKED", ("LIVE_AUTHORIZATION_NOT_AVAILABLE",), f"intent:{decision.decision_id}")

        if intent.proposal_id is None:
            raise RuntimeError("PROPOSAL_ID_NOT_BOUND_TO_INTENT")

        outcome = await self.executor.execute(intent, ctx, self._fence)
        if not outcome.allowed:
            if outcome.status == "RECOVERY_REQUIRED" and not self.executor.kill_switch:
                self.executor.activate_kill_switch("BROKER_OUTCOME_UNCERTAIN")
            return outcome

        self.trades_accepted += 1
        if not outcome.broker_transaction_id:
            self.executor.activate_kill_switch("BROKER_TRANSACTION_ID_MISSING_AFTER_ACCEPTANCE")
            return LifecycleResult(
                intent.intent_id,
                "RECOVERY_REQUIRED",
                None,
                None,
                False,
                False,
                None,
            )

        if not intent.proposal_id:
            self.executor.activate_kill_switch("PROPOSAL_ID_MISSING")
            return LifecycleResult(
                intent.intent_id,
                "RECOVERY_REQUIRED",
                outcome.broker_transaction_id,
                None,
                False,
                False,
                None,
            )

        # Prefer the contract ID already confirmed in the broker buy response.
        # Fall back to portfolio/statement only for adapters that omit it.
        contract_id = str(outcome.contract_id) if outcome.contract_id else None
        if contract_id is None:
            portfolio = await self.adapter.portfolio()
            candidate = next(
                (
                    row for row in portfolio
                    if str(row.get("transaction_id") or "") == str(outcome.broker_transaction_id)
                ),
                None,
            )
            contract_id = str(candidate.get("contract_id")) if candidate and candidate.get("contract_id") else None
        if contract_id is None:
            statement = await self.adapter.statement(limit=100)
            candidate = next(
                (
                    row for row in statement
                    if str(row.get("transaction_id") or row.get("id") or "") == str(outcome.broker_transaction_id)
                ),
                None,
            )
            contract_id = str(candidate.get("contract_id")) if candidate and candidate.get("contract_id") else None

        if contract_id is None:
            self.executor.activate_kill_switch("BROKER_CONTRACT_BINDING_UNRESOLVED")
            return LifecycleResult(
                intent.intent_id,
                "RECOVERY_REQUIRED",
                outcome.broker_transaction_id,
                None,
                False,
                False,
                None,
            )

        return await self._settle_and_reconcile(
            intent=intent,
            prior_capital=capital,
            contract_id=contract_id,
            broker_transaction_id=outcome.broker_transaction_id,
        )

    async def run(self) -> None:
        if not self.symbols:
            symbols = await self.adapter.active_symbols()
            self.symbols = tuple(
                str(item.get("symbol"))
                for item in symbols
                if item.get("symbol")
            )

        if not self.symbols:
            raise RuntimeError("NO_DERIV_SYMBOLS_AVAILABLE")

        streams = [self.adapter.subscribe_ticks(symbol) for symbol in self.symbols]
        iterators = [stream.__aiter__() for stream in streams]
        # Keep one outstanding read per symbol. Cancelling all slower reads
        # whenever any one symbol ticks can cancel/close the other async
        # generators and silently starve multi-symbol runtime decisions.
        inflight: dict[asyncio.Task, tuple[Any, str]] = {}
        started_at = utc_now()
        last_tick_received: dict[str, datetime] = {
            symbol: started_at for symbol in self.symbols
        }
        try:
            tick_timeout = float(self.tick_timeout_seconds)
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("TICK_TIMEOUT_CONFIGURATION_INVALID") from exc
        if not __import__("math").isfinite(tick_timeout) or tick_timeout <= 0:
            raise RuntimeError("TICK_TIMEOUT_CONFIGURATION_INVALID")

        for expected_symbol, iterator in zip(self.symbols, iterators):
            task = asyncio.create_task(iterator.__anext__())
            inflight[task] = (iterator, expected_symbol)
        stop_task = asyncio.create_task(self._stop.wait(), name="aurelia-execution-loop-stop")

        try:
            while not self._stop.is_set() and inflight:
                done, _ = await asyncio.wait(
                    (*inflight.keys(), stop_task),
                    timeout=tick_timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if stop_task in done and self._stop.is_set():
                    break
                if not done:
                    now = utc_now()
                    stale_symbols = [
                        symbol
                        for symbol, last_received in last_tick_received.items()
                        if (now - last_received).total_seconds() >= tick_timeout
                    ]
                    reason = "MARKET_DATA_TIMEOUT"
                    if not self.executor.kill_switch:
                        self.executor.activate_kill_switch(reason)
                    self.executor._log("MARKET_DATA_WATCHDOG_TIMEOUT", {
                        "reason": reason,
                        "stale_symbols": stale_symbols or list(self.symbols),
                        "timeout_seconds": tick_timeout,
                        "capital_authority_granted": False,
                        "order_submission_permitted": False,
                    })
                    continue

                for task in done:
                    iterator, expected_symbol = inflight.pop(task)
                    try:
                        tick = task.result()
                    except StopAsyncIteration:
                        continue

                    # Re-arm only the stream that produced this tick. Other
                    # symbol readers stay alive and retain their pending read.
                    next_task = asyncio.create_task(iterator.__anext__())
                    inflight[next_task] = (iterator, expected_symbol)

                    tick_error = validate_incoming_tick(
                        tick,
                        expected_symbol=expected_symbol,
                        now=utc_now(),
                        previous_epoch=self._last_tick_epoch.get(expected_symbol),
                    )
                    if tick_error:
                        self.executor.activate_kill_switch(tick_error)
                        self.executor._log("MARKET_DATA_REJECTED", {
                            "reason": tick_error,
                            "expected_symbol": expected_symbol,
                            "observed_symbol": getattr(tick, "symbol", None),
                            "source_epoch": getattr(tick, "epoch", None),
                            "capital_authority_granted": False,
                            "order_submission_permitted": False,
                        })
                        continue
                    self._last_tick_epoch[expected_symbol] = int(tick.epoch)
                    last_tick_received[expected_symbol] = tick.received_at
                    if callable(self.on_validated_tick):
                        try:
                            self.on_validated_tick()
                        except Exception as exc:
                            self.executor._log("VALIDATED_TICK_HEALTH_HOOK_FAILED", {
                                "error_class": type(exc).__name__,
                                "capital_authority_granted": False,
                                "order_submission_permitted": False,
                            })
                    now = utc_now()
                    stale_symbols = [
                        symbol
                        for symbol, last_received in last_tick_received.items()
                        if (now - last_received).total_seconds() >= tick_timeout
                    ]
                    if stale_symbols:
                        reason = "MARKET_DATA_SYMBOL_TIMEOUT"
                        if not self.executor.kill_switch:
                            self.executor.activate_kill_switch(reason)
                        self.executor._log("MARKET_DATA_WATCHDOG_TIMEOUT", {
                            "reason": reason,
                            "stale_symbols": stale_symbols,
                            "timeout_seconds": tick_timeout,
                            "capital_authority_granted": False,
                            "order_submission_permitted": False,
                        })
                        continue
                    capital = await self.adapter.get_balance()

                    decision = await self.decision_provider.next_decision(
                        tick=tick,
                        capital=capital,
                        account=capital.account,
                    )
                    if decision is None:
                        if self._stop.is_set():
                            break
                        continue

                    symbol_error = _decision_symbol_error(decision, tick, self.symbols)
                    if symbol_error:
                        self.executor._log("DECISION_SYMBOL_REJECTED", {
                            "decision_id": decision.decision_id,
                            "reason": symbol_error,
                            "decision_symbol": decision.symbol,
                            "tick_symbol": tick.symbol,
                            "capital_authority_granted": False,
                            "order_submission_permitted": False,
                        })
                        self.executor.activate_kill_switch(symbol_error)
                        continue

                    if decision.decision_time.tzinfo is None or decision.decision_time > tick.received_at:
                        self.executor.activate_kill_switch("DECISION_TIME_INVALID")
                        continue
                    if (tick.received_at - decision.decision_time).total_seconds() > 5:
                        self.executor.activate_kill_switch("DECISION_STALE")
                        continue

                    # Size from fresh broker-verified available capital before
                    # computing risk/exposure approvals. Strategy-supplied stake
                    # cannot override this deterministic 1% risk policy.
                    sizing = size_stake_for_balance(capital.available_balance)
                    if not sizing.allowed:
                        self.executor._log("STAKE_SIZING_BLOCKED", {
                            "decision_id": decision.decision_id,
                            "reason": sizing.reason,
                            "capital_authority_granted": False,
                            "order_submission_permitted": False,
                        })
                        continue
                    proposed_stake = decision.risk_requested_stake
                    decision = replace(decision, risk_requested_stake=float(sizing.stake))
                    self.executor._log("LIVE_STAKE_POLICY_APPLIED", {
                        "decision_id": decision.decision_id,
                        "proposed_stake": proposed_stake,
                        "policy_stake": decision.risk_requested_stake,
                        "risk_fraction": 0.01,
                        "sizing_source": "fresh_verified_available_balance",
                    })

                    controls = self.decision_provider.control_snapshot(
                        decision=decision,
                        tick=tick,
                        capital=capital,
                    )
                    if not all(isinstance(value, bool) for value in controls.values()):
                        self.executor.activate_kill_switch("CONTROL_SNAPSHOT_INVALID")
                        continue

                    try:
                        result = await self.execute_decision(
                            decision=decision,
                            capital=capital,
                            account=capital.account,
                            controls=controls,
                        )
                        if isinstance(result, LifecycleResult) and not result.reconciliation_healthy:
                            self.executor.activate_kill_switch("TRADE_LIFECYCLE_RECONCILIATION_FAILED")
                    except Exception:
                        self.executor.activate_kill_switch("AUTONOMOUS_LOOP_EXCEPTION")
        finally:
            remaining = list(inflight.keys())
            for task in remaining:
                task.cancel()
            if not stop_task.done():
                stop_task.cancel()
            await asyncio.gather(*remaining, stop_task, return_exceptions=True)

        if not self._stop.is_set():
            raise RuntimeError("NO_ACTIVE_TICK_STREAMS")

    def stop(self) -> None:
        self._stop.set()


class FederatedDecisionProvider:
    """Turns durable agent DECISION_PROPOSAL messages into Decisions.

    Agents can propose; only the capital plane can authorize and submit.
    """

    def __init__(
        self,
        federation,
        *,
        consumer: str = "AURELIA",
        strategy_registry: StrategyQualificationRegistry | None = None,
        registry_path: str | Path | None = None,
    ) -> None:
        self.federation = federation
        self.consumer = consumer
        self._seen: set[str] = set()
        self._proposal_parameters: dict[str, dict[str, Any]] = {}
        self._rejections: list[dict[str, Any]] = []
        self._registry_error: str | None = None
        try:
            self._expected_config_hash = readiness_config_hash(Path(__file__).resolve().parents[1])
        except (OSError, ValueError, RuntimeError):
            self._expected_config_hash = ""
        if strategy_registry is not None:
            self.strategy_registry = strategy_registry
        else:
            try:
                self.strategy_registry = StrategyQualificationRegistry.from_file(registry_path)
            except (OSError, ValueError) as exc:
                self.strategy_registry = None
                self._registry_error = type(exc).__name__

    async def _publish_rejection(self, message: dict[str, Any], payload: dict[str, Any]) -> None:
        publish = getattr(self.federation, "publish", None)
        if not callable(publish):
            return
        sender = str(message.get("sender") or self.consumer).strip() or self.consumer
        try:
            await publish(
                sender="AURELIA",
                recipients=(sender,),
                message_type="STRATEGY_PROPOSAL_REJECTED",
                payload=payload,
                correlation_id="strategy-gate:" + str(payload.get("message_id") or "unknown"),
                priority=90,
                requires_response=False,
            )
        except Exception:
            # Local rejection remains effective even if notifying the proposer fails.
            return

    async def next_decision(self, *, tick, capital, account):
        messages = self.federation.messages_for(self.consumer, limit=100)
        for message in messages:
            if message.get("message_type") != "DECISION_PROPOSAL":
                continue
            message_id = str(message.get("message_id", ""))
            if not message_id or message_id in self._seen:
                continue
            payload = message.get("payload", {})
            if not isinstance(payload, dict):
                self._seen.add(message_id)
                rejected = {
                    "message_id": message_id,
                    "eligible": False,
                    "reasons": ["DECISION_PAYLOAD_INVALID"],
                }
                self._rejections.append(rejected)
                await self._publish_rejection(message, rejected)
                continue
            if str(payload.get("account_loginid", account.loginid)) != account.loginid:
                continue
            if str(payload.get("symbol", tick.symbol)) != tick.symbol:
                continue
            try:
                for field in ("probability", "risk_requested_stake"):
                    raw = payload.get(field)
                    if (
                        isinstance(raw, bool)
                        or not isinstance(raw, (int, float))
                        or not isfinite(float(raw))
                    ):
                        raise ValueError("DECISION_NUMERIC_FIELD_INVALID")
                for field in (
                    "average_win", "average_loss", "execution_cost",
                    "slippage_cost", "quote_cost", "expected_value",
                ):
                    raw = payload.get(field)
                    if raw is None:
                        continue
                    if (
                        isinstance(raw, bool)
                        or not isinstance(raw, (int, float))
                        or not isfinite(float(raw))
                    ):
                        raise ValueError("DECISION_NUMERIC_FIELD_INVALID")
                decision = Decision(
                    decision_id=str(payload["decision_id"]),
                    strategy_id=str(payload["strategy_id"]),
                    strategy_version=str(payload["strategy_version"]),
                    strategy_hash=str(payload["strategy_hash"]),
                    symbol=str(payload["symbol"]),
                    direction=str(payload["direction"]),
                    probability=float(payload["probability"]),
                    decision_time=datetime.fromisoformat(str(payload["decision_time"])),
                    market_snapshot_hash=str(payload["market_snapshot_hash"]),
                    risk_requested_stake=float(payload["risk_requested_stake"]),
                    rationale_codes=tuple(payload.get("rationale_codes", ())),
                    average_win=(float(payload["average_win"]) if payload.get("average_win") is not None else None),
                    average_loss=(float(payload["average_loss"]) if payload.get("average_loss") is not None else None),
                    execution_cost=float(payload.get("execution_cost", 0.0)),
                    slippage_cost=float(payload.get("slippage_cost", 0.0)),
                    quote_cost=float(payload.get("quote_cost", 0.0)),
                    expected_value=(float(payload["expected_value"]) if payload.get("expected_value") is not None else None),
                )
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                self._seen.add(message_id)
                rejected = {
                    "message_id": message_id,
                    "decision_id": str(payload.get("decision_id", "")),
                    "eligible": False,
                    "reasons": ["DECISION_PAYLOAD_INVALID"],
                    "error_class": type(exc).__name__,
                }
                self._rejections.append(rejected)
                await self._publish_rejection(message, rejected)
                continue
            if self.strategy_registry is None:
                eligibility = {
                    "eligible": False,
                    "status": "BLOCKED",
                    "strategy_id": decision.strategy_id,
                    "version": decision.strategy_version,
                    "instrument_id": decision.symbol,
                    "reasons": ["STRATEGY_REGISTRY_UNAVAILABLE"],
                }
                if self._registry_error:
                    eligibility["registry_error_class"] = self._registry_error
            else:
                eligibility = self.strategy_registry.eligibility(
                    decision.strategy_id,
                    decision.strategy_version,
                    decision.symbol,
                    strategy_hash=decision.strategy_hash,
                )
            if not eligibility.get("eligible", False):
                self._seen.add(message_id)
                rejected = {
                    "message_id": message_id,
                    "decision_id": decision.decision_id,
                    "strategy_id": decision.strategy_id,
                    "strategy_version": decision.strategy_version,
                    "instrument_id": decision.symbol,
                    "eligible": False,
                    "reasons": list(eligibility.get("reasons") or ["STRATEGY_ELIGIBILITY_UNKNOWN"]),
                }
                self._rejections.append(rejected)
                await self._publish_rejection(message, rejected)
                continue

            params = payload.get("proposal_parameters")
            if not isinstance(params, dict):
                self._seen.add(message_id)
                continue
            self._proposal_parameters[decision.decision_id] = dict(params)
            self._seen.add(message_id)
            return decision
        return None

    def proposal_parameters(self, *, decision, capital, account):
        params = self._proposal_parameters.pop(decision.decision_id, None)
        if not isinstance(params, dict):
            raise RuntimeError("DECISION_PROPOSAL_PARAMETERS_NOT_AVAILABLE")
        required = ("contract_type", "currency", "underlying_symbol")
        missing = [key for key in required if not params.get(key)]
        if missing:
            raise RuntimeError("PROPOSAL_PARAMETERS_MISSING:" + ",".join(missing))
        if str(params.get("currency")) != account.currency:
            raise RuntimeError("PROPOSAL_CURRENCY_MISMATCH")
        if str(params.get("underlying_symbol")) != decision.symbol:
            raise RuntimeError("PROPOSAL_SYMBOL_MISMATCH")
        expected_contract = _expected_deriv_contract_type(decision.direction)
        supplied_contract = str(params.get("contract_type", "")).strip().upper()
        if expected_contract is None or supplied_contract != expected_contract:
            raise RuntimeError("PROPOSAL_CONTRACT_DIRECTION_MISMATCH")
        if str(params.get("basis", "stake")).strip().lower() != "stake":
            raise RuntimeError("PROPOSAL_BASIS_MUST_BE_STAKE")
        return dict(params)

    def control_snapshot(self, *, decision, tick, capital):
        # Consume the live runtime publisher's output, never a tracked historical
        # readiness snapshot. Every field remains false unless the report is
        # current, source-bound, and backed by verified attestations.
        denied = {key: False for key in (
            "risk_approved", "firewall_approved", "reconciliation_healthy",
            "final_execution_authorization", "live_trading_enabled",
            "probability_calibrated", "probability_fresh", "probability_drift_ok",
            "market_data_validated", "exposure_approved",
        )}
        path = state_path("AURELIA_READINESS_PATH", "AURELIA_READINESS.json")
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return denied
        if not isinstance(report, dict):
            return denied

        try:
            max_age = float(__import__("os").getenv("AURELIA_READINESS_MAX_AGE_SECONDS", "30"))
            generated = datetime.fromisoformat(
                str(report["generated_at_utc"]).replace("Z", "+00:00")
            )
            age = (utc_now() - generated).total_seconds()
            fresh = (
                __import__("math").isfinite(max_age)
                and max_age > 0
                and generated.tzinfo is not None
                and 0 <= age <= max_age
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            fresh = False

        expected_source = (
            __import__("os").getenv("GITHUB_SHA", "").strip()
            or __import__("os").getenv("AURELIA_SOURCE_SHA", "").strip()
        )
        attestations = report.get("attestations")
        required_capabilities = {
            "MARKET_DATA", "PROBABILITY", "RISK_WARDEN",
            "EXECUTION_FIREWALL", "EXPOSURE", "RECONCILIATION",
            "WATCHDOG", "IDEMPOTENCY", "PERSISTENT_WORKER",
        }
        verified = attestations.get("verified") if isinstance(attestations, dict) else None
        attestation_expiry_ok = False
        if isinstance(verified, dict):
            try:
                expires = [
                    datetime.fromisoformat(
                        str(item["expires_at_utc"]).replace("Z", "+00:00")
                    )
                    for item in verified.values()
                    if isinstance(item, dict)
                ]
                attestation_expiry_ok = bool(expires) and all(
                    expiry.tzinfo is not None and expiry > utc_now()
                    for expiry in expires
                )
            except (KeyError, TypeError, ValueError, OverflowError):
                attestation_expiry_ok = False
        verified_bundle_complete = (
            isinstance(verified, dict)
            and set(verified) == required_capabilities
            and all(
                isinstance(item, dict)
                and item.get("status") == "PASS"
                and isinstance(item.get("issuer"), str) and bool(item["issuer"].strip())
                and isinstance(item.get("subject"), str) and bool(item["subject"].strip())
                and isinstance(item.get("evidence_hash"), str) and bool(item["evidence_hash"].strip())
                and isinstance(item.get("provenance"), str) and bool(item["provenance"].strip())
                and isinstance(item.get("expires_at_utc"), str) and bool(item["expires_at_utc"].strip())
                for item in verified.values()
            )
            and attestation_expiry_ok
        )
        source_bound = (
            bool(expected_source)
            and isinstance(attestations, dict)
            and attestations.get("source_sha") == expected_source
            and bool(self._expected_config_hash)
            and attestations.get("config_hash") == self._expected_config_hash
            and isinstance(attestations.get("runtime_id"), str)
            and bool(attestations["runtime_id"].strip())
            and attestations.get("all_passed") is True
            and verified_bundle_complete
            and attestations.get("failures") == {}
        )
        fresh = fresh and source_bound

        deriv = report.get("deriv")
        if (
            not isinstance(deriv, dict)
            or not isinstance(capital, CapitalSnapshot)
            or not capital.is_valid()
            or capital.account.account_type != "real"
            or capital.account.environment != "real"
            or deriv.get("account_loginid") != capital.account.loginid
            or str(deriv.get("currency", "")).strip().upper() != capital.currency.strip().upper()
            or str(deriv.get("environment", "")).strip().lower() != "real"
            or deriv.get("balance_fresh") is not True
            or not isinstance(deriv.get("balance"), (int, float))
            or isinstance(deriv.get("balance"), bool)
            or not isfinite(float(deriv.get("balance", float("nan"))))
            or abs(float(deriv.get("balance", float("nan"))) - float(capital.available_balance)) > 0.01
        ):
            fresh = False

        controls = report.get("controls")
        evidence = report.get("evidence")
        if not isinstance(controls, dict) or not isinstance(evidence, dict):
            return denied

        calibration_ok = evidence.get("calibration") is True
        live_ok = (
            isinstance(report.get("live_execution"), str)
            and report["live_execution"].strip().upper() == "ENABLED"
        )
        return {
            "risk_approved": controls.get("risk_warden") is True and fresh,
            "firewall_approved": controls.get("execution_firewall") is True and fresh,
            "reconciliation_healthy": controls.get("reconciliation") is True and fresh,
            "final_execution_authorization": report.get("final_execution_authorization") is True and fresh,
            "live_trading_enabled": live_ok and fresh,
            "probability_calibrated": calibration_ok and fresh,
            "probability_fresh": calibration_ok and fresh,
            "probability_drift_ok": calibration_ok and fresh,
            "market_data_validated": evidence.get("market_data") is True and fresh,
            "exposure_approved": controls.get("exposure") is True and fresh,
        }


def load_federated_proposal_parameters(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload", {})
    params = payload.get("proposal_parameters")
    if not isinstance(params, dict):
        raise RuntimeError("PROPOSAL_PARAMETERS_NOT_PRESENT")
    required = ("contract_type", "currency", "underlying_symbol")
    missing = [key for key in required if not params.get(key)]
    if missing:
        raise RuntimeError("PROPOSAL_PARAMETERS_MISSING:" + ",".join(missing))
    return dict(params)


def decision_digest(decision: Decision) -> str:
    return sha256(json.loads(canonical_json(decision.__dict__)))
