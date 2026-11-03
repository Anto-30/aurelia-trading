from __future__ import annotations

import unittest
from datetime import datetime, timezone

from runtime.core.stake_sizing import (
    CapitalPlane,
    StakePolicyRecord,
    StakePolicyReconciliationRegistry,
    StakePolicyStatus,
)


UTC = timezone.utc
COMMIT = "a" * 40


def documented_policy(value: float, *, plane: CapitalPlane = CapitalPlane.LIVE) -> StakePolicyRecord:
    now = datetime.now(UTC)
    return StakePolicyRecord(
        stake_value=value,
        source_document="docs/test-policy.md",
        source_commit=COMMIT,
        approval_authority="test-review-authority",
        approval_date=now,
        effective_date=now,
        intended_capital_plane=plane,
        rationale="Unit-test fixture only; not a production approval.",
        validation_status=StakePolicyStatus.VALIDATED,
    )


class StakePolicyReconciliationRegistryTests(unittest.TestCase):
    def test_incomplete_provenance_is_rejected_from_authoritative_registry(self) -> None:
        registry = StakePolicyReconciliationRegistry()
        incomplete = StakePolicyRecord(
            stake_value=1.0,
            source_document=None,
            source_commit=None,
            approval_authority=None,
            approval_date=None,
            effective_date=None,
            intended_capital_plane=CapitalPlane.LIVE,
            rationale=None,
        )
        with self.assertRaisesRegex(ValueError, "STAKE_POLICY_PROVENANCE_INCOMPLETE"):
            registry.register_policy(incomplete)
        self.assertIsNone(registry.get_authoritative_policy(CapitalPlane.LIVE))

    def test_multiple_validated_policies_for_same_plane_are_blocked(self) -> None:
        registry = StakePolicyReconciliationRegistry()
        registry.register_policy(documented_policy(1.0))
        registry.register_policy(documented_policy(1.5))
        with self.assertRaisesRegex(
            ValueError, "MULTIPLE_VALIDATED_STAKE_POLICIES_FOR_LIVE"
        ):
            registry.get_authoritative_policy(CapitalPlane.LIVE)

    def test_exactly_one_validated_policy_is_returned_for_its_plane(self) -> None:
        registry = StakePolicyReconciliationRegistry()
        policy = documented_policy(1.0, plane=CapitalPlane.RESEARCH)
        registry.register_policy(policy)
        self.assertIsNone(registry.get_authoritative_policy(CapitalPlane.LIVE))
        self.assertIs(registry.get_authoritative_policy(CapitalPlane.RESEARCH), policy)

    def test_user_supplied_stake_candidates_remain_unverified(self) -> None:
        registry = StakePolicyReconciliationRegistry()
        for value in (0.35, 1.00, 1.50):
            registry.record_candidate(StakePolicyRecord(
                stake_value=value,
                source_document=None,
                source_commit=None,
                approval_authority=None,
                approval_date=None,
                effective_date=None,
                intended_capital_plane=None,
                rationale=None,
                validation_status=StakePolicyStatus.PENDING,
            ))

        report = registry.export_reconciliation_report()
        self.assertEqual(
            [row["stake_value"] for row in report["policies"]],
            [0.35, 1.00, 1.50],
        )
        self.assertEqual(report["authoritative_policy_count"], 0)
        self.assertTrue(all(not row["authoritative"] for row in report["policies"]))
        self.assertTrue(all(row["provenance_gaps"] for row in report["policies"]))

    def test_invalid_candidate_value_is_rejected(self) -> None:
        registry = StakePolicyReconciliationRegistry()
        invalid = StakePolicyRecord(
            stake_value=float("nan"),
            source_document=None,
            source_commit=None,
            approval_authority=None,
            approval_date=None,
            effective_date=None,
            intended_capital_plane=None,
            rationale=None,
        )
        with self.assertRaisesRegex(ValueError, "STAKE_POLICY_CANDIDATE_INVALID"):
            registry.record_candidate(invalid)

    def test_current_numeric_policy_remains_one_percent_with_one_dollar_minimum(self) -> None:
        from runtime.core.stake_sizing import (
            DEFAULT_MAX_TRADE_RISK_FRACTION,
            DEFAULT_MINIMUM_STAKE,
            size_stake_for_balance,
        )
        self.assertEqual(DEFAULT_MAX_TRADE_RISK_FRACTION, 0.01)
        self.assertEqual(DEFAULT_MINIMUM_STAKE, 1.0)
        result = size_stake_for_balance(1.45)
        self.assertFalse(result.allowed)
        self.assertIsNone(result.stake)
        self.assertEqual(result.reason, "STAKE_RISK_BUDGET_BELOW_BROKER_MINIMUM")


if __name__ == "__main__":
    unittest.main()
