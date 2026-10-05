from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    with (ROOT / path).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise AssertionError(path)
    return value


class TestEvidenceLineage(unittest.TestCase):
    def test_current_external_access_state_is_newer_than_preserved_history(self) -> None:
        current = load_json("data/runtime/AURELIA_EXTERNAL_ACCESS_STATE.json")
        historical = load_json(
            "data/runtime/archive/AURELIA_EXTERNAL_ACCESS_STATE_2026-10-04.json"
        )

        self.assertEqual(
            current["current_tip"],
            current["simulation_soak"]["source_commit"],
        )
        self.assertNotEqual(current["current_tip"], historical["current_tip"])
        self.assertEqual(
            current["simulation_soak"]["workflow_run_id"],
            current["ci"]["nonprod_soak_run_id"],
        )
        self.assertEqual(
            current["simulation_soak"]["evidence_artifact_id"],
            11351107615,
        )
        self.assertEqual(current["capital"]["final_execution_authorization"], False)
        self.assertEqual(current["capital"]["live_execution"], "BLOCKED")
        self.assertEqual(current["capital"]["live_orders"], 0)

    def test_current_state_does_not_claim_authenticated_deriv_or_production_soak(self) -> None:
        current = load_json("data/runtime/AURELIA_EXTERNAL_ACCESS_STATE.json")
        self.assertEqual(
            current["deriv"]["current_authenticated_runtime_session"],
            "NOT_CONFIGURED",
        )
        self.assertFalse(current["deriv"]["independent_authenticated_runtime_check"])
        self.assertEqual(current["deriv"]["real_broker_evidence"], "UNAVAILABLE")
        self.assertEqual(current["qualification"]["production_soak_3600s"], "NOT_RUN")
        self.assertEqual(current["qualification"]["strategy_live_eligible"], False)

    def test_federation_and_capital_boundaries_are_fail_closed(self) -> None:
        current = load_json("data/runtime/AURELIA_EXTERNAL_ACCESS_STATE.json")
        federation = current["federation"]
        capital = current["capital"]

        self.assertFalse(federation["external_capital_authority"])
        self.assertFalse(federation["live_order_authority"])
        self.assertFalse(federation["live_lock_mutation"])
        self.assertFalse(federation["secret_reading"])
        self.assertEqual(federation["external_code_execution"], "DENY_BY_DEFAULT")
        self.assertTrue(capital["live_lock"])
        self.assertFalse(capital["final_execution_authorization"])
        self.assertEqual(capital["live_execution"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
