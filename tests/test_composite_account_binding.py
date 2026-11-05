from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet

from runtime.core.models import (
    AURELIAIdentity,
    AccountContext,
    BrokerReturnedUUID,
    CompositeAccountIdentity,
    DerivAccountIdentifier,
    LoginID,
)
from runtime.core.persistent import BrokerUUIDToLoginBinding
from runtime.core.account_binding_store import EncryptedAccountBindingStore


def make_identity(
    *, account_id: str = "DOT90004580",
    legacy_loginid: str | None = None,
) -> CompositeAccountIdentity:
    now = datetime.now(timezone.utc)
    aurelia = AURELIAIdentity(str(uuid4()), now, "test-version")
    deriv = DerivAccountIdentifier(
        account_id=account_id,
        account_type="real",
        status="active",
        group="row",
        currency="USD",
        balance=100.0,
        legacy_loginid=legacy_loginid,
    )
    broker_uuid = BrokerReturnedUUID(None, "not_returned", None)
    login_id = LoginID(None, "not_returned")
    context = AccountContext("OPTIONS", "REAL", "USD", now)
    return CompositeAccountIdentity.create(
        aurelia, deriv, broker_uuid, login_id, context
    )


def serialize_identity(identity: CompositeAccountIdentity) -> dict:
    return {
        "aurelia": {
            "internal_uuid": identity.aurelia.internal_uuid,
            "created_at": identity.aurelia.created_at.isoformat(),
            "system_version": identity.aurelia.system_version,
        },
        "deriv_account": {
            "account_id": identity.deriv_account.account_id,
            "account_type": identity.deriv_account.account_type,
            "status": identity.deriv_account.status,
            "group": identity.deriv_account.group,
            "currency": identity.deriv_account.currency,
            "balance": float(identity.deriv_account.balance),
            "legacy_loginid": identity.deriv_account.legacy_loginid,
        },
        "broker_uuid": {
            "broker_uuid": identity.broker_uuid.broker_uuid,
            "broker_uuid_source": identity.broker_uuid.broker_uuid_source,
            "broker_uuid_timestamp": (
                identity.broker_uuid.broker_uuid_timestamp.isoformat()
                if identity.broker_uuid.broker_uuid_timestamp else None
            ),
        },
        "login_id": {
            "login_id": identity.login_id.login_id,
            "login_id_source": identity.login_id.login_id_source,
        },
        "context": {
            "product": identity.context.product,
            "environment": identity.context.environment,
            "currency": identity.context.currency,
            "currency_validated_at": identity.context.currency_validated_at.isoformat(),
        },
        "identity_checksum": identity.identity_checksum,
        "verified_at": identity.verified_at.isoformat(),
    }


def deserialize_identity(row: dict) -> CompositeAccountIdentity:
    return CompositeAccountIdentity(
        aurelia=AURELIAIdentity(
            row["aurelia"]["internal_uuid"],
            datetime.fromisoformat(row["aurelia"]["created_at"]),
            row["aurelia"]["system_version"],
        ),
        deriv_account=DerivAccountIdentifier(**row["deriv_account"]),
        broker_uuid=BrokerReturnedUUID(
            row["broker_uuid"]["broker_uuid"],
            row["broker_uuid"]["broker_uuid_source"],
            datetime.fromisoformat(row["broker_uuid"]["broker_uuid_timestamp"])
            if row["broker_uuid"]["broker_uuid_timestamp"] else None,
        ),
        login_id=LoginID(**row["login_id"]),
        context=AccountContext(
            product=row["context"]["product"],
            environment=row["context"]["environment"],
            currency=row["context"]["currency"],
            currency_validated_at=datetime.fromisoformat(row["context"]["currency_validated_at"]),
        ),
        identity_checksum=row["identity_checksum"],
        verified_at=datetime.fromisoformat(row["verified_at"]),
    )


