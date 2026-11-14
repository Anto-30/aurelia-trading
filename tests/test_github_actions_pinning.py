from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTION_REF = re.compile(
    r"^\s*uses:\s*(actions/[A-Za-z0-9_.-]+)@([^\s#]+)",
    re.MULTILINE,
)


class GitHubActionPinningTests(unittest.TestCase):
    def test_all_first_party_actions_are_pinned_to_full_commit_shas(self) -> None:
        workflow_files = sorted(
            path
            for path in WORKFLOWS.iterdir()
            if path.is_file() and path.suffix in {".yml", ".yaml"}
        )
        self.assertTrue(workflow_files, "No GitHub Actions workflows were found")

        mutable: list[str] = []
        for path in workflow_files:
            source = path.read_text(encoding="utf-8")
            for action, reference in ACTION_REF.findall(source):
                if re.fullmatch(r"[0-9a-f]{40}", reference) is None:
                    mutable.append(f"{path.relative_to(ROOT)}: {action}@{reference}")

        self.assertEqual(
            mutable,
            [],
            "GitHub Actions must be pinned to reviewed immutable commit SHAs:\n"
            + "\n".join(mutable),
        )


if __name__ == "__main__":
    unittest.main()
