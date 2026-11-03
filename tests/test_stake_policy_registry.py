from __future__ import annotations

import json
import unittest
from pathlib import Path

from assurance.stake_policy_registry import (
    CapitalPlane,
    StakePolicyRecord,
    StakePolicyReconciliationRegistry,
    ValidationStatus,
)

COMMIT = "a" * 40


def valid_record(**overrides):
    values = dict(
        policy_id="LIVE-ONE",
        version="v1",
        stake_usd=1.0,
        role="EXECUTION_MINIMUM",
        source_documents=("policy.yaml",),
        source_modified_at_utc="2026-10-03T15:03:56Z",
        source_commit=COMMIT,
        observed_at_commit=COMMIT,
        approval_authority="OWNER",
        approval_date="2026-09-26",
        effective_date="2026-09-27",
        intended_capital_plane=CapitalPlane.LIVE,
        rationale="Approved execution minimum subject to the canonical guards.",
        validation_status=ValidationStatus.VALIDATED,
    )
    values.update(overrides)
    return StakePolicyRecord(**values)


class StakePolicyRegistryTests(unittest.TestCase):
    def test_incomplete_policy_can_be_recorded_but_not_selected(self):
        pending = valid_record(
            source_commit=None,
            effective_date=None,
            validation_status=ValidationStatus.PENDING,
        )
        registry = StakePolicyReconciliationRegistry([pending])
        self.assertIsNone(registry.get_authoritative_policy(CapitalPlane.LIVE))
        report = registry.export_reconciliation_report()
        self.assertEqual(report["pending"], 1)
        self.assertIn("source_commit", report["policies"][0]["missing_provenance"])
        self.assertIn("effective_date", report["policies"][0]["missing_provenance"])
        self.assertFalse(report["capital_authority"])
        self.assertFalse(report["runtime_policy_mutation"])
        self.assertFalse(report["policy_selection_performed"])

    def test_validated_policy_requires_origin_commit_and_approval_chain(self):
        with self.assertRaisesRegex(ValueError, "VALIDATED_STAKE_POLICY_MISSING_PROVENANCE"):
            StakePolicyReconciliationRegistry([
                valid_record(source_commit=None)
            ])

    def test_exactly_one_fully_validated_policy_can_be_reported_per_plane(self):
        record = valid_record()
        registry = StakePolicyReconciliationRegistry([record])
        self.assertEqual(
            registry.get_authoritative_policy(CapitalPlane.LIVE).policy_id,
            "LIVE-ONE",
        )

    def test_multiple_validated_policies_for_one_plane_are_conflicted(self):
        first = valid_record(policy_id="LIVE-ONE")
        second = valid_record(policy_id="LIVE-TWO", version="v2")
        registry = StakePolicyReconciliationRegistry([first, second])
        with self.assertRaisesRegex(
            ValueError, "MULTIPLE_VALIDATED_STAKE_POLICIES_FOR_CAPITAL_PLANE"
        ):
            registry.get_authoritative_policy(CapitalPlane.LIVE)

    def test_duplicate_policy_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_STAKE_POLICY_ID"):
            StakePolicyReconciliationRegistry([
                valid_record(), valid_record()
            ])

    def test_historical_policy_does_not_resolve_live_plane(self):
        historical = valid_record(
            policy_id="HIST-150",
            version="legacy",
            stake_usd=1.5,
            intended_capital_plane=CapitalPlane.HISTORICAL,
        )
        registry = StakePolicyReconciliationRegistry([historical])
        self.assertIsNone(registry.get_authoritative_policy(CapitalPlane.LIVE))
        self.assertEqual(
            registry.get_authoritative_policy(CapitalPlane.HISTORICAL).policy_id,
            "HIST-150",
        )

    def test_inventory_classifies_each_amount_on_its_documented_plane(self):
        path = Path(__file__).resolve().parents[1] / "config" / "stake_policy_provenance.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        policies = {round(item["stake_usd"], 2): item for item in data["policies"]}
        self.assertEqual(policies[0.35]["intended_capital_plane"], "RESEARCH")
        self.assertEqual(policies[1.0]["intended_capital_plane"], "LIVE")
        self.assertEqual(policies[1.5]["intended_capital_plane"], "HISTORICAL")
        self.assertTrue(all(item["validation_status"] == "PENDING" for item in policies.values()))
        self.assertTrue(all(item["source_commit"] is None for item in policies.values()))
        self.assertFalse(data["capital_authority"])
        self.assertFalse(data["runtime_policy_mutation"])
        self.assertFalse(data["policy_selection_performed"])

    def test_non_utc_source_timestamp_is_not_complete_provenance(self):
        record = valid_record(source_modified_at_utc="2026-10-03T17:03:56+02:00")
        self.assertIn("source_modified_at_utc", record.missing_provenance())
        with self.assertRaisesRegex(ValueError, "VALIDATED_STAKE_POLICY_MISSING_PROVENANCE"):
            StakePolicyReconciliationRegistry([record])

    def test_invalid_nonfinite_values_rejected(self):
        for value in (float("nan"), float("inf"), 0.0, -1.0, True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "STAKE_POLICY_VALUE_INVALID"):
                    StakePolicyReconciliationRegistry([
                        valid_record(stake_usd=value)
                    ])


if __name__ == "__main__":
    unittest.main()
