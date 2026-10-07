import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.intelligence.agent_genome import AgentGenome, save_genome
from runtime.intelligence.champion_challenger import evaluate_promotion
from runtime.intelligence.performance_ledger import EvaluationRecord, PerformanceLedger
from runtime.intelligence.provenance import Provenance, stale


class IntelligenceEvolutionTests(unittest.TestCase):
    def test_ledger_is_append_only(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = PerformanceLedger(Path(d) / "performance.jsonl")
            record = EvaluationRecord.create(
                task_id="t1", agent_id="a1", model_id="m1", model_version="v1",
                task_type="research", correctness=.9, calibration=.9, robustness=.9,
                evidence_quality=.9, latency_ms=100, cost=.01, failure_type=None,
                review_result="PASS",
            )
            ledger.append(record)
            self.assertEqual(len(ledger.read()), 1)

    def test_promotion_requires_all_gates(self):
        result = evaluate_promotion(
            champion_score=.8, challenger_score=.95,
            champion_samples=100, challenger_samples=100,
            unseen_superior=True, adversarial_pass=True, regression_pass=True,
            calibration_pass=True, reliability_pass=True, generalization_pass=True,
        )
        self.assertEqual(result.status, "PROMOTE")

    def test_promotion_rejected_without_adversarial_validation(self):
        result = evaluate_promotion(
            champion_score=.8, challenger_score=.99,
            champion_samples=100, challenger_samples=100,
            unseen_superior=True, adversarial_pass=False, regression_pass=True,
            calibration_pass=True, reliability_pass=True, generalization_pass=True,
        )
        self.assertEqual(result.status, "RETAIN")

    def test_provenance_rejects_unvalidated_active_knowledge(self):
        with self.assertRaises(ValueError):
            Provenance("k1","source","2026-10-07T00:00:00Z",(),(),(),(),None,"active").validate()

    def test_stale_detection(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        self.assertTrue(stale(old, 3600))

    def test_genome_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            g = AgentGenome("a1","research","m1","v1",capabilities=["research"])
            save_genome(Path(d)/"genome.json",g)
            self.assertTrue((Path(d)/"genome.json").exists())


if __name__ == "__main__":
    unittest.main()
