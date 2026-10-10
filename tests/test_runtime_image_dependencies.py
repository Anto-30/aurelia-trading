from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RuntimeImageDependencyTests(unittest.TestCase):
    def test_docker_image_includes_shared_evidence_modules_used_by_runtime(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        runtime_main = (ROOT / "runtime" / "main.py").read_text(encoding="utf-8")
        readiness = (
            ROOT / "runtime" / "ops" / "readiness_orchestrator.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "COPY assurance/certification_evidence.py assurance/evidence_writer.py ./assurance/",
            dockerfile,
        )
        self.assertIn(
            "from assurance.evidence_writer import",
            runtime_main,
        )
        self.assertIn(
            "from assurance.certification_evidence import",
            readiness,
        )

    def test_dockerfile_does_not_require_repository_root_copy(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY runtime ./runtime", dockerfile)
        self.assertIn("COPY config ./config", dockerfile)
        self.assertNotIn("COPY . .", dockerfile)


if __name__ == "__main__":
    unittest.main()
