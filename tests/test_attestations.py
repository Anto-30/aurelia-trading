import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.ops.attestations import (
    AttestationError,
    sign_attestation,
    verify_attestation,
    write_attestation,
)


class AttestationTests(unittest.TestCase):
    def base(self):
        now = datetime.now(timezone.utc)
        return {
            "issuer": "AURELIA-control-plane",
            "subject": "runtime-1",
            "capability": "RISK_WARDEN",
            "status": "PASS",
            "issued_at_utc": now.isoformat(),
            "expires_at_utc": (now + timedelta(minutes=5)).isoformat(),
            "source_sha": "abc123",
            "runtime_id": "runtime-1",
            "config_hash": "cfg123",
            "evidence_hash": "ev123",
            "provenance": "control_plane",
        }

    def test_valid_attestation(self):
        record = sign_attestation(self.base(), "test-secret")
        result = verify_attestation(
            record,
            signing_key="test-secret",
            expected_source_sha="abc123",
            expected_runtime_id="runtime-1",
            expected_config_hash="cfg123",
        )
        self.assertEqual(result.capability, "RISK_WARDEN")

    def test_source_mismatch_is_rejected(self):
        record = sign_attestation(self.base(), "test-secret")
        with self.assertRaises(AttestationError):
            verify_attestation(
                record,
                signing_key="test-secret",
                expected_source_sha="different",
                expected_runtime_id="runtime-1",
                expected_config_hash="cfg123",
            )

    def test_expired_attestation_is_rejected(self):
        record = self.base()
        now = datetime.now(timezone.utc)
        record["issued_at_utc"] = (now - timedelta(minutes=10)).isoformat()
        record["expires_at_utc"] = (now - timedelta(minutes=1)).isoformat()
        record = sign_attestation(record, "test-secret")
        with self.assertRaises(AttestationError):
            verify_attestation(
                record,
                signing_key="test-secret",
                expected_source_sha="abc123",
                expected_runtime_id="runtime-1",
                expected_config_hash="cfg123",
            )

    def test_tampering_is_rejected(self):
        record = sign_attestation(self.base(), "test-secret")
        record["evidence_hash"] = "tampered"
        with self.assertRaises(AttestationError):
            verify_attestation(
                record,
                signing_key="test-secret",
                expected_source_sha="abc123",
                expected_runtime_id="runtime-1",
                expected_config_hash="cfg123",
            )

    def test_persisted_artifact_roundtrip(self):
        record = sign_attestation(self.base(), "test-secret")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "risk.json"
            write_attestation(path, record)
            self.assertTrue(path.exists())
