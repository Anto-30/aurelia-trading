from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

class FreshAuthEvidenceContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_nonprod_runtime_injects_fail_closed_flags(self):
        text = self.read(".github/workflows/non-production-3600s-soak.yml")
        self.assertIn("--env FINAL_EXECUTION_AUTHORIZATION=false", text)
        self.assertIn("--env LIVE_EXECUTION=BLOCKED", text)

    def test_railway_smoke_injects_sealed_nonprod_mode(self):
        text = self.read(".github/workflows/railway-deploy.yml")
        self.assertIn("--env AURELIA_NON_PRODUCTION_SOAK=true", text)
        self.assertIn("--env FINAL_EXECUTION_AUTHORIZATION=false", text)
        self.assertIn("--env LIVE_EXECUTION=BLOCKED", text)

    def test_r100_workflow_uses_campaign_guard(self):
        workflow = self.read(".github/workflows/r100-prospective-oos.yml")
        guard = self.read("research/r100_campaign_guard.py")
        self.assertIn("python -m research.r100_campaign_guard", workflow)
        self.assertIn("R100_CONFIG_HASH_MISMATCH", guard)

    def test_jev_is_explicitly_routed_to_grok(self):
        payload = json.loads(self.read("config/intelligence_source_routing.json"))
        entry = next(x for x in payload["routing"] if x.get("source") == "JEV (claude-x-jev)")
        self.assertEqual(entry["primary_agent"], "GrokBot")
        self.assertEqual(entry["authority"], "advisory_typed_challenge_only")
        self.assertFalse(entry["capital_authority"])

    def test_grok_has_jev_skill(self):
        payload = json.loads(self.read("config/agent_capability_matrix.json"))
        self.assertIn("jev-typed-decision-challenger", payload["agents"]["GrokBot"]["skills"])

    def test_campaign_guard_detects_config_drift(self):
        from research.r100_campaign_guard import inspect_state, main
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps({
                "schema": "aurelia.r100.prospective_oos.v1",
                "manifest": {
                    "strategy_id": "R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0",
                    "strategy_version": "0.2.0",
                    "sealed": False,
                    "code_commit": "old",
                    "config_hash": "stale-config",
                },
            }), encoding="utf-8")
            self.assertEqual(inspect_state(path), "R100_ROLLOVER_REQUIRED:R100_CONFIG_HASH_MISMATCH")


    def test_campaign_guard_entrypoint_uses_configured_state_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "missing-state.json"
            output = StringIO()
            with patch.dict(os.environ, {"AURELIA_R100_STATE_PATH": str(state_path)}):
                with redirect_stdout(output):
                    result = main()
            self.assertEqual(result, 0)
            self.assertEqual(output.getvalue().strip(), "R100_NO_STATE")

if __name__ == "__main__":
    unittest.main()
