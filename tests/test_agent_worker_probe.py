from __future__ import annotations

import ast
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.agent_worker_probe import ADVISORY_WORKERS, main


class AgentWorkerProbeTests(unittest.TestCase):
    def test_ci_probe_reports_provider_connectivity_as_unverified(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main()

        report = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("AGENT_PROVIDER_CONNECTIVITY=NOT_VERIFIED", report)
        self.assertIn("AGENT_PROVIDER_CONNECTED=NONE_CONFIRMED", report)
        self.assertIn(
            "AGENT_PROVIDER_NOT_VERIFIED=" + ",".join(sorted(ADVISORY_WORKERS)),
            report,
        )
        self.assertIn("AGENT_WORKER_PROCESS_LEASES=NOT_PROBED_IN_CI", report)
        self.assertIn("AGENT_WORKER_TASK_EVIDENCE=NOT_VERIFIED", report)
        self.assertNotIn("AGENT_WORKER_ACTIVE=", report)

    def test_ci_probe_cannot_launch_or_heartbeat_agent_workers(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "scripts" / "agent_worker_probe.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)

        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_modules.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )

        self.assertFalse(
            any(
                module.startswith("runtime.agent_federation")
                or module.startswith("runtime.agent_workers")
                for module in imported_modules
            )
        )
        self.assertNotIn("workers.start()", source)
        self.assertNotIn("federation.heartbeat(", source)


if __name__ == "__main__":
    unittest.main()
