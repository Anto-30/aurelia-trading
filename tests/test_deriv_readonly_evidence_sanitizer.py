from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.sanitize_deriv_readonly_evidence import AttestationError, build_attestation
from scripts.run_redacted_deriv_verifier import redacted_status_lines


class DerivReadOnlySanitizerTests(unittest.TestCase):
    def _record(self) -> dict:
        record = {
            "evidence_id": "DERIV_AUTH_SESSION:20261025T120000Z",
            "source_hash": "a" * 40,
            "record_hash": "b" * 64,
            "status": "CURRENT",
            "result": "PROVEN",
            "environment": "real",
            "ended_at_utc": "2026-10-25T12:00:00+00:00",
            "verification_scope": "AUTHENTICATED_DERIV_REAL_SESSION",
            "invariants_checked": [
                "exact_real_account_binding",
                "no_order_submission",
                "capital_authority_not_granted",
            ],
            "invariants_failed": [],
            "orders_submitted": 0,
            "capital_authority_granted": False,
            "order_submission_permitted": False,
            "observed": {
                "account_loginid": "CR-SENSITIVE-ACCOUNT",
                "balance": 12.34,
                "available_balance": 11.11,
            },
        }
        return self._rehash(record)

    @staticmethod
    def _rehash(record: dict) -> dict:
        record.pop("record_hash", None)
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        record["record_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return record

    def test_attestation_excludes_raw_account_and_financial_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.json"
            raw = json.dumps(self._record()).encode()
            path.write_bytes(raw)
            result = build_attestation(
                path,
                evidence_type="session",
                source_commit="a" * 40,
                workflow_run_id="123",
                workflow_run_attempt="1",
            )
        encoded = json.dumps(result)
        self.assertEqual(result["raw_evidence_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertNotIn("observed", result)
        self.assertNotIn("CR-SENSITIVE-ACCOUNT", encoded)
        self.assertNotIn("12.34", encoded)
        self.assertEqual(result["orders_submitted"], 0)
        self.assertIs(result["capital_authority_granted"], False)
        self.assertIs(result["order_submission_permitted"], False)

    def test_mismatched_source_commit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.json"
            path.write_text(json.dumps(self._record()), encoding="utf-8")
            with self.assertRaisesRegex(AttestationError, "EVIDENCE_SOURCE_COMMIT_MISMATCH"):
                build_attestation(
                    path,
                    evidence_type="session",
                    source_commit="c" * 40,
                    workflow_run_id="123",
                    workflow_run_attempt="1",
                )

    def test_authority_or_order_permission_true_fails_closed(self) -> None:
        for field in ("capital_authority_granted", "order_submission_permitted"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                record = self._record()
                record[field] = True
                record = self._rehash(record)
                path = Path(tmp) / "raw.json"
                path.write_text(json.dumps(record), encoding="utf-8")
                with self.assertRaises(AttestationError):
                    build_attestation(
                        path,
                        evidence_type="session",
                        source_commit="a" * 40,
                        workflow_run_id="123",
                        workflow_run_attempt="1",
                    )

    def test_log_redaction_allows_status_not_account_identifiers(self) -> None:
        output = "\n".join(
            [
                "DERIV_AUTH_SESSION=VERIFIED",
                "DERIV_ACCOUNT_LOGINID=CR-SENSITIVE-ACCOUNT",
                "DERIV_ACCOUNT_CURRENCY=USD",
                "DERIV_AUTH_SESSION_REASON=ACCOUNT_IDENTITY_MISMATCH",
            ]
        )
        self.assertEqual(
            redacted_status_lines(output),
            [
                "DERIV_AUTH_SESSION=VERIFIED",
                "DERIV_AUTH_SESSION_REASON=ACCOUNT_IDENTITY_MISMATCH",
            ],
        )


if __name__ == "__main__":
    unittest.main()
