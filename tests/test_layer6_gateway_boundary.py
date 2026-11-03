from __future__ import annotations

import tempfile
import unittest
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.core.events import sha256
from runtime.core.layer6_risk_gate import RiskPolicy, RiskRequest, RiskVerdict
from runtime.core.models import AccountIdentity, CapitalSnapshot, Decision
from runtime.core.boundary_contracts import (
    IExecutionGateway,
    IRiskEngine,
    Layer6RiskEngine,
    RiskEvaluationInput,
    RiskProvenance,
    RISK_INPUT_SCHEMA,
    RISK_POLICY_SCHEMA,
)
from tests.test_capital_executor import (
    FakeBroker,
    account,
    capital,
    context,
    decision,
    make_executor,
)


UTC = timezone.utc
POLICY_SOURCE = "aurelia-runtime-risk-policy"
INPUT_SOURCE = "aurelia-verified-risk-snapshot"


def policy() -> RiskPolicy:
    return RiskPolicy(
        max_daily_loss=5.0,
        max_position_size=2.0,
        max_total_exposure=5.0,
        timeout_ms=50,
    )


def risk_request(**overrides) -> RiskRequest:
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


def provenance(
    payload,
    *,
    source_id: str,
    schema_version: str,
    currency: str = "USD",
    captured_at: datetime | None = None,
) -> RiskProvenance:
    return RiskProvenance(
        source_id=source_id,
        captured_at_utc=captured_at or datetime.now(UTC),
        schema_version=schema_version,
        checksum_sha256=sha256(payload),
        currency=currency,
        unit="ACCOUNT_CURRENCY",
    )


def source_bound_engine_and_input(
    *,
    now: datetime | None = None,
    request: RiskRequest | None = None,
    input_source_id: str = INPUT_SOURCE,
    input_currency: str = "USD",
    policy_currency: str = "USD",
    input_captured_at: datetime | None = None,
    policy_captured_at: datetime | None = None,
    enabled: bool = True,
):
    observed = now or datetime.now(UTC)
    current_policy = policy()
    current_request = request or risk_request()
    policy_proof = provenance(
        asdict(current_policy),
        source_id=POLICY_SOURCE,
        schema_version=RISK_POLICY_SCHEMA,
        currency=policy_currency,
        captured_at=policy_captured_at or observed,
    )
    input_proof = provenance(
        asdict(current_request),
        source_id=input_source_id,
        schema_version=RISK_INPUT_SCHEMA,
        currency=input_currency,
        captured_at=input_captured_at or observed,
    )
    engine = Layer6RiskEngine(
        current_policy,
        policy_provenance=policy_proof,
        account_currency="USD",
        expected_policy_source_id=POLICY_SOURCE,
        expected_input_source_id=INPUT_SOURCE,
        enabled=enabled,
        max_input_age_seconds=30.0,
    )
    return engine, RiskEvaluationInput(current_request, input_proof)


def write_live_release(path: Path, *, enabled: bool) -> None:
    path.write_text(
        "schema: aurelia.live_lock.v1\n"
        f"live_trading_enabled: {'true' if enabled else 'false'}\n"
        f"FINAL_EXECUTION_AUTHORIZATION: {'true' if enabled else 'false'}\n"
        f"LIVE_EXECUTION: {'ENABLED' if enabled else 'BLOCKED'}\n"
        f"capital_plane_mode: {'LIVE' if enabled else 'VERIFY_ONLY'}\n"
        "research_capital_authority: false\n"
        "external_repositories_capital_forbidden: true\n"
        "blind_resubmission: false\n"
        "kill_switch_independent: true\n",
        encoding="utf-8",
    )


def gateway_arguments(*, broker_account=None, recon_healthy=True):
    active_account = broker_account or account()
    active_capital = capital()
    active_decision = decision()
    engine, bound_input = source_bound_engine_and_input()
    verdict = engine.evaluate_order(bound_input)
    assert isinstance(verdict, RiskVerdict)
    assert verdict.risk_approved
    return {
        "decision": active_decision,
        "capital": active_capital,
        "runtime_config_hash": "config-hash",
        "account": active_account,
        "risk_approved": verdict.risk_approved,
        "firewall_approved": True,
        "reconciliation_healthy": recon_healthy,
        "final_execution_authorization": True,
        "live_trading_enabled": True,
        "probability_calibrated": True,
        "probability_fresh": True,
        "probability_drift_ok": True,
        "market_data_validated": True,
        "exposure_approved": True,
        "mode": "LIVE",
    }


