from __future__ import annotations

import asyncio
import json
import os
from time import perf_counter
from math import isfinite
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from runtime.core.authority import GateResult, authorization_gate, build_intent
from runtime.core.events import event_envelope, sha256
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
from runtime.core.stake_sizing import DEFAULT_MAX_TRADE_RISK_FRACTION
from runtime.core.operator_reset import read_operator_reset_record, verify_operator_reset_record
from runtime.core.secrets import get_optional_secret


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
        max_trade_risk_pct: float = DEFAULT_MAX_TRADE_RISK_FRACTION,
        kill_switch_state_path: Path | str | None = None,
        operator_reset_path: Path | str | None = None,
        operator_reset_signing_key: str | None = None,
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
        self._kill_switch_state_path = (
            Path(kill_switch_state_path) if kill_switch_state_path is not None else None
        )
        self._operator_reset_path = (
            Path(operator_reset_path)
            if operator_reset_path is not None
            else Path(os.getenv(
                "AURELIA_OPERATOR_RESET_PATH",
                "/run/aurelia/operator-kill-switch-reset.json",
            ))
        )
        self._operator_reset_signing_key = (
            operator_reset_signing_key
            if operator_reset_signing_key is not None
            else get_optional_secret("AURELIA_OPERATOR_RESET_SIGNING_KEY")
        )
        self._kill_switch_reason = "STARTUP_LOCKED"
        self._kill_switch_generation = 0
        self._fault_source_sha: str | None = None
        self._last_reset_nonce: str | None = None
        self._startup_clearance_pending = True
        self._fault_latched = False
        self._kill_switch_state_store_failed = False
        self._execution_lock = asyncio.Lock()
        self.latency = LatencyMetrics()
        self.circuit_breaker = CircuitBreaker()
        # Proposal metadata is capability state: one bound quote, one exact
        # decision/stake binding, one authorized submission. It is never inferred
        # from proposal_id alone.
        self._proposal_bindings: dict[str, dict] = {}
        self._consumed_proposal_ids: set[str] = set()
        self._proposal_max_age_seconds = 30.0
        if self._kill_switch_state_path is not None:
            self._load_kill_switch_state()

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

    def _persist_kill_switch_state(self, state: str) -> bool:
        path = self._kill_switch_state_path
        if path is None:
            return True
        payload = {
            "schema": "aurelia.kill_switch_state.v1",
            "state": state,
            "reason": self._kill_switch_reason,
            "generation": self._kill_switch_generation,
            "activated_at_utc": (
                self._kill_switch_activated_at.isoformat()
                if self._kill_switch_activated_at is not None else None
            ),
            "last_reset_nonce": self._last_reset_nonce,
            "source_sha": self.source_hash,
            "fault_source_sha": (
                self._fault_source_sha
                or (self.source_hash if state == "TRIPPED" else None)
            ),
            "updated_at_utc": utc_now().isoformat(),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_text(
                json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
            return True
        except (OSError, TypeError, ValueError):
            self._kill_switch_state_store_failed = True
            return False

    def _load_kill_switch_state(self) -> None:
        path = self._kill_switch_state_path
        if path is None:
            return
        if not path.exists():
            self._kill_switch_reason = "STARTUP_LOCKED"
            self._startup_clearance_pending = True
            if not self._persist_kill_switch_state("STARTUP_LOCKED"):
                self.kill_switch = True
                self._fault_latched = True
                self._startup_clearance_pending = False
                self._kill_switch_reason = "KILL_SWITCH_STATE_PERSISTENCE_FAILED"
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if (
                not isinstance(data, dict)
                or data.get("schema") != "aurelia.kill_switch_state.v1"
                or data.get("state") not in {"STARTUP_LOCKED", "TRIPPED", "CLEARED"}
                or isinstance(data.get("generation"), bool)
                or not isinstance(data.get("generation"), int)
                or data["generation"] < 0
            ):
                raise ValueError("KILL_SWITCH_STATE_SCHEMA_INVALID")
            self._kill_switch_generation = data["generation"]
            self._last_reset_nonce = (
                data.get("last_reset_nonce")
                if isinstance(data.get("last_reset_nonce"), str) else None
            )
            if data.get("state") == "TRIPPED":
                fault_source = data.get("fault_source_sha") or data.get("source_sha")
                if not isinstance(fault_source, str) or not fault_source.strip():
                    raise ValueError("KILL_SWITCH_FAULT_SOURCE_SHA_MISSING")
                self._fault_source_sha = fault_source.strip()
                self._kill_switch_reason = str(data.get("reason") or "KILL_SWITCH_STATE_REASON_MISSING")
                activated = datetime.fromisoformat(
                    str(data.get("activated_at_utc") or "").replace("Z", "+00:00")
                )
                if activated.tzinfo is None:
                    raise ValueError("KILL_SWITCH_ACTIVATION_TIMEZONE_INVALID")
                self._kill_switch_activated_at = activated
                self.kill_switch = True
                self._fault_latched = True
                self._startup_clearance_pending = False
                return

            # Every process restart relocks execution. A previous clean stop or
            # startup lock requires a new full startup authorization; a prior
            # TRIPPED state remains latched until explicitly reset.
            self._kill_switch_reason = "STARTUP_LOCKED"
            self._fault_source_sha = None
            self._kill_switch_activated_at = utc_now()
            self.kill_switch = True
            self._fault_latched = False
            self._startup_clearance_pending = True
            if not self._persist_kill_switch_state("STARTUP_LOCKED"):
                self._fault_latched = True
                self._startup_clearance_pending = False
                self._kill_switch_reason = "KILL_SWITCH_STATE_PERSISTENCE_FAILED"
        except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
            self.kill_switch = True
            self._kill_switch_generation = max(1, self._kill_switch_generation + 1)
            self._kill_switch_reason = "KILL_SWITCH_STATE_CORRUPT"
            self._fault_source_sha = self.source_hash
            self._kill_switch_activated_at = utc_now()
            self._fault_latched = True
            self._startup_clearance_pending = False
            if not self._persist_kill_switch_state("TRIPPED"):
                self._kill_switch_state_store_failed = True

    def activate_kill_switch(self, reason: str) -> None:
        normalized_reason = str(reason or "UNSPECIFIED_KILL_SWITCH_REASON")
        new_fault = not self._fault_latched
        changed_fault = self._fault_latched and normalized_reason != self._kill_switch_reason
        if new_fault or changed_fault:
            self._kill_switch_generation += 1
            self._kill_switch_reason = normalized_reason
            self._fault_source_sha = self.source_hash
            self._kill_switch_activated_at = utc_now()
        self.kill_switch = True
        self._startup_clearance_pending = False
        self._fault_latched = True
        self.fence.revoke()
        self._persist_kill_switch_state("TRIPPED")
        if self.state.state not in {RuntimeState.CAPITAL_PROTECTED, RuntimeState.SHUTDOWN}:
            try:
                self.state.transition(RuntimeState.CAPITAL_PROTECTED)
            except ValueError:
                pass
        self._log("KILL_SWITCH_ACTIVATED", {
            "reason": self._kill_switch_reason,
            "trigger_reason": normalized_reason,
            "generation": self._kill_switch_generation,
            "new_incident": bool(new_fault or changed_fault),
            "persistent_state_ok": not self._kill_switch_state_store_failed,
        })

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
        unresolved = self.unresolved_unknown_intents()
        if unresolved is None or unresolved:
            self._log(
                "KILL_SWITCH_CLEAR_BLOCKED",
                {
                    "reason": "UNRESOLVED_BROKER_OUTCOME" if unresolved else "IDEMPOTENCY_STATE_UNKNOWN",
                    "unresolved_count": len(unresolved) if unresolved is not None else None,
                },
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
                authorization.account.environment == "real",
                authorization.capital.is_valid(),
                authorization.capital.account == authorization.account,
                authorization.capital.account.environment == "real",
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
        if self._kill_switch_state_store_failed:
            self._log(
                "KILL_SWITCH_CLEAR_BLOCKED",
                {"reason": "KILL_SWITCH_STATE_PERSISTENCE_FAILED"},
            )
            return False

        if self._fault_latched:
            record = read_operator_reset_record(self._operator_reset_path)
            valid, reason, nonce = verify_operator_reset_record(
                record or {},
                signing_key=self._operator_reset_signing_key,
                expected_reason=self._kill_switch_reason,
                expected_source_sha=self.source_hash,
                expected_fault_source_sha=self._fault_source_sha or self.source_hash,
                expected_account_loginid=authorization.account.loginid,
                expected_generation=self._kill_switch_generation,
                last_consumed_nonce=self._last_reset_nonce,
            )
            if not valid or nonce is None:
                self._log(
                    "KILL_SWITCH_CLEAR_BLOCKED",
                    {"reason": reason, "generation": self._kill_switch_generation},
                )
                return False
            # Persist the nonce before consuming the file. A crash after this
            # write still prevents replay of the same proof on restart.
            self._last_reset_nonce = nonce
            if not self._persist_kill_switch_state("TRIPPED"):
                self._log(
                    "KILL_SWITCH_CLEAR_BLOCKED",
                    {"reason": "KILL_SWITCH_STATE_PERSISTENCE_FAILED"},
                )
                return False
            try:
                consumed = self._operator_reset_path.with_name(
                    self._operator_reset_path.name + ".consumed." + nonce
                )
                self._operator_reset_path.replace(consumed)
            except OSError:
                self._log(
                    "KILL_SWITCH_CLEAR_BLOCKED",
                    {"reason": "OPERATOR_RESET_PROOF_COULD_NOT_BE_CONSUMED"},
                )
                return False

        self.kill_switch = False
        self._fault_latched = False
        self._startup_clearance_pending = False
        self._kill_switch_reason = "CLEARED"
        self._fault_source_sha = None
        if not self._persist_kill_switch_state("CLEARED"):
            self.kill_switch = True
            self._fault_latched = True
            self._startup_clearance_pending = False
            self._kill_switch_reason = "KILL_SWITCH_STATE_PERSISTENCE_FAILED"
            self._fault_source_sha = self.source_hash
            self._persist_kill_switch_state("TRIPPED")
            self._log(
                "KILL_SWITCH_CLEAR_BLOCKED",
                {"reason": "KILL_SWITCH_STATE_PERSISTENCE_FAILED"},
            )
            return False
        self._log(
            "KILL_SWITCH_CLEARED",
            {
                "authorization_id": authorization.authorization_id,
                "operator_reset_consumed": bool(self._last_reset_nonce),
            },
        )
        return True

    def release_allows_live(self) -> bool:
        return read_live_release(self.live_lock_path).may_move_capital

    def unresolved_unknown_intents(self) -> tuple[str, ...] | None:
        """Return unresolved broker outcomes, or None when the store cannot prove state."""
        reader = getattr(self.idempotency, "unresolved_unknown_intents", None)
        if not callable(reader):
            return None
        try:
            values = reader()
            if not isinstance(values, (tuple, list)) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                return None
            return tuple(sorted(set(values)))
        except Exception:
            return None

    async def verify_no_open_positions(self) -> str | None:
        """Fail closed unless the broker positively confirms there are no open positions.

        A known non-empty portfolio blocks only new exposure. Missing interfaces,
        malformed replies, and transport failures are UNKNOWN and trip the kill
        switch at the calling execution boundary.
        """
        reader = getattr(self.broker, "portfolio", None)
        if not callable(reader):
            return "PORTFOLIO_STATE_UNAVAILABLE"
        try:
            positions = await reader()
        except Exception:
            return "PORTFOLIO_STATE_UNAVAILABLE"
        if not isinstance(positions, (list, tuple)):
            return "PORTFOLIO_STATE_INVALID"
        if positions:
            return "OPEN_POSITIONS_PRESENT"
        return None

    async def prepare_proposal(self, parameters: dict) -> str:
        """Fetch and register one exact proposal for a bounded, one-use intent."""
        if not isinstance(parameters, dict):
            raise RuntimeError("PROPOSAL_PARAMETERS_INVALID")
        contract_type = str(parameters.get("contract_type", "")).strip().upper()
        currency = str(parameters.get("currency", "")).strip().upper()
        symbol = str(parameters.get("underlying_symbol", "")).strip()
        basis = str(parameters.get("basis", "")).strip().lower()
        amount = parameters.get("amount")
        try:
            amount_value = float(amount)
        except (TypeError, ValueError, OverflowError):
            amount_value = float("nan")
        if contract_type not in {"CALL", "PUT"}:
            raise RuntimeError("PROPOSAL_CONTRACT_TYPE_INVALID")
        if not currency or not symbol:
            raise RuntimeError("PROPOSAL_SYMBOL_OR_CURRENCY_MISSING")
        if basis != "stake":
            raise RuntimeError("PROPOSAL_BASIS_MUST_BE_STAKE")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not isfinite(amount_value)
            or amount_value <= 0
        ):
            raise RuntimeError("PROPOSAL_AMOUNT_INVALID")
        try:
            parameter_hash = sha256(parameters)
        except (TypeError, ValueError, OverflowError):
            raise RuntimeError("PROPOSAL_PARAMETERS_NOT_HASHABLE") from None

        request_proposal = getattr(self.broker, "request_proposal", None)
        if not callable(request_proposal):
            raise RuntimeError("BROKER_PROPOSAL_INTERFACE_MISSING")
        proposal_id = await request_proposal(parameters)
        proposal_id = str(proposal_id or "").strip()
        if not proposal_id:
            raise RuntimeError("PROPOSAL_ID_MISSING_FROM_BROKER")
        if proposal_id in self._proposal_bindings or proposal_id in self._consumed_proposal_ids:
            raise RuntimeError("BROKER_PROPOSAL_ID_REUSED")
        self._proposal_bindings[proposal_id] = {
            "parameters": dict(parameters),
            "parameters_hash": parameter_hash,
            "created_at": utc_now(),
        }
        self._log("BROKER_PROPOSAL_REGISTERED", {
            "proposal_id": proposal_id,
            "parameters_hash": parameter_hash,
            "symbol": symbol,
            "contract_type": contract_type,
            "currency": currency,
            "basis": basis,
            "amount": amount_value,
            "capital_authority_granted": False,
            "order_submission_permitted": False,
        })
        return proposal_id

    def proposal_binding_hash(self, proposal_id: str | None) -> str | None:
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            return None
        if proposal_id in self._consumed_proposal_ids:
            return None
        binding = self._proposal_bindings.get(proposal_id)
        if not isinstance(binding, dict):
            return None
        created_at = binding.get("created_at")
        if not isinstance(created_at, datetime) or created_at.tzinfo is None:
            return None
        age = (utc_now() - created_at).total_seconds()
        if age < 0 or age > self._proposal_max_age_seconds:
            return None
        value = binding.get("parameters_hash")
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _expected_contract_type(direction: str) -> str | None:
        if not isinstance(direction, str):
            return None
        return {
            "CALL": "CALL", "UP": "CALL", "RISE": "CALL", "BUY": "CALL", "LONG": "CALL",
            "PUT": "PUT", "DOWN": "PUT", "FALL": "PUT", "SELL": "PUT", "SHORT": "PUT",
        }.get(direction.strip().upper())

    def _proposal_binding_error(self, intent: OrderIntent) -> str | None:
        if not intent.proposal_id:
            return "PROPOSAL_ID_MISSING"
        if intent.proposal_id in self._consumed_proposal_ids:
            return "PROPOSAL_ALREADY_CONSUMED"
        binding = self._proposal_bindings.get(intent.proposal_id)
        if not isinstance(binding, dict):
            return "PROPOSAL_BINDING_NOT_REGISTERED"
        bound_hash = self.proposal_binding_hash(intent.proposal_id)
        if bound_hash is None:
            return "PROPOSAL_BINDING_EXPIRED_OR_INVALID"
        if not intent.proposal_parameters_hash or intent.proposal_parameters_hash != bound_hash:
            return "PROPOSAL_PARAMETERS_HASH_MISMATCH"
        parameters = binding.get("parameters")
        if not isinstance(parameters, dict):
            return "PROPOSAL_BINDING_INVALID"
        if str(parameters.get("underlying_symbol", "")).strip() != intent.symbol:
            return "PROPOSAL_SYMBOL_MISMATCH"
        if str(parameters.get("currency", "")).strip().upper() != intent.account.currency.strip().upper():
            return "PROPOSAL_CURRENCY_MISMATCH"
        expected_contract = self._expected_contract_type(intent.direction)
        if expected_contract is None or str(parameters.get("contract_type", "")).strip().upper() != expected_contract:
            return "PROPOSAL_CONTRACT_DIRECTION_MISMATCH"
        if str(parameters.get("basis", "")).strip().lower() != "stake":
            return "PROPOSAL_BASIS_MUST_BE_STAKE"
        amount = parameters.get("amount")
        try:
            amount_value = float(amount)
            intent_stake = float(intent.stake)
        except (TypeError, ValueError, OverflowError):
            return "PROPOSAL_STAKE_MISMATCH"
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not isfinite(amount_value)
            or not isfinite(intent_stake)
            or abs(amount_value - intent_stake) > 1e-9
        ):
            return "PROPOSAL_STAKE_MISMATCH"
        return None

    def _consume_proposal_binding(self, intent: OrderIntent) -> str | None:
        """Atomically consume a verified proposal so it cannot authorize a second buy."""
        error = self._proposal_binding_error(intent)
        if error:
            return error
        proposal_id = intent.proposal_id
        if proposal_id is None:
            return "PROPOSAL_ID_MISSING"
        self._proposal_bindings.pop(proposal_id, None)
        self._consumed_proposal_ids.add(proposal_id)
        return None

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
        broker_minimum_stake: float | None = None,
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
        if mode == "LIVE":
            unresolved = self.unresolved_unknown_intents()
            if unresolved is None or unresolved:
                reason = "UNRESOLVED_BROKER_OUTCOME" if unresolved else "IDEMPOTENCY_STATE_UNKNOWN"
                return GateResult(False, (reason,)), None, None

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
            broker_minimum_stake=broker_minimum_stake,
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
        proposal_hash = None
        if mode == "LIVE":
            proposal_hash = self.proposal_binding_hash(proposal_id)
            if proposal_hash is None:
                failed = GateResult(False, ("PROPOSAL_BINDING_NOT_AVAILABLE",))
                return failed, None, None
        intent = build_intent(
            ctx,
            proposal_id=proposal_id,
            mode=mode,
            proposal_parameters_hash=proposal_hash,
        )
        if mode == "LIVE":
            binding_error = self._proposal_binding_error(intent)
            if binding_error:
                return GateResult(False, (binding_error,)), None, None
        return gate, ctx, intent

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
        broker_minimum_stake: float | None = None,
    ) -> tuple[GateResult, AuthorizationContext | None]:
        """Evaluate a fresh live control chain before clearing the startup kill switch."""
        release = read_live_release(self.live_lock_path)
        if not release.may_move_capital:
            return GateResult(
                False,
                ("LIVE_RELEASE_NOT_ENABLED", "CAPITAL_PLANE_VERIFY_ONLY"),
            ), None
        unresolved = self.unresolved_unknown_intents()
        if unresolved is None or unresolved:
            reason = "UNRESOLVED_BROKER_OUTCOME" if unresolved else "IDEMPOTENCY_STATE_UNKNOWN"
            return GateResult(False, (reason,)), None

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
            execution_mode="LIVE",
            broker_minimum_stake=broker_minimum_stake,
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

        # Any previous UNKNOWN broker outcome is account-global: a new intent
        # cannot proceed merely because its id differs from the unresolved one.
        same_record = self.idempotency.get(intent.intent_id)
        if same_record is not None and same_record.broker_transaction_id:
            return ExecutionOutcome(
                True, "ALREADY_ACCEPTED", (), intent.intent_id,
                same_record.broker_transaction_id,
            )
        if same_record is not None and same_record.broker_outcome_unknown:
            return ExecutionOutcome(
                False, "RECOVERY_REQUIRED",
                ("BROKER_OUTCOME_UNKNOWN_REQUIRES_RECONCILIATION",),
                intent.intent_id,
            )
        binding_error = self._proposal_binding_error(intent)
        if binding_error:
            self._log("PROPOSAL_BINDING_BLOCKED", {
                "intent_id": intent.intent_id,
                "proposal_id": intent.proposal_id,
                "reason": binding_error,
                "capital_authority_granted": False,
                "order_submission_permitted": False,
            })
            self.activate_kill_switch(binding_error)
            return ExecutionOutcome(False, "BLOCKED", (binding_error,), intent.intent_id)
        unresolved = self.unresolved_unknown_intents()
        if unresolved is None:
            self.activate_kill_switch("IDEMPOTENCY_STATE_UNKNOWN")
            return ExecutionOutcome(
                False, "RECOVERY_REQUIRED", ("IDEMPOTENCY_STATE_UNKNOWN",), intent.intent_id
            )
        if unresolved:
            self.activate_kill_switch("UNRESOLVED_BROKER_OUTCOME")
            return ExecutionOutcome(
                False, "RECOVERY_REQUIRED",
                ("UNRESOLVED_BROKER_OUTCOME",),
                intent.intent_id,
            )

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

        # The risk budget is based on verified available funds, not gross
        # balance. Gross balance can include funds not available for new exposure.
        # This policy is only valid for stake-basis purchased contracts.
        permitted_loss = fresh_balance.available_balance * self.max_trade_risk_pct
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

        portfolio_block = await self.verify_no_open_positions()
        if portfolio_block:
            self._log(
                "PRE_SUBMISSION_BLOCKED",
                {
                    "intent_id": intent.intent_id,
                    "reasons": (portfolio_block,),
                    "new_exposure_permitted": False,
                },
            )
            if portfolio_block != "OPEN_POSITIONS_PRESENT":
                self.activate_kill_switch(portfolio_block)
                return ExecutionOutcome(
                    False, "RECOVERY_REQUIRED", (portfolio_block,), intent.intent_id
                )
            return ExecutionOutcome(False, "BLOCKED", (portfolio_block,), intent.intent_id)

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

        binding_error = self._consume_proposal_binding(intent)
        if binding_error:
            self.activate_kill_switch(binding_error)
            self._log("PROPOSAL_BINDING_BLOCKED", {
                "intent_id": intent.intent_id,
                "proposal_id": intent.proposal_id,
                "reason": binding_error,
                "capital_authority_granted": False,
                "order_submission_permitted": False,
            })
            return ExecutionOutcome(False, "BLOCKED", (binding_error,), intent.intent_id)

        self._log(
            "INTENT_CREATED",
            {
                "intent_id": intent.intent_id,
                "decision_id": intent.decision_id,
                "stake": intent.stake,
                "proposal_id": intent.proposal_id,
                "proposal_parameters_hash": intent.proposal_parameters_hash,
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
            self.activate_kill_switch("BROKER_SUBMISSION_OUTCOME_UNKNOWN")
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
            self.activate_kill_switch("BROKER_OUTCOME_UNKNOWN")
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
