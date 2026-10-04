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


if __name__ == "__main__":
    unittest.main()
