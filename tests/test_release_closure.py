import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import live_release_gate


class ReleaseGateTests(unittest.TestCase):
    def test_readiness_does_not_trust_stale_repository_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            snapshot = Path(d) / "AURELIA_READINESS.json"
            snapshot.write_text(
                json.dumps({
                    "final_execution_authorization": False,
                    "live_execution": "BLOCKED",
                    "blockers": [{"gate": "STALE_READINESS_SNAPSHOT"}],
                }),
                encoding="utf-8",
            )
            with patch.object(
                live_release_gate,
                "evaluate_readiness",
                return_value={
                    "final_execution_authorization": True,
                    "live_execution": "ENABLED",
                    "blockers": [],
                },
            ):
                live_release_gate.check_readiness()


if __name__ == "__main__":
    unittest.main()
