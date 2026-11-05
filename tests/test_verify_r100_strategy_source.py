from __future__ import annotations

import ast
import unittest

from scripts.verify_r100_strategy_source import (
    COLLECTOR_PATH,
    ENGINE_PATH,
    _selected_ast,
    _strip_operational_input_validation,
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

    def test_operational_tick_validation_does_not_change_strategy_hash_input(self):
        baseline = ast.parse("""
def observe_tick(hunter, state, quote, received_at):
    pending = state["pending"]
    state["observations"].extend(pending)
""").body[0]
        guarded = ast.parse("""
def observe_tick(hunter, state, quote, received_at):
    quote, received_at = validate_tick_input(quote, received_at)
    pending = state["pending"]
    state["observations"].extend(pending)
""").body[0]
        changed_strategy = ast.parse("""
def observe_tick(hunter, state, quote, received_at):
    quote, received_at = validate_tick_input(quote, received_at)
    pending = state["pending"]
    state["observations"].clear()
""").body[0]

        baseline_hash_input = ast.dump(
            _strip_operational_input_validation(baseline),
            include_attributes=False,
        )
        guarded_hash_input = ast.dump(
            _strip_operational_input_validation(guarded),
            include_attributes=False,
        )
        changed_hash_input = ast.dump(
            _strip_operational_input_validation(changed_strategy),
            include_attributes=False,
        )

        self.assertEqual(baseline_hash_input, guarded_hash_input)
        self.assertNotEqual(guarded_hash_input, changed_hash_input)

    def test_validation_wrapper_must_remain_a_single_first_statement(self):
        invalid = ast.parse("""
def observe_tick(hunter, state, quote, received_at):
    pending = state["pending"]
    quote, received_at = validate_tick_input(quote, received_at)
""").body[0]
        with self.assertRaisesRegex(
            ValueError,
            "R100_INPUT_VALIDATION_WRAPPER_POSITION_INVALID",
        ):
            _strip_operational_input_validation(invalid)


if __name__ == "__main__":
    unittest.main()
