from __future__ import annotations

import ast
import unittest
from pathlib import Path

from research.r100_prospective_oos_collector import evaluation, initial_state


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR_PATH = ROOT / "research" / "r100_prospective_oos_collector.py"
FORBIDDEN_CALLS = {
    "buy",
    "sell",
    "submit_order",
    "place_trade",
    "execute_order",
    "open_position",
    "close_position",
    "authorize",
}


class ResearchSecurityBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = COLLECTOR_PATH.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source, filename=str(COLLECTOR_PATH))

    def test_collector_does_not_import_account_or_execution_adapters(self):
        runtime_imports = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                runtime_imports.update(
                    alias.name for alias in node.names
                    if alias.name.startswith("runtime.")
                )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("runtime."):
                    runtime_imports.add(module)

        self.assertEqual(
            runtime_imports,
            {
                "runtime.adapters.deriv_ws",
                "runtime.strategy.autonomous_signal_engine",
            },
        )

    def test_collector_has_no_capital_moving_or_authorization_calls(self):
        calls = set()
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if isinstance(function, ast.Name):
                calls.add(function.id.lower())
            elif isinstance(function, ast.Attribute):
                calls.add(function.attr.lower())

        self.assertEqual(sorted(calls & FORBIDDEN_CALLS), [])

    def test_collector_uses_only_the_public_market_data_endpoint(self):
        assignments = {
            node.targets[0].id: node.value.value
            for node in self.tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        }
        self.assertEqual(
            assignments.get("PUBLIC_WS_URL"),
            "wss://api.derivws.com/trading/v1/options/ws/public",
        )
        for credential_name in (
            "DERIV_AUTH_TOKEN",
            "DERIV_PAT",
            "DERIV_OAUTH_ACCESS_TOKEN",
            "DERIV_APP_ID",
        ):
            self.assertNotIn(credential_name, self.source)

    def test_research_evaluation_is_always_non_authorizing(self):
        report = evaluation(initial_state())
        self.assertIs(report["strategy_live_eligible"], False)
        self.assertIs(report["execution_authorized"], False)
        self.assertIs(report["capital_authority"], False)
        self.assertIs(report["live_execution"], False)


if __name__ == "__main__":
    unittest.main()
