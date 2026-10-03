from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositorySourceOfTruthTests(unittest.TestCase):
    REQUIRED_FILES = (
        "README.md",
        "AURELIA_REPOSITORY_MAP.md",
        "AURELIA_SOURCE_OF_TRUTH.json",
        "config/LIVE_LOCK.yaml",
        "runtime/main.py",
        "runtime/ops/readiness_orchestrator.py",
        "runtime/adapters/deriv_session.py",
        "runtime/adapters/session_manager.py",
        "runtime/adapters/deriv_adapter.py",
        "runtime/adapters/deriv_ws.py",
        "runtime/broker/executor.py",
        "capital/capital_plane.py",
        "execution/deriv.py",
        "railway.toml",
        ".github/workflows/railway-deploy.yml",
        ".github/workflows/deriv-session-verification.yml",
        ".github/workflows/aurelia-assurance.yml",
        "docs/AURELIA_GITHUB_SOURCE_OF_TRUTH_2026-10-03.md",
    )

    EXECUTABLE_ROOTS = (
        ROOT / "runtime",
        ROOT / "execution",
        ROOT / "capital",
    )

    LEGACY_MARKERS = (
        "ws.derivws.com",
        "binaryws.derivws.com",
        "websockets/v3",
    )

    def test_required_source_paths_exist(self) -> None:
        missing = [
            path
            for path in self.REQUIRED_FILES
            if not (ROOT / path).is_file()
        ]
        self.assertEqual([], missing, f"missing canonical source paths: {missing}")

    def test_live_lock_is_fail_closed(self) -> None:
        lock = (ROOT / "config" / "LIVE_LOCK.yaml").read_text(encoding="utf-8")
        self.assertIn("live_trading_enabled: false", lock)
        self.assertIn("FINAL_EXECUTION_AUTHORIZATION: false", lock)
        self.assertIn("LIVE_EXECUTION: BLOCKED", lock)

    def test_production_executable_code_contains_no_legacy_deriv_endpoint(self) -> None:
        offenders: list[str] = []
        for base in self.EXECUTABLE_ROOTS:
            for path in base.rglob("*.py"):
                content = path.read_text(encoding="utf-8")
                if any(marker in content for marker in self.LEGACY_MARKERS):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(
            [],
            offenders,
            f"legacy Deriv endpoint found in executable code: {offenders}",
        )

    def test_source_of_truth_points_to_main(self) -> None:
        metadata = (ROOT / "AURELIA_SOURCE_OF_TRUTH.json").read_text(
            encoding="utf-8"
        )
        self.assertIn('"canonical_branch": "main"', metadata)
        self.assertIn('"default_branch": "main"', metadata)
        self.assertIn('"github_canonical_branch": "main"', metadata)


if __name__ == "__main__":
    unittest.main()
