from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINNED_WORKFLOWS = (
    ".github/workflows/atos-research-validation.yml",
    ".github/workflows/aurelia-assurance.yml",
    ".github/workflows/deriv-history-ingestion.yml",
    ".github/workflows/deriv-readonly-verification.yml",
)
USES_PATTERN = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")


class WorkflowActionPinTests(unittest.TestCase):
    def test_scanner_recognizes_standard_uses_line(self):
        sample = USES_PATTERN.match("      - uses: actions/checkout@" + "a" * 40 + " # pinned")
        self.assertIsNotNone(sample, "scanner must recognize a standard GitHub Actions uses line")
        self.assertEqual(sample.group(1), "actions/checkout@" + "a" * 40)

    def test_all_external_actions_in_release_research_workflows_use_full_shas(self):
        scanned = 0
        for relative in PINNED_WORKFLOWS:
            path = ROOT / relative
            self.assertTrue(path.is_file(), f"required workflow is missing: {relative}")
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                match = USES_PATTERN.match(line)
                if not match:
                    continue
                action_ref = match.group(1)
                if action_ref.startswith("./"):
                    continue
                scanned += 1
                with self.subTest(workflow=relative, line=line_number, action=action_ref):
                    self.assertRegex(
                        action_ref,
                        r"^[^@\s]+@[0-9a-f]{40}$",
                        "external actions must be pinned to immutable full commit SHAs",
                    )
        self.assertGreater(scanned, 0, "scanner must inspect at least one external action")


if __name__ == "__main__":
    unittest.main()
