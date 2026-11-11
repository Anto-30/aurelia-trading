"""Regression tests for the quarantined legacy ATOS SMC workflow."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "atos-v2-smc-baseline.yml"


class LegacyATOSWorkflowSafetyTests(unittest.TestCase):
    def test_legacy_baseline_is_manual_only_and_non_collecting(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(
            workflow,
            r"(?m)^  (push|schedule|pull_request|pull_request_target):",
        )
        self.assertNotIn("inputs:", workflow)
        self.assertNotIn("${{ inputs.", workflow)
        self.assertNotIn("${{ github.event.inputs.", workflow)
        self.assertNotIn("research.labs.run_smc_baseline", workflow)
        self.assertNotIn("research.labs.deriv_history", workflow)
        self.assertNotIn("R_100", workflow)
        self.assertNotIn("actions/checkout@", workflow)
        self.assertNotIn("actions/upload-artifact@", workflow)
        self.assertNotIn("retention-days:", workflow)
        self.assertIn("WORKFLOW_INPUT_SHELL_INTERPOLATION=REMOVED", workflow)
        self.assertIn("DATA_DOWNLOAD_PERMITTED=false", workflow)
        self.assertIn("BACKTEST_EXECUTION_PERMITTED=false", workflow)
        self.assertIn("ARTIFACT_UPLOAD_PERMITTED=false", workflow)
        self.assertIn("LIVE_EXECUTION=BLOCKED", workflow)
        self.assertIn("FINAL_EXECUTION_AUTHORIZATION=false", workflow)


if __name__ == "__main__":
    unittest.main()
