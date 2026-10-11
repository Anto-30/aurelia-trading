from __future__ import annotations

import os
import tempfile
import unittest

from runtime.agent_federation import AgentFederationSupervisor, PersistentAgentFederation
from runtime.continuous_runtime import start_continuous_runtime
from runtime.core.state import RuntimeStateMachine


class ContinuousRuntimeFederationTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_existing_federation_and_supervisor(self):
        original = dict(os.environ)
        with tempfile.TemporaryDirectory() as td:
            try:
                os.environ["AURELIA_AUTONOMOUS_LOOP"] = "false"
                os.environ["AURELIA_FEDERATION_JOURNAL_PATH"] = f"{td}/events.ndjson"
                os.environ["AURELIA_FEDERATION_LEASE_PATH"] = f"{td}/leases.json"
                federation = PersistentAgentFederation(
                    journal_path=f"{td}/events.ndjson",
                    lease_path=f"{td}/leases.json",
                    config_hash="cfg",
                    source_hash="src",
                )
                supervisor = AgentFederationSupervisor(
                    federation,
                    agents=("AURELIA", "ClaudeCode"),
                )
                runtime = await start_continuous_runtime(
                    RuntimeStateMachine(),
                    federation=federation,
                    federation_supervisor=supervisor,
                )
                self.assertIs(runtime.federation, federation)
                self.assertIs(runtime.federation_supervisor, supervisor)
                self.assertIsNone(runtime.execution_loop)
                await runtime.stop()
            finally:
                os.environ.clear()
                os.environ.update(original)


    def test_live_mode_requires_explicit_allowlisted_symbols(self):
        from runtime.continuous_runtime import resolve_runtime_symbols

        active = [{"symbol": "R_100"}, {"underlying_symbol": "R_75"}]
        with self.assertRaisesRegex(RuntimeError, "AURELIA_LIVE_SYMBOL_ALLOWLIST_REQUIRED"):
            resolve_runtime_symbols("", active, live_release_enabled=True)

        self.assertEqual(
            resolve_runtime_symbols("R_100,R_75", active, live_release_enabled=True),
            ("R_100", "R_75"),
        )

    def test_symbol_allowlist_rejects_inactive_duplicates_and_empty_items(self):
        from runtime.continuous_runtime import resolve_runtime_symbols

        active = [{"symbol": "R_100"}, {"symbol": "R_75"}]
        with self.assertRaisesRegex(RuntimeError, "AURELIA_CONFIGURED_SYMBOL_NOT_ACTIVE"):
            resolve_runtime_symbols("R_100,UNKNOWN", active, live_release_enabled=False)
        with self.assertRaisesRegex(RuntimeError, "AURELIA_SYMBOL_ALLOWLIST_HAS_DUPLICATES"):
            resolve_runtime_symbols("R_100,R_100", active, live_release_enabled=False)
        with self.assertRaisesRegex(RuntimeError, "AURELIA_SYMBOL_ALLOWLIST_INVALID"):
            resolve_runtime_symbols("R_100,", active, live_release_enabled=False)

    def test_research_mode_can_use_bounded_active_symbol_discovery(self):
        from runtime.continuous_runtime import resolve_runtime_symbols

        active = [{"symbol": f"R_{index}"} for index in range(5)]
        self.assertEqual(
            resolve_runtime_symbols("", active, live_release_enabled=False, max_symbols=2),
            ("R_0", "R_1"),
        )


if __name__ == "__main__":
    unittest.main()
