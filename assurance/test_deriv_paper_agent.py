"""Regression tests for the research-only Deriv paper decision gate."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.paper_agent import (
    JevDecision, DecisionSchemaError, PaperAgent, PaperEventLedger,
    PaperReflexGate, PortfolioRiskSnapshot,
)

GOOD = {
    "regime": "trending",
    "direction": "long",
    "setup_quality": 3,
    "risk_state": "safe",
    "confidence": 0.72,
    "position_size_pct": 1.0,
    "stop_loss_ticks": 10,
    "take_profit_ticks": 20,
}


def healthy(**overrides):
    data = {
        "equity": 100.0,
        "day_start_equity": 100.0,
        "peak_equity": 100.0,
        "daily_pnl": 0.0,
        "api_healthy": True,
        "consecutive_losses": 0,
    }
    data.update(overrides)
    return PortfolioRiskSnapshot(**data)


class JevSchemaTests(unittest.TestCase):
    def test_valid_decision_is_typed(self):
        decision = JevDecision.from_mapping(GOOD)
        self.assertEqual(decision.direction, "long")
        self.assertEqual(decision.setup_quality, 3)

    def test_extra_fields_rejected(self):
        with self.assertRaisesRegex(DecisionSchemaError, "FIELDS_MISMATCH"):
            JevDecision.from_mapping({**GOOD, "explanation": "untrusted LLM prose"})

    def test_boolean_is_not_probability(self):
        with self.assertRaisesRegex(DecisionSchemaError, "MUST_BE_NUMERIC"):
            JevDecision.from_mapping({**GOOD, "confidence": True})

    def test_nan_rejected(self):
        with self.assertRaisesRegex(DecisionSchemaError, "MUST_BE_FINITE"):
            JevDecision.from_mapping({**GOOD, "confidence": float("nan")})

    def test_neutral_signal_must_have_zero_size(self):
        with self.assertRaisesRegex(DecisionSchemaError, "NEUTRAL"):
            JevDecision.from_mapping({**GOOD, "direction": "neutral"})

    def test_invalid_tick_count_rejected(self):
        with self.assertRaisesRegex(DecisionSchemaError, "POSITIVE_TICKS"):
            JevDecision.from_mapping({**GOOD, "stop_loss_ticks": 0})


class ReflexRiskTests(unittest.TestCase):
    def test_valid_candidate_is_only_a_paper_intent(self):
        result = PaperReflexGate().evaluate(JevDecision.from_mapping(GOOD), healthy())
        self.assertTrue(result.allowed)
        self.assertEqual(result.status, "WOULD_TRADE")
        self.assertFalse(result.kill_switch_tripped)

    def test_confidence_above_canonical_max_is_rejected_not_clipped(self):
        result = PaperReflexGate().evaluate(
            JevDecision.from_mapping({**GOOD, "confidence": 0.80}), healthy()
        )
        self.assertFalse(result.allowed)
        self.assertIn("PROBABILITY_ABOVE_AURELIA_MAX_0_75", result.reasons)

    def test_1_5_percent_is_blocked_by_default_1_percent_policy(self):
        result = PaperReflexGate().evaluate(
            JevDecision.from_mapping({**GOOD, "position_size_pct": 1.5}), healthy()
        )
        self.assertFalse(result.allowed)
        self.assertIn("POSITION_SIZE_ABOVE_DEFAULT_1_PERCENT_POLICY", result.reasons)

    def test_sub_050_confidence_trips_latched_kill_switch(self):
        gate = PaperReflexGate()
        result = gate.evaluate(
            JevDecision.from_mapping({**GOOD, "confidence": 0.49}), healthy()
        )
        self.assertTrue(result.kill_switch_tripped)
        self.assertIn("CONFIDENCE_BELOW_0_50", result.reasons)
        later = gate.evaluate(JevDecision.from_mapping(GOOD), healthy())
        self.assertFalse(later.allowed)
        self.assertIn("KILL_SWITCH_LATCHED", later.reasons)

    def test_crisis_trips_kill_switch(self):
        result = PaperReflexGate().evaluate(
            JevDecision.from_mapping({**GOOD, "regime": "crisis"}), healthy()
        )
        self.assertFalse(result.allowed)
        self.assertTrue(result.kill_switch_tripped)
        self.assertIn("CRISIS_REGIME", result.reasons)

    def test_stale_risk_snapshot_trips_kill_switch(self):
        stale = healthy(observed_at_utc=datetime.now(timezone.utc) - timedelta(seconds=60))
        result = PaperReflexGate().evaluate(JevDecision.from_mapping(GOOD), stale)
        self.assertFalse(result.allowed)
        self.assertTrue(result.kill_switch_tripped)
        self.assertIn("RISK_SNAPSHOT_STALE_OR_INVALID", result.reasons)

    def test_api_failure_trips_kill_switch(self):
        result = PaperReflexGate().evaluate(
            JevDecision.from_mapping(GOOD), healthy(api_healthy=False)
        )
        self.assertFalse(result.allowed)
        self.assertIn("API_ERROR", result.reasons)

    def test_daily_loss_is_hard_stop(self):
        result = PaperReflexGate().evaluate(
            JevDecision.from_mapping(GOOD), healthy(daily_pnl=-3.0)
        )
        self.assertTrue(result.kill_switch_tripped)
        self.assertIn("DAILY_LOSS_LIMIT_REACHED", result.reasons)

    def test_three_consecutive_losses_are_a_hard_stop(self):
        result = PaperReflexGate().evaluate(
            JevDecision.from_mapping(GOOD), healthy(consecutive_losses=3)
        )
        self.assertFalse(result.allowed)
        self.assertTrue(result.kill_switch_tripped)
        self.assertIn("CONSECUTIVE_LOSS_LIMIT_REACHED", result.reasons)

    def test_drawdown_is_hard_stop(self):
        result = PaperReflexGate().evaluate(
            JevDecision.from_mapping(GOOD),
            healthy(equity=85.0, peak_equity=100.0, daily_pnl=-1.0),
        )
        self.assertTrue(result.kill_switch_tripped)
        self.assertIn("MAX_DRAWDOWN_REACHED", result.reasons)

    def test_operator_reset_cannot_override_hard_daily_loss(self):
        gate = PaperReflexGate()
        gate.trip("DAILY_LOSS_LIMIT_REACHED")
        with self.assertRaisesRegex(ValueError, "CANNOT_BE_OVERRIDDEN"):
            gate.reset_after_operator_review(
                operator_approval_id="review-001", snapshot=healthy(daily_pnl=-5.0),
                crisis_cleared=True, confidence_recovered=True,
            )

    def test_operator_reset_cannot_override_three_loss_streak(self):
        gate = PaperReflexGate()
        gate.trip("CONSECUTIVE_LOSS_LIMIT_REACHED")
        with self.assertRaisesRegex(ValueError, "CANNOT_BE_OVERRIDDEN"):
            gate.reset_after_operator_review(
                operator_approval_id="review-streak",
                snapshot=healthy(consecutive_losses=3),
                crisis_cleared=True, confidence_recovered=True,
            )

    def test_reset_requires_operator_reference_and_recovery_conditions(self):
        gate = PaperReflexGate()
        gate.trip("API_ERROR")
        with self.assertRaisesRegex(ValueError, "APPROVAL_REFERENCE_REQUIRED"):
            gate.reset_after_operator_review(
                operator_approval_id="", snapshot=healthy(),
                crisis_cleared=True, confidence_recovered=True,
            )
        gate.reset_after_operator_review(
            operator_approval_id="review-002", snapshot=healthy(),
            crisis_cleared=True, confidence_recovered=True,
        )
        self.assertFalse(gate.tripped)


class PaperLedgerAndAgentTests(unittest.TestCase):
    def test_hash_chain_append_only_and_idempotency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.sqlite3"
            with PaperEventLedger(path) as ledger:
                first = ledger.append(
                    event_id="d1", event_type="PAPER_INTENT",
                    payload={"allowed_by_risk_gate": True},
                )
                duplicate = ledger.append(
                    event_id="d1", event_type="PAPER_INTENT",
                    payload={"allowed_by_risk_gate": True},
                )
                self.assertEqual(first["event_hash"], duplicate["event_hash"])
                ledger.append(
                    event_id="d2", event_type="MISSED_SIGNAL",
                    payload={"reason": "low-confidence"},
                )
                self.assertTrue(ledger.verify_chain())
                with self.assertRaisesRegex(ValueError, "ID_CONFLICT"):
                    ledger.append(
                        event_id="d1", event_type="PAPER_INTENT",
                        payload={"allowed_by_risk_gate": False},
                    )
            with sqlite3.connect(path) as db:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(
                        "UPDATE paper_events SET event_type='SYSTEM_ALERT' WHERE event_id='d1'"
                    )

    def test_agent_records_missed_signal_and_never_submits(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = PaperEventLedger(Path(tmp) / "events.sqlite3")
            agent = PaperAgent(PaperReflexGate(), ledger)
            result = agent.evaluate(
                event_id="decision-1", candidate={**GOOD, "confidence": 0.60},
                snapshot=healthy(),
            )
            self.assertEqual(result.status, "HOLD")
            events = ledger.read_all()
            self.assertEqual(events[0]["event_type"], "MISSED_SIGNAL")
            payload = json.loads(events[0]["payload_json"])
            self.assertFalse(payload["order_submission_permitted"])
            self.assertIsNone(payload["simulated_pnl"])
            self.assertFalse(hasattr(agent, "submit_order"))
            self.assertFalse(hasattr(agent, "execute_trade"))
            self.assertTrue(ledger.verify_chain())
            ledger.close()

    def test_invalid_candidate_logged_without_echoing_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = PaperEventLedger(Path(tmp) / "events.sqlite3")
            agent = PaperAgent(PaperReflexGate(), ledger)
            result = agent.evaluate(
                event_id="invalid-1", candidate={"access_token": "never-log-this"},
                snapshot=healthy(),
            )
            self.assertEqual(result.status, "BLOCKED")
            serialized = json.dumps(ledger.read_all())
            self.assertNotIn("never-log-this", serialized)
            self.assertTrue(ledger.verify_chain())
            ledger.close()


if __name__ == "__main__":
    unittest.main()
