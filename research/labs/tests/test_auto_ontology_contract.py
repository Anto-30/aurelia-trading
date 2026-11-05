"""Tests for the isolated NVIDIA Auto Ontology research contract."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from research.auto_ontology.contract import (
    EvidenceEnvelope,
    EvidenceValidationError,
    QueryPolicy,
    sha256_hex,
    validate_evidence,
)


NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
GOOD = EvidenceEnvelope(
    evidence_id="ev-001",
    source_system="aurelia-research",
    source_ref="dataset:r100:v1",
    source_commit="a" * 40,
    dataset_sha256="b" * 64,
    payload_sha256="c" * 64,
    strategy_id="S7",
    strategy_version="1.0.0",
    timeframe="1m",
    units="USD",
    grain="one-row-per-signal",
    decision_time=NOW,
    available_at=NOW - timedelta(minutes=1),
    observed_at=NOW,
    evidence_status="PASS",
)


class TestAutoOntologyResearchContract(unittest.TestCase):
    def test_accepts_valid_research_envelope(self):
        validate_evidence(GOOD)

    def test_rejects_future_available_at(self):
        with self.assertRaisesRegex(EvidenceValidationError, "look-ahead"):
            validate_evidence(replace(GOOD, available_at=NOW + timedelta(seconds=1)))

    def test_rejects_naive_timestamps(self):
        with self.assertRaisesRegex(EvidenceValidationError, "timezone-aware"):
            validate_evidence(replace(GOOD, observed_at=datetime(2026, 11, 4, 12, 0)))

    def test_rejects_bad_hash(self):
        with self.assertRaisesRegex(EvidenceValidationError, "SHA-256"):
            validate_evidence(replace(GOOD, dataset_sha256="not-a-hash"))

    def test_rejects_bad_git_commit(self):
        with self.assertRaisesRegex(EvidenceValidationError, "Git SHA"):
            validate_evidence(replace(GOOD, source_commit="main"))

    def test_rejects_non_research_scope(self):
        with self.assertRaisesRegex(EvidenceValidationError, "RESEARCH"):
            validate_evidence(replace(GOOD, data_scope="PRODUCTION"))

    def test_rejects_capital_authority(self):
        with self.assertRaisesRegex(EvidenceValidationError, "capital_authority"):
            validate_evidence(replace(GOOD, capital_authority=True))

    def test_rejects_live_order_submission(self):
        with self.assertRaisesRegex(EvidenceValidationError, "live_order_submission"):
            validate_evidence(replace(GOOD, live_order_submission=True))

    def test_unknown_is_preserved_not_promoted(self):
        unknown = replace(GOOD, evidence_status="UNKNOWN")
        validate_evidence(unknown)
        self.assertNotEqual(unknown.evidence_status, "PASS")

    def test_rejects_unregistered_query(self):
        policy = QueryPolicy({"signals_v1": "SELECT signal FROM research_signals"})
        with self.assertRaisesRegex(EvidenceValidationError, "not allowlisted"):
            policy.validate("other_query", "SELECT signal FROM research_signals")

    def test_rejects_generated_sql_mismatch(self):
        policy = QueryPolicy({"signals_v1": "SELECT signal FROM research_signals"})
        with self.assertRaisesRegex(EvidenceValidationError, "exactly match"):
            policy.validate("signals_v1", "SELECT * FROM research_signals")

    def test_rejects_non_select_template(self):
        policy = QueryPolicy({"bad": "DELETE FROM research_signals"})
        with self.assertRaisesRegex(EvidenceValidationError, "SELECT"):
            policy.validate("bad", "DELETE FROM research_signals")

    def test_rejects_multi_statement_template(self):
        policy = QueryPolicy({"bad": "SELECT 1; SELECT 2"})
        with self.assertRaisesRegex(EvidenceValidationError, "multiple"):
            policy.validate("bad", "SELECT 1; SELECT 2")

    def test_sha256_is_deterministic(self):
        self.assertEqual(sha256_hex(b"aurelia"), sha256_hex(b"aurelia"))
        self.assertEqual(len(sha256_hex(b"aurelia")), 64)


if __name__ == "__main__":
    unittest.main()
