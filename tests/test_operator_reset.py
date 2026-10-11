from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from runtime.core.operator_reset import (
    create_operator_reset_record,
    verify_operator_reset_record,
)

UTC = timezone.utc
KEY = "operator-reset-unit-test-signing-key-at-least-32-characters"
BINDING = {
    "expected_reason": "STATE_MISMATCH",
    "expected_source_sha": "source-123",
    "expected_account_loginid": "CRREAL123",
    "expected_generation": 7,
}


class OperatorResetProofTests(unittest.TestCase):
    def make_record(self, *, issued_at=None, ttl_seconds=60):
        return create_operator_reset_record(
            signing_key=KEY,
            operator_id="operator-test",
            reason="STATE_MISMATCH",
            source_sha="source-123",
            account_loginid="CRREAL123",
            kill_switch_generation=7,
            issued_at=issued_at,
            ttl_seconds=ttl_seconds,
            nonce="a" * 48,
        )

    def verify(self, record, **overrides):
        return verify_operator_reset_record(
            record,
            signing_key=KEY,
            now=datetime.now(UTC),
            **(BINDING | overrides),
        )

    def test_signed_current_proof_is_valid(self):
        record = self.make_record()
        valid, reason, nonce = self.verify(record)
        self.assertTrue(valid)
        self.assertEqual(reason, "OPERATOR_RESET_VERIFIED")
        self.assertEqual(nonce, "a" * 48)

    def test_tampering_with_signed_reason_is_rejected(self):
        record = self.make_record()
        record["reason"] = "OTHER_REASON"
        valid, reason, nonce = self.verify(record)
        self.assertFalse(valid)
        self.assertEqual(reason, "OPERATOR_RESET_REASON_MISMATCH")
        self.assertIsNone(nonce)

    def test_wrong_account_source_and_generation_are_rejected(self):
        record = self.make_record()
        for overrides, expected in (
            ({"expected_account_loginid": "CROTHER"}, "OPERATOR_RESET_ACCOUNT_MISMATCH"),
            ({"expected_source_sha": "other-source"}, "OPERATOR_RESET_SOURCE_MISMATCH"),
            ({"expected_generation": 8}, "OPERATOR_RESET_GENERATION_MISMATCH"),
        ):
            with self.subTest(expected=expected):
                valid, reason, _ = self.verify(record, **overrides)
                self.assertFalse(valid)
                self.assertEqual(reason, expected)

    def test_proof_expired_before_use_is_rejected(self):
        now = datetime.now(UTC)
        record = self.make_record(
            issued_at=now - timedelta(seconds=120),
            ttl_seconds=60,
        )
        valid, reason, nonce = self.verify(record)
        self.assertFalse(valid)
        self.assertEqual(reason, "OPERATOR_RESET_EXPIRED_OR_TEMPORALLY_INVALID")
        self.assertIsNone(nonce)

    def test_replayed_nonce_is_rejected(self):
        record = self.make_record()
        valid, reason, nonce = self.verify(record, last_consumed_nonce="a" * 48)
        self.assertFalse(valid)
        self.assertEqual(reason, "OPERATOR_RESET_REPLAYED")
        self.assertIsNone(nonce)

    def test_short_signing_key_and_excessive_ttl_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "SIGNING_KEY_TOO_SHORT"):
            create_operator_reset_record(
                signing_key="short",
                operator_id="operator-test",
                reason="STATE_MISMATCH",
                source_sha="source-123",
                account_loginid="CRREAL123",
                kill_switch_generation=7,
            )
        with self.assertRaisesRegex(ValueError, "TTL_OUT_OF_RANGE"):
            self.make_record(ttl_seconds=301)


if __name__ == "__main__":
    unittest.main()
