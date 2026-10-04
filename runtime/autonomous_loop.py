from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
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
    RuntimeState,
    utc_now,
)
from runtime.core.release_gate import read_live_release


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
    ) -> None:
        self.adapter = adapter
        self.executor = executor
        self.decision_provider = decision_provider
        self.runtime_config_hash = runtime_config_hash
        self.fence_owner = fence_owner
        self.symbols = symbols
        self.lifecycle_timeout_seconds = lifecycle_timeout_seconds
        self.tick_timeout_seconds = tick_timeout_seconds
        self._stop = asyncio.Event()
        self._fence: FenceToken | None = None
        self.trades_attempted = 0
        self.trades_accepted = 0

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
    ) -> tuple[AuthorizationContext | None, Any | None]:
        # First obtain a fresh control-chain authorization solely to clear the
        # startup kill switch; then immediately rebuild the final intent after
        # the switch is clear. This avoids a circular "kill-switch must already
        # be off" requirement while preserving the fresh-authorization rule.
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
            mode="LIVE",
        )

    async def _settle_and_reconcile(
        self,
        *,
        intent: Any,
        prior_capital: CapitalSnapshot,
        contract_id: str,
    ) -> LifecycleResult:
        final_contract: dict[str, Any] | None = None
        try:
            async with asyncio.timeout(self.lifecycle_timeout_seconds):
                async for status in monitor_contract(self.adapter, contract_id):
                    final_contract = status
        except TimeoutError:
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

        if final_contract is None:
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

        post_balance = await self.adapter.get_balance()
        reconciliation = await self.executor.reconcile(
            broker_capital=post_balance,
            prior_authoritative_balance=prior_capital.available_balance,
            explainable_delta=net_delta,
        )
        self.executor.ledger.post(
            __import__("runtime.core.models", fromlist=["LedgerEvent"]).LedgerEvent(
                event_id=f"settlement:{intent.intent_id}",
                intent_id=intent.intent_id,
                account=intent.account,
                event_type="CONTRACT_SETTLED",
                amount=net_delta,
                currency=intent.account.currency,
                occurred_at=utc_now(),
                broker_transaction_id=None,
                metadata={
                    "contract_id": contract_id,
                    "post_balance": post_balance.available_balance,
                    "broker_profit": final_contract.get("profit"),
                    "broker_payout": final_contract.get("payout"),
                },
            )
        )
        if not reconciliation.healthy:
            self.executor.activate_kill_switch("POST_TRADE_RECONCILIATION_MISMATCH")

        return LifecycleResult(
            intent.intent_id,
            "SETTLED" if reconciliation.healthy else "RECOVERY_REQUIRED",
            None,
            contract_id,
            True,
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
        if self._fence is None or not self.executor.fence.valid(self._fence):
            self._fence = self.executor.fence.acquire(self.fence_owner)

        parameters = self.decision_provider.proposal_parameters(
            decision=decision,
            capital=capital,
            account=account,
        )
        proposal_id = await self.executor.prepare_proposal(parameters)
        ctx, intent = await self._prepare_live_intent(
            decision=decision,
            capital=capital,
            account=account,
            controls=controls,
        )
        if ctx is None or intent is None:
            return ExecutionOutcome(False, "BLOCKED", ("LIVE_AUTHORIZATION_NOT_AVAILABLE",), f"intent:{decision.decision_id}")

        if intent.proposal_id is None:
            raise RuntimeError("PROPOSAL_ID_NOT_BOUND_TO_INTENT")

        outcome = await self.executor.execute(intent, ctx, self._fence)
        if not outcome.allowed:
            if outcome.status == "RECOVERY_REQUIRED":
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

        # The executor's accepted result does not carry the contract ID in its
        # public outcome. Recover it from the broker portfolio/statement using
        # the transaction ID rather than guessing.
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

        while not self._stop.is_set():
            tasks = [asyncio.create_task(it.__anext__()) for it in iterators]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                try:
                    tick = task.result()
                except StopAsyncIteration:
                    continue
                capital = await self.adapter.get_balance()
                if (utc_now() - tick.received_at).total_seconds() > 5:
                    self.executor.activate_kill_switch("MARKET_DATA_STALE")
                    continue

                decision = await self.decision_provider.next_decision(
                    tick=tick,
                    capital=capital,
                    account=capital.account,
                )
                if decision is None:
                    continue

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
                    if isinstance(result, LifecycleResult) and result.reconciliation_healthy:
                        self.executor.kill_switch = True
                        self.executor._kill_switch_activated_at = utc_now()
                except Exception:
                    self.executor.activate_kill_switch("AUTONOMOUS_LOOP_EXCEPTION")

    def stop(self) -> None:
        self._stop.set()


class FederatedDecisionProvider:
    """Turns durable agent DECISION_PROPOSAL messages into Decisions.

    Agents can propose; only the capital plane can authorize and submit.
    """

    def __init__(self, federation, *, consumer: str = "AURELIA") -> None:
        self.federation = federation
        self.consumer = consumer
        self._seen: set[str] = set()

    async def next_decision(self, *, tick, capital, account):
        messages = self.federation.messages_for(self.consumer, limit=100)
        for message in messages:
            if message.get("message_type") != "DECISION_PROPOSAL":
                continue
            message_id = str(message.get("message_id", ""))
            if not message_id or message_id in self._seen:
                continue
            payload = message.get("payload", {})
            if str(payload.get("account_loginid", account.loginid)) != account.loginid:
                continue
            if str(payload.get("symbol", tick.symbol)) != tick.symbol:
                continue
            try:
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
                )
            except (KeyError, TypeError, ValueError):
                self._seen.add(message_id)
                continue
            self._seen.add(message_id)
            return decision
        return None

    def proposal_parameters(self, *, decision, capital, account):
        # Agents must provide the complete broker proposal terms. The loop does
        # not invent a contract type, duration, barrier, or multiplier.
        raise RuntimeError(
            "DECISION_PROPOSAL_MUST_INCLUDE_BROKER_PARAMETERS"
        )

    def control_snapshot(self, *, decision, tick, capital):
        return {
            "risk_approved": False,
            "firewall_approved": False,
            "reconciliation_healthy": False,
            "final_execution_authorization": False,
            "live_trading_enabled": False,
            "probability_calibrated": False,
            "probability_fresh": False,
            "probability_drift_ok": False,
            "market_data_validated": False,
            "exposure_approved": False,
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
