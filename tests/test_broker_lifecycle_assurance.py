from __future__ import annotations

import unittest
from types import SimpleNamespace
from uuid import uuid4

from runtime.adapters.deriv_lifecycle import AURELIABrokerLifecycleAssurance


class FakeIdentity:
    def __init__(self, valid: bool = True, aurelia_uuid: str | None = None):
        self.valid = valid
        self.aurelia = (
            SimpleNamespace(internal_uuid=aurelia_uuid)
            if aurelia_uuid is not None else None
        )

    def validate_integrity(self) -> bool:
        return self.valid


class FakeVerifier:
    def __init__(self, transport, identity=None, adapter=None, replace_transport=False):
        self.transport = transport
        self.identity = identity or FakeIdentity()
        self.adapter = adapter
        self.replace_transport = replace_transport
        self.calls = 0

    async def verify_complete_identity(self):
        self.calls += 1
        if self.replace_transport:
            self.adapter.transport = object()
        return self.identity


class FakeEvidenceAcquirer:
    def __init__(self, transport, evidence=None):
        self.transport = transport
        self.evidence = evidence or {
            "identity": {"identity_checksum": "a" * 64},
            "balance": {"currency": "USD", "available_balance": 100.0},
            "account_status": {"status": "READ_ONLY_TEST_FIXTURE"},
            "portfolio": {"positions": []},
            "statement": {"transactions": []},
            "timestamps": {"captured_at_utc": "2026-11-03T00:00:00+00:00"},
            "provenance": {"source": "unit-test", "source_commit": "b" * 40},
            "hashes": {"balance_sha256": "c" * 64},
        }
        self.calls = 0

    async def acquire_extended_evidence(self, identity):
        self.calls += 1
        return self.evidence


class FakeLifecycleAssessor:
    def __init__(self, transport):
        self.transport = transport
        self.calls = 0
        self.adapter = None

    async def execute_lifecycle_tests(self, *, adapter, identity, evidence):
        self.calls += 1
        self.adapter = adapter
        return {
            # This is an injected unit-test double, not broker-side evidence.
            "authentication": "PASS",
            "connection": "PASS",
            "heartbeat": "PASS",
            "controlled_disconnect": "PASS",
            "fresh_otp_reconnect": "PASS",
            "state_recovery": "PASS",
            "reconciliation": "PASS",
            "clean_shutdown": "PASS",
            "test_scope": "UNIT_TEST_DOUBLE_ONLY",
        }


class FakePolicyRegistry:
    def export_reconciliation_report(self):
        return {
            "policy_count": 3,
            "authoritative_policy_count": 0,
            "policies": [],
        }


class FakeAdapter:
    def __init__(self):
        self.transport = object()
        self.connect_calls = 0

    async def connect(self):
        self.connect_calls += 1
        raise AssertionError("assurance must not establish a new connection")


def make_assurance(*, evidence=None, identity=None, replace_transport=False):
    adapter = FakeAdapter()
    expected_aurelia_uuid = str(uuid4())
    verified_identity = identity or FakeIdentity(aurelia_uuid=expected_aurelia_uuid)
    verifier = FakeVerifier(
        adapter.transport,
        identity=verified_identity,
        adapter=adapter,
        replace_transport=replace_transport,
    )
    acquirer = FakeEvidenceAcquirer(adapter.transport, evidence=evidence)
    lifecycle = FakeLifecycleAssessor(adapter.transport)
    assurance = AURELIABrokerLifecycleAssurance(
        existing_adapter=adapter,
        aurelia_uuid=expected_aurelia_uuid,
        identity_verifier=verifier,
        evidence_acquirer=acquirer,
        lifecycle_assessor=lifecycle,
        stake_policy_registry=FakePolicyRegistry(),
    )
    return assurance, adapter, verifier, acquirer, lifecycle


