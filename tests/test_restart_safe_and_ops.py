import tempfile
import unittest
from pathlib import Path

from runtime.core.persistent import PersistentExecutionFence, PersistentIdempotencyStore
from runtime.core.recovery import RecoveryAssessment, RecoveryDecision
from runtime.core.retry_policy import RetryClass, retry_class
from runtime.ops.self_test import run_self_test
from runtime.ops.soak import run_logical_soak


class RestartSafeOperationalTests(unittest.TestCase):
    def test_persistent_idempotency_survives_reload(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "idempotency.json"
            first = PersistentIdempotencyStore(path)
            first.register_intent("I1")
            first.attach_broker_transaction("I1", "TX1")
            second = PersistentIdempotencyStore(path)
            self.assertEqual(second.get("I1").broker_transaction_id, "TX1")

    def test_persistent_fence_survives_reload(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fence.txt"
            first = PersistentExecutionFence(path)
            token = first.acquire("worker-a")
            second = PersistentExecutionFence(path)
            newer = second.acquire("worker-b")
            self.assertFalse(first.valid(token))
            self.assertTrue(second.valid(newer))

    def test_recovery_unknown_protects_capital(self):
        result = RecoveryAssessment(False, True, False, True, True).decide()
        self.assertEqual(result, RecoveryDecision.CAPITAL_PROTECTED)

    def test_retry_semantics(self):
        self.assertEqual(retry_class("ticks"), RetryClass.SAFE)
        self.assertEqual(retry_class("buy"), RetryClass.RECONCILE_FIRST)

    def test_logical_soak_is_not_production_evidence(self):
        result = run_logical_soak(
            3600,
            lambda _: {
                "invariant_violation": False,
                "silent_degradation": False,
                "capital_authority_escape": False,
                "unresolved_unknown": False,
            },
        )
        self.assertEqual(result.logical_duration_seconds, 3600)
        self.assertFalse(result.acceptance_ready)
        self.assertFalse(result.is_production_evidence)

    def test_self_test_stays_blocked_for_live(self):
        result = run_self_test(Path("."))
        self.assertFalse(result["live_release_may_move_capital"])
        self.assertFalse(result["research_can_submit"])


if __name__ == "__main__":
    unittest.main()
