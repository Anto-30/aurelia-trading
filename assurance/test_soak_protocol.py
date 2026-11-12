import unittest

from assurance.soak_protocol import SoakResult, smoke_soak_is_not_full_soak, validate_full_soak

class SoakProtocolTest(unittest.TestCase):
    def test_full_soak_acceptance_contract(self):
        good = SoakResult(3600, 0, 0, 0, 0, 0, 0, 0)
        self.assertTrue(validate_full_soak(good))

    def test_any_failure_blocks(self):
        bad = SoakResult(3600, 1, 0, 0, 0, 0, 0, 0)
        self.assertFalse(validate_full_soak(bad))

    def test_short_run_is_not_evidence(self):
        smoke = SoakResult(30, 0, 0, 0, 0, 0, 0, 0)
        self.assertTrue(smoke_soak_is_not_full_soak(smoke))
        self.assertFalse(validate_full_soak(smoke))

    def test_soak_workflow_is_public_only_and_keeps_capital_blocked(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        workflow = (
            root / ".github" / "workflows" / "non-production-3600s-soak.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('FINAL_EXECUTION_AUTHORIZATION: "false"', workflow)
        self.assertIn('LIVE_EXECUTION: "BLOCKED"', workflow)
        self.assertIn('AURELIA_VERIFY_DERIV_AUTH: "false"', workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("python scripts/deriv_public_ws_soak_3600.py", workflow)
        self.assertIn("capital_movement: false", workflow)


if __name__ == "__main__":
    unittest.main()
