"""Regression coverage for the ATOS v2.0 R_100 research quarantine."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from research.r100_prospective_oos_archiver import seal_r100_archive


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "r100-prospective-oos.yml"


class R100ResearchQuarantineTests(unittest.TestCase):
    def test_legacy_workflow_is_manual_only_and_non_collecting(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(workflow, r"(?m)^  (push|schedule|pull_request|pull_request_target):")
        self.assertNotIn("actions/checkout@", workflow)
        self.assertNotIn("actions/setup-python@", workflow)
        self.assertNotIn("actions/upload-artifact@", workflow)
        self.assertNotIn("retention-days:", workflow)
        self.assertNotIn("research.r100_prospective_oos_collector", workflow)
        self.assertNotIn("GH_TOKEN:", workflow)
        self.assertIn("R100_RESEARCH_STATUS=QUARANTINED", workflow)
        self.assertIn("FX_SMC_EVIDENCE_ELIGIBLE=false", workflow)
        self.assertIn("NEW_DATA_COLLECTION_PERMITTED=false", workflow)
        self.assertIn("LEGACY_ARTIFACT_PURGE_REQUIRED=true", workflow)
        self.assertIn("LIVE_EXECUTION=BLOCKED", workflow)
        self.assertIn("FINAL_EXECUTION_AUTHORIZATION=false", workflow)

    def test_archiver_refuses_to_create_new_persistent_r100_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "r100-archive.json"
            with self.assertRaisesRegex(RuntimeError, "R100_ARCHIVE_QUARANTINED"):
                seal_r100_archive(
                    [{"timestamp": "2026-11-11T00:00:00Z", "price": 100.0}],
                    strategy_id="LEGACY_R100",
                    symbol="R_100",
                    regime="LEGACY",
                    started_at_utc="2026-11-11T00:00:00Z",
                    output_path=target,
                )
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