class BrokerLifecycleAssuranceTests(unittest.IsolatedAsyncioTestCase):
    async def test_assurance_reuses_injected_adapter_and_transport(self):
        assurance, adapter, verifier, acquirer, lifecycle = make_assurance()
        canonical_transport = adapter.transport

        report = await assurance.execute_complete_assurance()

        self.assertEqual(report.status, "COMPLETED")
        self.assertTrue(report.transport_reused)
        self.assertIsNone(report.new_connections_created)
        self.assertIs(adapter.transport, canonical_transport)
        self.assertIs(lifecycle.adapter, adapter)
        self.assertEqual(adapter.connect_calls, 0)
        self.assertEqual(verifier.calls, 1)
        self.assertEqual(acquirer.calls, 1)

    async def test_no_transport_factory_or_connection_method_is_invoked(self):
        assurance, adapter, *_ = make_assurance()
        transport_before = adapter.transport
        await assurance.execute_complete_assurance()
        self.assertIs(adapter.transport, transport_before)
        self.assertEqual(adapter.connect_calls, 0)

    async def test_rejects_verifier_bound_to_different_transport(self):
        adapter = FakeAdapter()
        verifier = FakeVerifier(object())
        with self.assertRaisesRegex(ValueError, "IDENTITY_VERIFIER_MUST_USE_CANONICAL_TRANSPORT"):
            AURELIABrokerLifecycleAssurance(
                existing_adapter=adapter,
                aurelia_uuid=str(uuid4()),
                identity_verifier=verifier,
                evidence_acquirer=FakeEvidenceAcquirer(adapter.transport),
                lifecycle_assessor=FakeLifecycleAssessor(adapter.transport),
                stake_policy_registry=FakePolicyRegistry(),
            )

    async def test_rejects_lifecycle_assessor_with_noncanonical_transport(self):
        adapter = FakeAdapter()
        lifecycle = FakeLifecycleAssessor(object())
        with self.assertRaisesRegex(ValueError, "LIFECYCLE_ASSESSOR_MUST_USE_CANONICAL_TRANSPORT"):
            AURELIABrokerLifecycleAssurance(
                existing_adapter=adapter,
                aurelia_uuid=str(uuid4()),
                identity_verifier=FakeVerifier(adapter.transport),
                evidence_acquirer=FakeEvidenceAcquirer(adapter.transport),
                lifecycle_assessor=lifecycle,
                stake_policy_registry=FakePolicyRegistry(),
            )

    async def test_rejects_missing_existing_transport(self):
        adapter = SimpleNamespace(transport=None)
        with self.assertRaisesRegex(ValueError, "CANONICAL_AURELIA_TRANSPORT_REQUIRED"):
            AURELIABrokerLifecycleAssurance(
                existing_adapter=adapter,
                aurelia_uuid=str(uuid4()),
                identity_verifier=FakeVerifier(None),
                evidence_acquirer=FakeEvidenceAcquirer(None),
                lifecycle_assessor=FakeLifecycleAssessor(None),
                stake_policy_registry=FakePolicyRegistry(),
            )

    async def test_rejects_invalid_aurelia_uuid(self):
        adapter = FakeAdapter()
        with self.assertRaisesRegex(ValueError, "AURELIA_UUID_INVALID"):
            AURELIABrokerLifecycleAssurance(
                existing_adapter=adapter,
                aurelia_uuid="not-a-uuid",
                identity_verifier=FakeVerifier(adapter.transport),
                evidence_acquirer=FakeEvidenceAcquirer(adapter.transport),
                lifecycle_assessor=FakeLifecycleAssessor(adapter.transport),
                stake_policy_registry=FakePolicyRegistry(),
            )

    async def test_identity_integrity_failure_blocks_all_following_phases(self):
        assurance, adapter, verifier, acquirer, lifecycle = make_assurance(
            identity=FakeIdentity(valid=False)
        )
        report = await assurance.execute_complete_assurance()
        self.assertEqual(report.status, "FAILED")
        self.assertEqual(report.failure_reason, "ValueError")
        self.assertFalse(report.evidence_acquired)
        self.assertEqual(acquirer.calls, 0)
        self.assertEqual(lifecycle.calls, 0)

    async def test_mismatched_aurelia_identity_blocks_evidence_and_lifecycle(self):
        assurance, _, _, acquirer, lifecycle = make_assurance(
            identity=FakeIdentity(aurelia_uuid=str(uuid4()))
        )

        report = await assurance.execute_complete_assurance()

        self.assertEqual(report.status, "FAILED")
        self.assertEqual(report.failure_reason, "ValueError")
        self.assertFalse(report.identity_verified)
        self.assertFalse(report.evidence_acquired)
        self.assertEqual(acquirer.calls, 0)
        self.assertEqual(lifecycle.calls, 0)

    async def test_missing_required_evidence_field_fails_closed(self):
        evidence = {"identity": {}, "balance": {}, "account_status": {}}
        assurance, _, _, _, lifecycle = make_assurance(evidence=evidence)
        report = await assurance.execute_complete_assurance()
        self.assertEqual(report.status, "FAILED")
        self.assertEqual(report.failure_reason, "ValueError")
        self.assertFalse(report.evidence_acquired)
        self.assertEqual(lifecycle.calls, 0)

    async def test_pii_and_credentials_are_rejected_without_echoing_values(self):
        assurance, _, _, _, lifecycle = make_assurance()
        assurance.evidence_acquirer.evidence["identity"]["email"] = "private@example.invalid"
        report = await assurance.execute_complete_assurance()
        self.assertEqual(report.status, "FAILED")
        self.assertEqual(report.failure_reason, "ValueError")
        self.assertNotIn("private@example.invalid", str(report))
        self.assertEqual(lifecycle.calls, 0)

    async def test_transport_replacement_during_assurance_fails(self):
        assurance, adapter, *_ = make_assurance(replace_transport=True)
        report = await assurance.execute_complete_assurance()
        self.assertEqual(report.status, "FAILED")
        self.assertEqual(report.failure_reason, "RuntimeError")
        self.assertFalse(report.transport_reused)
        self.assertIsNone(report.new_connections_created)

    async def test_unrun_lifecycle_phases_cannot_be_reported_as_complete(self):
        assurance, _, _, _, lifecycle_assessor = make_assurance()
        async def incomplete(**_kwargs):
            return {
                "authentication": "not_run",
                "connection": "PASS",
                "heartbeat": "PASS",
                "controlled_disconnect": "PASS",
                "fresh_otp_reconnect": "not_run",
                "state_recovery": "not_run",
                "reconciliation": "not_run",
                "clean_shutdown": "PASS",
            }
        lifecycle_assessor.execute_lifecycle_tests = incomplete
        report = await assurance.execute_complete_assurance()
        self.assertEqual(report.status, "FAILED")
        self.assertFalse(report.lifecycle_assessment_completed)
        self.assertEqual(report.failure_reason, "ValueError")


if __name__ == "__main__":
    unittest.main()