class FakeExistingPersistentBindingStore:
    """Test-only plaintext fake for adapter contract tests; not production persistence."""

    def __init__(self, path: Path):
        self.path = path
        self.rows = json.loads(path.read_text()) if path.exists() else {}
        self.bind_calls = 0

    def _save(self):
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.rows, sort_keys=True))
        temp.replace(self.path)

    def bind_account(self, identity: CompositeAccountIdentity) -> None:
        self.bind_calls += 1
        key = identity.aurelia.internal_uuid
        existing = self.rows.get(key)
        serialized = serialize_identity(identity)
        if existing is not None and existing != serialized:
            raise ValueError("IDENTITY_BINDING_CONFLICT")
        self.rows[key] = serialized
        self._save()

    def get_binding_by_aurelia_uuid(self, aurelia_uuid: str):
        row = self.rows.get(aurelia_uuid)
        return deserialize_identity(row) if row else None

    def get_binding_by_deriv_account_id(self, account_id: str):
        matches = [
            row for row in self.rows.values()
            if row["deriv_account"]["account_id"] == account_id
        ]
        if len(matches) > 1:
            raise ValueError("AMBIGUOUS_DERIV_ACCOUNT_ID_BINDING")
        return deserialize_identity(matches[0]) if matches else None

    def get_binding_by_deriv_loginid(self, deriv_loginid: str):
        matches = [
            row for row in self.rows.values()
            if row["deriv_account"].get("legacy_loginid") == deriv_loginid
        ]
        if len(matches) > 1:
            raise ValueError("AMBIGUOUS_LEGACY_DERIV_LOGINID_BINDING")
        return deserialize_identity(matches[0]) if matches else None


class BrokerUUIDToLoginBindingTests(unittest.TestCase):
    def test_binding_delegates_to_injected_existing_store(self):
        with tempfile.TemporaryDirectory() as td:
            store = FakeExistingPersistentBindingStore(Path(td) / "bindings.json")
            binding = BrokerUUIDToLoginBinding(store)
            identity = make_identity()
            binding.bind_complete_identity(identity)
            self.assertEqual(store.bind_calls, 1)
            self.assertFalse(hasattr(binding, "_bindings"))
            self.assertTrue(binding.validate_binding_integrity(identity.aurelia.internal_uuid))

    def test_binding_persists_across_store_and_adapter_reconstruction(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bindings.json"
            identity = make_identity()
            first = BrokerUUIDToLoginBinding(FakeExistingPersistentBindingStore(path))
            first.bind_complete_identity(identity)

            second_store = FakeExistingPersistentBindingStore(path)
            second = BrokerUUIDToLoginBinding(second_store)
            restored = second.get_binding_by_aurelia_uuid(identity.aurelia.internal_uuid)
            self.assertIsNotNone(restored)
            self.assertEqual(restored.identity_checksum, identity.identity_checksum)
            self.assertEqual(restored.deriv_account.account_id, "DOT90004580")
            self.assertTrue(second.validate_binding_integrity(identity.aurelia.internal_uuid))

    def test_lookup_by_deriv_account_id_uses_injected_store(self):
        with tempfile.TemporaryDirectory() as td:
            store = FakeExistingPersistentBindingStore(Path(td) / "bindings.json")
            binding = BrokerUUIDToLoginBinding(store)
            identity = make_identity()
            binding.bind_complete_identity(identity)
            self.assertEqual(
                binding.get_binding_by_deriv_account_id("DOT90004580").aurelia.internal_uuid,
                identity.aurelia.internal_uuid,
            )

    def test_legacy_loginid_is_optional_and_never_used_as_account_id(self):
        with tempfile.TemporaryDirectory() as td:
            store = FakeExistingPersistentBindingStore(Path(td) / "bindings.json")
            binding = BrokerUUIDToLoginBinding(store)
            identity = make_identity(legacy_loginid="CR123456")
            binding.bind_complete_identity(identity)
            self.assertEqual(
                binding.get_binding_by_deriv_loginid("CR123456").deriv_account.account_id,
                "DOT90004580",
            )
            self.assertIsNone(
                binding.get_binding_by_deriv_loginid("CR000000")
            )

    def test_invalid_identity_is_rejected_before_store_write(self):
        with tempfile.TemporaryDirectory() as td:
            store = FakeExistingPersistentBindingStore(Path(td) / "bindings.json")
            binding = BrokerUUIDToLoginBinding(store)
            identity = make_identity()
            object.__setattr__(identity.deriv_account, "account_id", "DOT90004581")
            with self.assertRaisesRegex(ValueError, "IDENTITY_INTEGRITY_VALIDATION_FAILED"):
                binding.bind_complete_identity(identity)
            self.assertEqual(store.bind_calls, 0)
            self.assertFalse(store.path.exists())

    def test_missing_or_incompatible_store_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "EXISTING_ACCOUNT_BINDING_STORE_REQUIRED"):
            BrokerUUIDToLoginBinding(None)
        with self.assertRaisesRegex(TypeError, "EXISTING_ACCOUNT_BINDING_STORE_INTERFACE_INVALID"):
            BrokerUUIDToLoginBinding(object())


