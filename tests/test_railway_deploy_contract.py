import unittest
from pathlib import Path


class RailwayDeployContractTests(unittest.TestCase):
    def test_workflow_uses_project_scoped_railway_token(self):
        workflow = Path(".github/workflows/railway-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("RAILWAY_TOKEN", workflow)
        self.assertIn("railway up", workflow)
        self.assertNotIn("RAILWAY_API_TOKEN", workflow)

    def test_workflow_targets_known_project_and_environment(self):
        workflow = Path(".github/workflows/railway-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("da9da5a1-acd2-4af2-9fec-bf46e4d4252b", workflow)
        self.assertIn("bb95dc97-ad27-4b3a-8fa0-cf52df555a38", workflow)

    def test_workflow_never_turns_on_live_execution(self):
        workflow = Path(".github/workflows/railway-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("FINAL_EXECUTION_AUTHORIZATION=false", workflow)
        self.assertIn("LIVE_EXECUTION=BLOCKED", workflow)


if __name__ == "__main__":
    unittest.main()
