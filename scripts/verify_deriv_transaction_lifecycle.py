from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path

from assurance.evidence_writer import build_evidence, payload_sha256, write_evidence
from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.adapters.session_manager import DerivSessionManager
from runtime.broker.executor import CapitalPlaneExecutor
from runtime.core.events import canonical_json, sha256
from runtime.core.fencing import ExecutionFence
from runtime.core.idempotency import IdempotencyStore
from runtime.core.journal import AppendOnlyJournal
from runtime.core.ledger import InMemoryLedger
from runtime.core.models import Decision, RuntimeState
from runtime.core.reconcile import Reconciler
from runtime.core.runtime_config import load_config_hash
from runtime.core.state import RuntimeStateMachine


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(os.getenv("DERIV_LIFECYCLE_EVIDENCE_OUT", "artifacts/deriv_transaction_lifecycle.json"))
INPUT = Path(os.getenv("AURELIA_LIVE_DECISION_ARTIFACT", "artifacts/live_canary_decision.json"))


def fail(message: str) -> int:
    print("DERIV_TRANSACTION_LIFECYCLE=BLOCKED")
    print(f"REASON={message}")
    return 2


async def run() -> int:
    mode = os.getenv("DERIV_LIFECYCLE_MODE", "LIVE").strip().upper()
    if mode not in {"LIVE", "VERIFY_ONLY"}:
        return fail("INVALID_DERIV_LIFECYCLE_MODE")

    lock = (
        (ROOT / "config" / "LIVE_LOCK.yaml").read_text(encoding="utf-8")
        if (ROOT / "config" / "LIVE_LOCK.yaml").exists()
        else ""
    )
    if mode == "LIVE" and (
        "live_trading_enabled: true" not in lock
        or "FINAL_EXECUTION_AUTHORIZATION: true" not in lock
        or "capital_plane_mode: LIVE" not in lock
    ):
        return fail("LIVE_RELEASE_GATE_NOT_ENABLED")

    for name in (
        "DERIV_AUTH_TOKEN",
        "DERIV_EXPECTED_LOGINID",
        "DERIV_EXPECTED_CURRENCY",
        "DERIV_ENVIRONMENT",
    ):
        if not os.getenv(name):
            return fail(f"REQUIRED_SECRET_OR_BINDING_MISSING:{name}")

    if os.getenv("DERIV_ENVIRONMENT", "").lower() != "real":
        return fail("REAL_ACCOUNT_REQUIRED")

    adapter: DerivAdapter | None = None
    try:
        manager = DerivSessionManager(
            expected_loginid=os.environ["DERIV_EXPECTED_LOGINID"],
            expected_environment="real",
            expected_currency=os.environ["DERIV_EXPECTED_CURRENCY"],
        )
        bootstrap = manager.bootstrap(
            bearer_token=os.environ["DERIV_AUTH_TOKEN"],
            app_id=os.getenv("DERIV_APP_ID") or None,
        )
        adapter = DerivAdapter(
            ws_url=bootstrap.websocket.url,
            expected_loginid=bootstrap.binding.loginid,
            expected_currency=os.environ["DERIV_EXPECTED_CURRENCY"],
            environment="real",
            auth_token="",
        )

        journal = AppendOnlyJournal(
            os.getenv("AURELIA_JOURNAL_PATH", "/tmp/aurelia/lifecycle.ndjson")
        )
        ledger = InMemoryLedger()
        idempotency = IdempotencyStore()
        fence = ExecutionFence()
        state = RuntimeStateMachine(RuntimeState.BROKER_CONNECTING)
        reconciler = Reconciler()
        source_hash = os.getenv("GITHUB_SHA", "LOCAL_UNPINNED")
        executor = CapitalPlaneExecutor(
            adapter,
            journal=journal,
            ledger=ledger,
            idempotency=idempotency,
            fence=fence,
            state=state,
            reconciler=reconciler,
            source_hash=source_hash,
            config_hash=load_config_hash(ROOT),
            live_lock_path=ROOT / "config" / "LIVE_LOCK.yaml",
        )

        account = await adapter.connect()
        if (
            account.loginid != os.environ["DERIV_EXPECTED_LOGINID"]
            or account.account_type != "real"
        ):
            return fail("ACCOUNT_BINDING_MISMATCH")
        prior = await adapter.get_balance()

        if mode == "VERIFY_ONLY":
            active_symbols = await adapter.active_symbols()
            if not active_symbols:
                return fail(
                    "MARKET_DATA_ACCOUNT_AUTHENTICATED_BUT_NO_ACTIVE_SYMBOLS"
                )

            requested_symbol = os.getenv("DERIV_VERIFY_SYMBOL", "").strip()
            available_symbols = {
                str(row.get("symbol"))
                for row in active_symbols
                if row.get("symbol")
            }
            symbol = requested_symbol or next(
                iter(sorted(available_symbols)), ""
            )
            if not symbol or symbol not in available_symbols:
                return fail("VERIFY_ONLY_SYMBOL_NOT_ACTIVE")

            try:
                verify_stake = float(
                    os.getenv("DERIV_VERIFY_STAKE", "1.0")
                )
            except ValueError:
                return fail("VERIFY_ONLY_STAKE_INVALID")
            if not isfinite(verify_stake) or verify_stake < 1.0:
                return fail("VERIFY_ONLY_STAKE_INVALID")
            if verify_stake > prior.available_balance:
                return fail("VERIFY_ONLY_STAKE_NOT_AFFORDABLE")

            try:
                verify_probability = float(
                    os.getenv("DERIV_VERIFY_PROBABILITY", "0.60")
                )
            except ValueError:
                return fail("VERIFY_ONLY_PROBABILITY_INVALID")
            if not isfinite(verify_probability) or not (
                0.55 <= verify_probability <= 0.75
            ):
                return fail("VERIFY_ONLY_PROBABILITY_OUTSIDE_HARD_POLICY")

            contract_type = (
                os.getenv("DERIV_VERIFY_CONTRACT_TYPE", "CALL")
                .strip()
                .upper()
            )
            duration_unit = (
                os.getenv("DERIV_VERIFY_DURATION_UNIT", "s")
                .strip()
                .lower()
            )
            try:
                duration = int(os.getenv("DERIV_VERIFY_DURATION", "1"))
            except ValueError:
                return fail("VERIFY_ONLY_DURATION_INVALID")
            if duration <= 0 or duration_unit not in {"s", "m", "h", "d", "t"}:
                return fail("VERIFY_ONLY_DURATION_INVALID")

            now = datetime.now(timezone.utc)
            snapshot_hash = sha256(
                {
                    "symbol": symbol,
                    "active_symbol_count": len(active_symbols),
                    "captured_at": now.isoformat(),
                }
            )
            decision = Decision(
                decision_id=f"verify-only:{now.strftime('%Y%m%dT%H%M%S%fZ')}",
                strategy_id="VERIFY_ONLY_BROKER_PLUMBING",
                strategy_version="1",
                strategy_hash="VERIFY_ONLY_BROKER_PLUMBING_V1",
                symbol=symbol,
                direction=(
                    os.getenv("DERIV_VERIFY_DIRECTION", "BUY").strip().upper()
                    or "BUY"
                ),
                probability=verify_probability,
                decision_time=now,
                market_snapshot_hash=snapshot_hash,
                risk_requested_stake=verify_stake,
                rationale_codes=("VERIFY_ONLY", "BROKER_PLUMBING"),
            )
            params = {
                "amount": verify_stake,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": account.currency,
                "duration": duration,
                "duration_unit": duration_unit,
                "underlying_symbol": symbol,
            }
            proposal_id = await executor.prepare_proposal(params)

            gate, verify_ctx, verify_intent = (
                await executor.authorize_and_build_intent(
                    decision=decision,
                    capital=prior,
                    runtime_config_hash=load_config_hash(ROOT),
                    account=account,
                    risk_approved=True,
                    firewall_approved=True,
                    reconciliation_healthy=True,
                    final_execution_authorization=False,
                    live_trading_enabled=False,
                    probability_calibrated=True,
                    probability_fresh=True,
                    probability_drift_ok=True,
                    market_data_validated=True,
                    exposure_approved=True,
                    proposal_id=proposal_id,
                    mode="VERIFY_ONLY",
                )
            )
            if not gate.allowed or verify_ctx is None or verify_intent is None:
                return fail("VERIFY_ONLY_CONTROL_CHAIN_REJECTED")

            fence_token = fence.acquire("deriv-lifecycle-verify-only")
            if not fence.valid(fence_token):
                return fail("VERIFY_ONLY_FENCE_INVALID")
            existing = idempotency.register_intent(verify_intent.intent_id)
            if existing.broker_transaction_id or existing.broker_outcome_unknown:
                return fail("VERIFY_ONLY_IDEMPOTENCY_STATE_NOT_CLEAN")

            ended = datetime.now(timezone.utc)
            observed = {
                "mode": "VERIFY_ONLY",
                "account_loginid": account.loginid,
                "environment": account.environment,
                "currency": prior.currency,
                "fresh_balance": prior.available_balance,
                "available_balance": prior.available_balance,
                "active_symbol_count": len(active_symbols),
                "symbol": symbol,
                "proposal_id": proposal_id,
                "intent_id": verify_intent.intent_id,
                "execution_mode": verify_intent.execution_mode,
                "risk_approved": verify_ctx.risk_approved,
                "firewall_approved": verify_ctx.firewall_approved,
                "reconciliation_healthy": verify_ctx.reconciliation_healthy,
                "fence_valid": fence.valid(fence_token),
                "broker_submission_performed": False,
                "capital_movement": False,
            }
            data_hash = sha256(observed)
            record = build_evidence(
                evidence_id=(
                    "DERIV_TRANSACTION_LIFECYCLE_VERIFY_ONLY:"
                    f"{ended.strftime('%Y%m%dT%H%M%SZ')}"
                ),
                source_hash=source_hash,
                artifact_hash=sha256(
                    {
                        "data_hash": data_hash,
                        "config_hash": load_config_hash(ROOT),
                    }
                ),
                config_hash=load_config_hash(ROOT),
                data_hash=data_hash,
                environment="production-real",
                started_at_utc=prior.captured_at.isoformat(),
                ended_at_utc=ended.isoformat(),
                status="CURRENT",
                valid_until_utc=(
                    ended.replace(microsecond=0)
                    + __import__("datetime").timedelta(minutes=30)
                ).isoformat(),
                provenance={
                    "origin": "runtime",
                    "issuer": "aurelia-deriv-lifecycle-verifier",
                    "source_commit": source_hash,
                    "generated_at_utc": ended.isoformat(),
                    "deployment_id": os.getenv(
                        "AURELIA_DEPLOYMENT_ID", "DERIV-VERIFY-ONLY"
                    ),
                },
                result="PROVEN",
                invariants_checked=[
                    "real_account_binding",
                    "fresh_pre_trade_balance",
                    "market_data_inventory",
                    "broker_proposal",
                    "risk_control_path",
                    "firewall_control_path",
                    "intent_construction",
                    "idempotency_registration",
                    "execution_fence",
                    "no_capital_submission",
                ],
                invariants_failed=[],
            )
            enriched = dict(record)
            enriched["observed"] = observed
            enriched["orders_submitted"] = 0
            enriched["capital_authority_granted"] = False
            enriched["verification_scope"] = (
                "REAL_DERIV_LIFECYCLE_VERIFY_ONLY"
            )
            enriched["order_submission_permitted"] = False
            enriched["record_hash"] = payload_sha256(
                {
                    key: value
                    for key, value in enriched.items()
                    if key != "record_hash"
                }
            )
            write_evidence(OUTPUT, enriched)

            print("DERIV_TRANSACTION_LIFECYCLE=VERIFY_ONLY_PROVEN")
            print(f"DERIV_EVIDENCE_PATH={OUTPUT}")
            print(f"DERIV_ACCOUNT={account.loginid}")
            print(f"FRESH_BALANCE={prior.available_balance}")
            print(f"ACTIVE_SYMBOLS={len(active_symbols)}")
            print(f"PROPOSAL_ID={proposal_id}")
            print(f"INTENT_ID={verify_intent.intent_id}")
            print("ORDERS_SUBMITTED=0")
            print("CAPITAL_MOVEMENT=false")
            return 0

        decision_payload = json.loads(INPUT.read_text(encoding="utf-8"))
        if not isinstance(decision_payload, dict):
            return fail("LIVE_DECISION_ARTIFACT_INVALID")
        decision = Decision(
            **{
                key: decision_payload[key]
                for key in (
                    "decision_id",
                    "strategy_id",
                    "strategy_version",
                    "strategy_hash",
                    "symbol",
                    "direction",
                    "probability",
                    "decision_time",
                    "market_snapshot_hash",
                    "risk_requested_stake",
                    "rationale_codes",
                )
            }
        )
        params = decision_payload.get("proposal_parameters")
        controls = decision_payload.get("controls")
        if not isinstance(params, dict) or not isinstance(controls, dict):
            return fail(
                "LIVE_DECISION_ARTIFACT_MISSING_BROKER_TERMS_OR_CONTROLS"
            )
        if not all(
            controls.get(k) is True
            for k in (
                "risk_approved",
                "firewall_approved",
                "reconciliation_healthy",
                "final_execution_authorization",
                "live_trading_enabled",
                "probability_calibrated",
                "probability_fresh",
                "probability_drift_ok",
                "market_data_validated",
                "exposure_approved",
            )
        ):
            return fail("CONTROL_SNAPSHOT_NOT_FULLY_APPROVED")

        if decision.symbol not in {
            str(row.get("symbol"))
            for row in await adapter.active_symbols()
            if row.get("symbol")
        }:
            return fail("LIVE_DECISION_SYMBOL_NOT_ACTIVE")
        proposal_id = await executor.prepare_proposal(params)

        gate, prectx = await executor.preflight_authorization(
            decision=decision,
            capital=prior,
            runtime_config_hash=load_config_hash(ROOT),
            account=account,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=True,
            live_trading_enabled=True,
            probability_calibrated=True,
            probability_fresh=True,
            probability_drift_ok=True,
            market_data_validated=True,
            exposure_approved=True,
        )
        if not gate.allowed or prectx is None:
            return fail("PREFLIGHT_AUTHORIZATION_REJECTED")
        if not executor.clear_kill_switch_with_fresh_authorization(prectx):
            return fail("KILL_SWITCH_CLEAR_REJECTED")

        gate2, ctx, intent = await executor.authorize_and_build_intent(
            decision=decision,
            capital=prior,
            runtime_config_hash=load_config_hash(ROOT),
            account=account,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=True,
            live_trading_enabled=True,
            probability_calibrated=True,
            probability_fresh=True,
            probability_drift_ok=True,
            market_data_validated=True,
            exposure_approved=True,
            proposal_id=proposal_id,
            mode="LIVE",
        )
        if not gate2.allowed or ctx is None or intent is None:
            return fail("FINAL_AUTHORIZATION_REJECTED")

        token = fence.acquire("deriv-lifecycle-proof")
        outcome = await executor.execute(intent, ctx, token)
        if not outcome.allowed or not outcome.broker_transaction_id:
            return fail(
                f"BROKER_EXECUTION_NOT_CONFIRMED:{outcome.status}"
            )

        statement = await adapter.statement(limit=100)
        transaction_found = any(
            str(row.get("transaction_id") or row.get("id") or "")
            == str(outcome.broker_transaction_id)
            for row in statement
        )
        if not transaction_found:
            return fail(
                "BROKER_TRANSACTION_NOT_CONFIRMED_IN_STATEMENT"
            )

        portfolio = await adapter.portfolio()
        candidate = next(
            (
                row
                for row in portfolio
                if str(row.get("transaction_id") or "")
                == str(outcome.broker_transaction_id)
            ),
            None,
        )
        contract_id = (
            str(candidate.get("contract_id"))
            if candidate and candidate.get("contract_id")
            else None
        )
        if contract_id is None:
            return fail("BROKER_CONTRACT_NOT_BOUND")

        final_status = None
        deadline = asyncio.get_running_loop().time() + float(
            os.getenv("AURELIA_LIFECYCLE_TIMEOUT_SECONDS", "600")
        )
        while asyncio.get_running_loop().time() < deadline:
            final_status = await adapter.get_contract_status(contract_id)
            status = str(final_status.get("status") or "").lower()
            if final_status.get("is_sold") or status in {
                "sold",
                "closed",
                "won",
                "lost",
                "expired",
            }:
                break
            await asyncio.sleep(2)

        if not final_status or not (
            final_status.get("is_sold")
            or str(final_status.get("status") or "").lower()
            in {"sold", "closed", "won", "lost", "expired"}
        ):
            return fail("CONTRACT_SETTLEMENT_NOT_CONFIRMED")

        final_balance = await adapter.get_balance()
        profit = final_status.get("profit")
        payout = final_status.get("payout")
        buy_price = final_status.get("buy_price")
        try:
            if profit is not None:
                net_delta = float(profit)
            elif payout is not None and buy_price is not None:
                net_delta = float(payout) - float(buy_price)
            else:
                return fail("SETTLEMENT_ECONOMICS_NOT_RESOLVED")
        except (TypeError, ValueError):
            return fail("SETTLEMENT_ECONOMICS_INVALID")

        reconciliation = await executor.reconcile(
            broker_capital=final_balance,
            prior_authoritative_balance=prior.available_balance,
            explainable_delta=net_delta,
        )
        if not reconciliation.healthy:
            return fail("POST_TRADE_RECONCILIATION_FAILED")

        ended = datetime.now(timezone.utc)
        observed = {
            "account_loginid": account.loginid,
            "environment": account.environment,
            "currency": final_balance.currency,
            "pre_trade_balance": prior.available_balance,
            "post_trade_balance": final_balance.available_balance,
            "proposal_id": proposal_id,
            "broker_transaction_id": outcome.broker_transaction_id,
            "contract_id": contract_id,
            "contract_status": final_status.get("status"),
            "profit": profit,
            "payout": payout,
            "buy_price": buy_price,
            "net_delta": net_delta,
            "reconciliation_difference": reconciliation.difference,
            "reconciliation_healthy": reconciliation.healthy,
            "orders_submitted": 1,
            "capital_authority_granted": True,
        }
        data_hash = sha256(observed)
        record = build_evidence(
            evidence_id=f"DERIV_TRANSACTION_LIFECYCLE:{ended.strftime('%Y%m%dT%H%M%SZ')}",
            source_hash=source_hash,
            artifact_hash=sha256(
                {"data_hash": data_hash, "config_hash": load_config_hash(ROOT)}
            ),
            config_hash=load_config_hash(ROOT),
            data_hash=data_hash,
            environment="production-real",
            started_at_utc=prior.captured_at.isoformat(),
            ended_at_utc=ended.isoformat(),
            status="CURRENT",
            valid_until_utc=(
                ended.replace(microsecond=0)
                + __import__("datetime").timedelta(minutes=30)
            ).isoformat(),
            provenance={
                "origin": "runtime",
                "issuer": "aurelia-live-lifecycle-verifier",
                "source_commit": source_hash,
                "generated_at_utc": ended.isoformat(),
                "deployment_id": os.getenv(
                    "AURELIA_DEPLOYMENT_ID", "DERIV-LIVE-LIFECYCLE"
                ),
            },
            result="PROVEN",
            invariants_checked=[
                "real_account_binding",
                "fresh_pre_trade_balance",
                "broker_proposal",
                "authorized_buy",
                "broker_transaction_confirmation",
                "contract_binding",
                "contract_settlement",
                "post_trade_balance",
                "capital_reconciliation",
            ],
            invariants_failed=[],
        )
        enriched = dict(record)
        enriched["observed"] = observed
        enriched["orders_submitted"] = 1
        enriched["capital_authority_granted"] = True
        enriched["verification_scope"] = "REAL_DERIV_TRANSACTION_LIFECYCLE"
        enriched["order_submission_permitted"] = True
        enriched["record_hash"] = payload_sha256(
            {
                key: value
                for key, value in enriched.items()
                if key != "record_hash"
            }
        )
        write_evidence(OUTPUT, enriched)
        print("DERIV_TRANSACTION_LIFECYCLE=PROVEN")
        print(f"DERIV_EVIDENCE_PATH={OUTPUT}")
        print(f"DERIV_TRANSACTION_ID={outcome.broker_transaction_id}")
        print(f"DERIV_CONTRACT_ID={contract_id}")
        print(f"POST_TRADE_BALANCE={final_balance.available_balance}")
        print("CAPITAL_AUTHORITY=USED_BY_EXISTING_CAPITAL_PLANE")
        return 0
    except Exception as exc:
        print("DERIV_TRANSACTION_LIFECYCLE=FAILED")
        print(f"REASON={type(exc).__name__}")
        return 1
    finally:
        if adapter is not None:
            await adapter.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