class EncryptedAccountBindingStoreTests(unittest.TestCase):
    def test_encrypted_store_survives_adapter_and_store_reconstruction(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "account_bindings.enc"
            key = Fernet.generate_key()
            identity = make_identity()

            first = BrokerUUIDToLoginBinding(EncryptedAccountBindingStore(path, key))
            first.bind_complete_identity(identity)

            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"gAAAA"))
            self.assertNotIn(identity.aurelia.internal_uuid.encode(), raw)
            self.assertNotIn(b"DOT90004580", raw)
            self.assertNotIn(b"OPTIONS", raw)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

            second = BrokerUUIDToLoginBinding(EncryptedAccountBindingStore(path, key))
            restored = second.get_binding_by_aurelia_uuid(identity.aurelia.internal_uuid)
            self.assertIsNotNone(restored)
            self.assertEqual(restored.identity_checksum, identity.identity_checksum)
            self.assertEqual(
                second.get_binding_by_deriv_account_id("DOT90004580").aurelia.internal_uuid,
                identity.aurelia.internal_uuid,
            )

    def test_missing_store_is_empty_and_does_not_create_plaintext_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "account_bindings.enc"
            store = EncryptedAccountBindingStore(path, Fernet.generate_key())
            self.assertIsNone(store.get_binding_by_aurelia_uuid(str(uuid4())))
            self.assertFalse(path.exists())

    def test_wrong_encryption_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "account_bindings.enc"
            identity = make_identity()
            EncryptedAccountBindingStore(path, Fernet.generate_key()).bind_account(identity)

            wrong_key_store = EncryptedAccountBindingStore(path, Fernet.generate_key())
            with self.assertRaisesRegex(RuntimeError, "ACCOUNT_BINDING_STORE_AUTHENTICATION_FAILED"):
                wrong_key_store.get_binding_by_aurelia_uuid(identity.aurelia.internal_uuid)

    def test_ciphertext_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "account_bindings.enc"
            key = Fernet.generate_key()
            identity = make_identity()
            EncryptedAccountBindingStore(path, key).bind_account(identity)

            ciphertext = bytearray(path.read_bytes())
            position = len(ciphertext) // 2
            ciphertext[position] = ord("A") if ciphertext[position] != ord("A") else ord("B")
            path.write_bytes(ciphertext)

            store = EncryptedAccountBindingStore(path, key)
            with self.assertRaisesRegex(RuntimeError, "ACCOUNT_BINDING_STORE_AUTHENTICATION_FAILED"):
                store.get_binding_by_aurelia_uuid(identity.aurelia.internal_uuid)

    def test_conflicting_modern_account_id_cannot_be_bound_to_two_internal_accounts(self):
        with tempfile.TemporaryDirectory() as td:
            store = EncryptedAccountBindingStore(Path(td) / "account_bindings.enc", Fernet.generate_key())
            first = make_identity(account_id="DOT90004580")
            second = make_identity(account_id="DOT90004580")
            store.bind_account(first)
            with self.assertRaisesRegex(ValueError, "DERIV_ACCOUNT_ID_ALREADY_BOUND"):
                store.bind_account(second)

    def test_distinct_modern_accounts_may_share_legacy_loginid(self):
        with tempfile.TemporaryDirectory() as td:
            store = EncryptedAccountBindingStore(Path(td) / "account_bindings.enc", Fernet.generate_key())
            store.bind_account(make_identity(account_id="DOT90004580", legacy_loginid="CR123456"))
            store.bind_account(make_identity(account_id="DOT90004581", legacy_loginid="CR123456"))
            with self.assertRaisesRegex(RuntimeError, "AMBIGUOUS_LEGACY_DERIV_LOGINID_BINDING"):
                store.get_binding_by_deriv_loginid("CR123456")

    def test_legacy_v1_store_fails_closed_and_requires_explicit_rebind(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "account_bindings.enc"
            key = Fernet.generate_key()
            payload = json.dumps({
                "schema": "aurelia.account_bindings.v1",
                "records": {},
            }).encode("utf-8")
            path.write_bytes(Fernet(key).encrypt(payload))
            path.chmod(0o600)
            store = EncryptedAccountBindingStore(path, key)
            with self.assertRaisesRegex(
                RuntimeError,
                "ACCOUNT_BINDING_SCHEMA_V1_REQUIRES_EXPLICIT_REBIND",
            ):
                store.get_binding_by_aurelia_uuid(str(uuid4()))

    def test_incomplete_or_invalid_encryption_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "ACCOUNT_BINDING_ENCRYPTION_KEY_REQUIRED"):
                EncryptedAccountBindingStore(Path(td) / "account_bindings.enc", b"")
            with self.assertRaisesRegex(ValueError, "ACCOUNT_BINDING_ENCRYPTION_KEY_INVALID"):
                EncryptedAccountBindingStore(Path(td) / "account_bindings.enc", b"not-a-fernet-key")


if __name__ == "__main__":
    unittest.main()