class Layer6BoundaryContractTests(unittest.TestCase):
    def test_valid_fresh_source_bound_input_can_only_produce_a_risk_verdict(self):
        engine, candidate = source_bound_engine_and_input()
        self.assertIsInstance(engine, IRiskEngine)
        verdict = engine.evaluate_order(candidate)
        self.assertTrue(verdict.risk_approved)
        self.assertEqual(verdict.reason, "RISK_CHECKS_PASSED")
        self.assertFalse(hasattr(engine, "get_current_capital_authority"))
        self.assertFalse(hasattr(engine, "submit_order"))
        self.assertFalse(hasattr(verdict, "authorized"))
        self.assertFalse(hasattr(verdict, "authorization_granted"))

    def test_modified_risk_numbers_do_not_match_the_source_checksum(self):
        engine, candidate = source_bound_engine_and_input()
        tampered = replace(candidate.risk_request, stake=1.5)
        verdict = engine.evaluate_order(replace(candidate, risk_request=tampered))
        self.assertFalse(verdict.risk_approved)
        self.assertEqual(verdict.reason, "RISK_INPUT_CHECKSUM_MISMATCH")

    def test_stale_or_future_input_provenance_fails_closed(self):
        now = datetime.now(UTC)
        stale_engine, stale_input = source_bound_engine_and_input(
            now=now,
            input_captured_at=now - timedelta(seconds=31),
        )
        stale = stale_engine.evaluate_order(stale_input)
        self.assertFalse(stale.risk_approved)
        self.assertEqual(stale.reason, "RISK_INPUT_STALE_OR_FUTURE")

        future_engine, future_input = source_bound_engine_and_input(
            now=now,
            input_captured_at=now + timedelta(seconds=1),
        )
        future = future_engine.evaluate_order(future_input)
        self.assertFalse(future.risk_approved)
        self.assertEqual(future.reason, "RISK_INPUT_STALE_OR_FUTURE")

    def test_unexpected_source_or_currency_is_rejected(self):
        wrong_source_engine, wrong_source_input = source_bound_engine_and_input(
            input_source_id="untrusted-source",
        )
        wrong_source = wrong_source_engine.evaluate_order(wrong_source_input)
        self.assertFalse(wrong_source.risk_approved)
        self.assertEqual(wrong_source.reason, "RISK_INPUT_SOURCE_MISMATCH")

        wrong_currency_engine, wrong_currency_input = source_bound_engine_and_input(
            input_currency="EUR",
        )
        wrong_currency = wrong_currency_engine.evaluate_order(wrong_currency_input)
        self.assertFalse(wrong_currency.risk_approved)
        self.assertEqual(wrong_currency.reason, "RISK_INPUT_CURRENCY_OR_UNIT_MISMATCH")

    def test_policy_provenance_mismatch_fails_closed(self):
        current_policy = policy()
        bad_proof = provenance(
            asdict(current_policy),
            source_id=POLICY_SOURCE,
            schema_version=RISK_POLICY_SCHEMA,
        )
        bad_proof = replace(bad_proof, checksum_sha256="0" * 64)
        engine = Layer6RiskEngine(
            current_policy,
            policy_provenance=bad_proof,
            account_currency="USD",
            expected_policy_source_id=POLICY_SOURCE,
            expected_input_source_id=INPUT_SOURCE,
            enabled=True,
            max_input_age_seconds=30.0,
        )
        _, candidate = source_bound_engine_and_input()
        verdict = engine.evaluate_order(candidate)
        self.assertFalse(verdict.risk_approved)
        self.assertEqual(verdict.reason, "RISK_POLICY_CHECKSUM_MISMATCH")

    def test_engine_disabled_by_default_is_not_an_approval(self):
        engine, candidate = source_bound_engine_and_input(enabled=False)
        verdict = engine.evaluate_order(candidate)
        self.assertFalse(verdict.risk_approved)
        self.assertEqual(verdict.reason, "RISK_GATE_DISABLED")


class GatewayOverridePreventionTests(unittest.IsolatedAsyncioTestCase):
    async def test_positive_risk_verdict_cannot_bypass_live_lock(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            write_live_release(lock, enabled=False)
            broker = FakeBroker()
            executor = make_executor(lock, broker)
            self.assertIsInstance(executor, IExecutionGateway)

            gate, auth, intent = await executor.authorize_and_build_intent(
                **gateway_arguments()
            )

            self.assertFalse(gate.allowed)
            self.assertIn("LIVE_LOCK_OR_FINAL_AUTHORIZATION_DISABLED", gate.reason_codes)
            self.assertIsNone(auth)
            self.assertIsNone(intent)
            self.assertEqual(broker.proposal_calls, 0)
            self.assertEqual(broker.calls, 0)

    async def test_positive_risk_verdict_cannot_bypass_active_kill_switch(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            write_live_release(lock, enabled=True)
            broker = FakeBroker()
            executor = make_executor(lock, broker)
            self.assertTrue(executor.kill_switch)

            gate, auth, intent = await executor.authorize_and_build_intent(
                **gateway_arguments()
            )

            self.assertFalse(gate.allowed)
            self.assertIn("KILL_SWITCH_ON", gate.reason_codes)
            self.assertIsNone(auth)
            self.assertIsNone(intent)
            self.assertEqual(broker.proposal_calls, 0)
            self.assertEqual(broker.calls, 0)

    async def test_positive_risk_verdict_cannot_bypass_reconciliation_failure(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            write_live_release(lock, enabled=True)
            broker = FakeBroker()
            executor = make_executor(lock, broker)
            # Simulate a previously verified startup clearance in an isolated
            # fixture. This is not a production reset or a live authorization.
            now = datetime.now(UTC)
            executor._kill_switch_activated_at = now - timedelta(seconds=2)
            fresh = context(issued_at=now - timedelta(seconds=1))
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(fresh))
            self.assertFalse(executor.kill_switch)

            gate, auth, intent = await executor.authorize_and_build_intent(
                **gateway_arguments(recon_healthy=False)
            )

            self.assertFalse(gate.allowed)
            self.assertIn("RECONCILIATION_UNHEALTHY", gate.reason_codes)
            self.assertIsNone(auth)
            self.assertIsNone(intent)
            self.assertEqual(broker.proposal_calls, 0)
            self.assertEqual(broker.calls, 0)


if __name__ == "__main__":
    unittest.main()
