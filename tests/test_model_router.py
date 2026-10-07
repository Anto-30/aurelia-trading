import unittest

from runtime.intelligence.model_router import ModelEvidence, ModelRouter


REGISTRY = {
    "agents": [
        {"agent_id": "quant_statistical", "primary": "openai.gpt-5.6-luna", "challengers": ["google.gemini-pro-class"]}
    ]
}


class ModelRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter(REGISTRY)

    def test_abstains_without_verified_sample(self):
        result = self.router.route(
            agent_id="quant_statistical",
            task_type="statistics",
            evidence=[
                ModelEvidence("openai.gpt-5.6-luna", "statistics", .99, 4),
            ],
        )
        self.assertEqual(result.status, "ABSTAIN")
        self.assertIsNone(result.model_id)

    def test_empirical_winner(self):
        result = self.router.route(
            agent_id="quant_statistical",
            task_type="statistics",
            evidence=[
                ModelEvidence("openai.gpt-5.6-luna", "statistics", .92, 100, .98, .95, .98),
                ModelEvidence("google.gemini-pro-class", "statistics", .96, 100, .90, .92, .95),
            ],
        )
        self.assertEqual(result.status, "ROUTE")
        self.assertEqual(result.model_id, "openai.gpt-5.6-luna")

    def test_stale_evidence_is_rejected(self):
        result = self.router.route(
            agent_id="quant_statistical",
            task_type="statistics",
            evidence=[
                ModelEvidence("openai.gpt-5.6-luna", "statistics", .99, 100, stale=True),
            ],
        )
        self.assertEqual(result.status, "ABSTAIN")

    def test_high_consequence_requires_deterministic_validation(self):
        result = self.router.route(
            agent_id="quant_statistical",
            task_type="statistics",
            evidence=[
                ModelEvidence("openai.gpt-5.6-luna", "statistics", .92, 100),
            ],
            high_consequence=True,
        )
        self.assertTrue(result.deterministic_validation_required)
        self.assertFalse(result.capital_authority)


if __name__ == "__main__":
    unittest.main()
