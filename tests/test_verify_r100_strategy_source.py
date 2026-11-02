from __future__ import annotations

import unittest

from scripts.verify_r100_strategy_source import (
    COLLECTOR_PATH,
    ENGINE_PATH,
    _selected_ast,
)


class StrategySourceVerifierTests(unittest.TestCase):
    def test_engine_source_requires_only_engine_nodes(self):
        source = """
class SignalCandidate:
    pass


class AutonomousSignalHunter:
    pass
"""
        selected = _selected_ast(source, path=ENGINE_PATH)

        self.assertEqual(
            set(selected),
            {"SignalCandidate", "AutonomousSignalHunter"},
        )

    def test_collector_source_still_requires_strategy_constants(self):
        with self.assertRaisesRegex(ValueError, "constant:SYMBOL"):
            _selected_ast("", path=COLLECTOR_PATH)


if __name__ == "__main__":
    unittest.main()
