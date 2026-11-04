"""Authenticated-encryption account identity binding store.

This adapter is suitable only for a single-host deployment with a durable,
private local volume. The Fernet key must be injected by the caller from a
separate secret manager/KMS; it is never generated, persisted, or logged here.
For multiple replicas, use a transactional shared store with equivalent
encryption, uniqueness, locking, and recovery guarantees.
"""
from __future__ import annotations

import json
import os
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Iterator

from cryptography.fernet import Fernet, InvalidToken

from .models import (
    AURELIAIdentity,
    AccountContext,
    BrokerReturnedUUID,
    CompositeAccountIdentity,
    DerivAccountIdentifier,
    LoginID,
)
from .persistent import ExistingAccountBindingStore


_SCHEMA = "aurelia.account_bindings.v1"
_PRIVATE_MODE = 0o600
_PRIVATE_DIR_MODE = 0o700


def _serialize_identity(identity: CompositeAccountIdentity) -> dict[str, object]:
    return {
        "aurelia": {
            "internal_uuid": identity.aurelia.internal_uuid,
            "created_at": identity.aurelia.created_at.isoformat(),
            "system_version": identity.aurelia.system_version,
        },
        "deriv_account": {
            "deriv_loginid": identity.deriv_account.deriv_loginid,
            "account_type": identity.deriv_account.account_type,
            "is_disabled": identity.deriv_account.is_disabled,
            "is_virtual": identity.deriv_account.is_virtual,
        },
        "broker_uuid": {
            "broker_uuid": identity.broker_uuid.broker_uuid,
            "broker_uuid_source": identity.broker_uuid.broker_uuid_source,
            "broker_uuid_timestamp": (
                identity.broker_uuid.broker_uuid_timestamp.isoformat()
                if identity.broker_uuid.broker_uuid_timestamp is not None else None
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


def _deserialize_identity(row: object) -> CompositeAccountIdentity:
    if not isinstance(row, dict):
        raise ValueError("IDENTITY_RECORD_NOT_OBJECT")
    aurelia = row["aurelia"]
    deriv = row["deriv_account"]
    broker = row["broker_uuid"]
    login = row["login_id"]
    context = row["context"]
    if not all(isinstance(item, dict) for item in (aurelia, deriv, broker, login, context)):
        raise ValueError("IDENTITY_COMPONENT_NOT_OBJECT")

    broker_timestamp = broker["broker_uuid_timestamp"]
    identity = CompositeAccountIdentity(
        aurelia=AURELIAIdentity(
            internal_uuid=aurelia["internal_uuid"],
            created_at=datetime.fromisoformat(aurelia["created_at"]),
            system_version=aurelia["system_version"],
        ),
        deriv_account=DerivAccountIdentifier(
            deriv_loginid=deriv["deriv_loginid"],
            account_type=deriv["account_type"],
            is_disabled=deriv["is_disabled"],
            is_virtual=deriv["is_virtual"],
        ),
        broker_uuid=BrokerReturnedUUID(
            broker_uuid=broker["broker_uuid"],
            broker_uuid_source=broker["broker_uuid_source"],
            broker_uuid_timestamp=(
                datetime.fromisoformat(broker_timestamp)
                if broker_timestamp is not None else None
            ),
        ),
        login_id=LoginID(
            login_id=login["login_id"],
            login_id_source=login["login_id_source"],
        ),
        context=AccountContext(
            product=context["product"],
            environment=context["environment"],
            currency=context["currency"],
            currency_validated_at=datetime.fromisoformat(
                context["currency_validated_at"]
            ),
        ),
        identity_checksum=row["identity_checksum"],
        verified_at=datetime.fromisoformat(row["verified_at"]),
    )
    if identity.validate_integrity() is not True:
        raise ValueError("IDENTITY_CHECKSUM_OR_COMPONENT_INVALID")
    return identity


class EncryptedAccountBindingStore(ExistingAccountBindingStore):
    """Fernet-encrypted implementation of AURELIA's account-binding contract.

    Every operation reloads under an OS lock so multiple local processes do not
    overwrite one another. A temp file + fsync + atomic replace protects against
    partial writes. The store fails closed on invalid ciphertext, schema, or
    identity integrity. It deliberately has no default or recoverable key.
    """

    def __init__(self, path: str | Path, encryption_key: str | bytes):
        if encryption_key is None or encryption_key == "" or encryption_key == b"":
            raise ValueError("ACCOUNT_BINDING_ENCRYPTION_KEY_REQUIRED")
        if isinstance(encryption_key, str):
            key = encryption_key.encode("ascii", errors="strict")
        elif isinstance(encryption_key, bytes):
            key = encryption_key
        else:
            raise ValueError("ACCOUNT_BINDING_ENCRYPTION_KEY_INVALID")
        try:
            self._cipher = Fernet(key)
        except (ValueError, TypeError) as exc:
            raise ValueError("ACCOUNT_BINDING_ENCRYPTION_KEY_INVALID") from exc

        self.path = Path(path)
        self._thread_lock = RLock()
        if not self.path.name or self.path.name in {".", ".."}:
            raise ValueError("ACCOUNT_BINDING_STORE_PATH_INVALID")
        if self.path.exists() and self.path.is_symlink():
            raise RuntimeError("ACCOUNT_BINDING_STORE_SYMLINK_FORBIDDEN")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        # This is a POSIX local-filesystem implementation, not a distributed
        # lock. Production deployments must provide a durable single-host volume.
        import fcntl

        with self._thread_lock:
            self.path.parent.mkdir(mode=_PRIVATE_DIR_MODE, parents=True, exist_ok=True)
            if self.path.parent.is_symlink():
                raise RuntimeError("ACCOUNT_BINDING_STORE_DIRECTORY_SYMLINK_FORBIDDEN")
            dir_mode = stat.S_IMODE(self.path.parent.stat().st_mode)
            if dir_mode & 0o077:
                raise RuntimeError("ACCOUNT_BINDING_STORE_DIRECTORY_PERMISSIONS_TOO_BROAD")

            lock_path = self.path.with_name(self.path.name + ".lock")
            flags = os.O_CREAT | os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(lock_path, flags, _PRIVATE_MODE)
            try:
                os.fchmod(fd, _PRIVATE_MODE)
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def _read_records_unlocked(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        if self.path.is_symlink():
            raise RuntimeError("ACCOUNT_BINDING_STORE_SYMLINK_FORBIDDEN")
        file_stat = self.path.stat()
        if not stat.S_ISREG(file_stat.st_mode):
            raise RuntimeError("ACCOUNT_BINDING_STORE_NOT_REGULAR_FILE")
        if stat.S_IMODE(file_stat.st_mode) & 0o077:
            raise RuntimeError("ACCOUNT_BINDING_STORE_PERMISSIONS_TOO_BROAD")

        try:
            token = self.path.read_bytes()
            plaintext = self._cipher.decrypt(token)
        except (InvalidToken, OSError, ValueError) as exc:
            raise RuntimeError(
                "ACCOUNT_BINDING_STORE_AUTHENTICATION_FAILED"
            ) from exc

        try:
            payload = json.loads(plaintext.decode("utf-8"))
            if not isinstance(payload, dict) or payload.get("schema") != _SCHEMA:
                raise ValueError("SCHEMA_MISMATCH")
            records = payload.get("records")
            if not isinstance(records, dict):
                raise ValueError("RECORDS_NOT_OBJECT")
            validated: dict[str, dict[str, object]] = {}
            for key, row in records.items():
                identity = _deserialize_identity(row)
                if key != identity.aurelia.internal_uuid:
                    raise ValueError("AURELIA_IDENTITY_KEY_MISMATCH")
                validated[key] = _serialize_identity(identity)
            return validated
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("ACCOUNT_BINDING_STORE_FORMAT_INVALID") from exc

    def _write_records_unlocked(self, records: dict[str, dict[str, object]]) -> None:
        payload = {
            "schema": _SCHEMA,
            "records": records,
        }
        plaintext = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        ciphertext = self._cipher.encrypt(plaintext)

        fd, temp_name = tempfile.mkstemp(
            prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent
        )
        temp_path = Path(temp_name)
        try:
            os.fchmod(fd, _PRIVATE_MODE)
            with os.fdopen(fd, "wb") as handle:
                handle.write(ciphertext)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            os.chmod(self.path, _PRIVATE_MODE)
            dir_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            finally:
                raise

    def bind_account(self, identity: CompositeAccountIdentity) -> None:
        if (
            not isinstance(identity, CompositeAccountIdentity)
            or identity.validate_integrity() is not True
        ):
            raise ValueError("IDENTITY_INTEGRITY_VALIDATION_FAILED")
        row = _serialize_identity(identity)
        aurelia_uuid = identity.aurelia.internal_uuid
        deriv_loginid = identity.deriv_account.deriv_loginid

        with self._locked():
            records = self._read_records_unlocked()
            existing = records.get(aurelia_uuid)
            if existing is not None and existing != row:
                raise ValueError("IDENTITY_BINDING_CONFLICT")
            for other_uuid, other_row in records.items():
                if (
                    other_uuid != aurelia_uuid
                    and other_row["deriv_account"]["deriv_loginid"] == deriv_loginid
                ):
                    raise ValueError("DERIV_LOGINID_ALREADY_BOUND")
            if existing is None:
                records[aurelia_uuid] = row
                self._write_records_unlocked(records)

    def get_binding_by_aurelia_uuid(
        self, aurelia_uuid: str
    ) -> CompositeAccountIdentity | None:
        if not isinstance(aurelia_uuid, str) or not aurelia_uuid.strip():
            raise ValueError("AURELIA_UUID_REQUIRED")
        with self._locked():
            records = self._read_records_unlocked()
            row = records.get(aurelia_uuid)
            return _deserialize_identity(row) if row is not None else None

    def get_binding_by_deriv_loginid(
        self, deriv_loginid: str
    ) -> CompositeAccountIdentity | None:
        if not isinstance(deriv_loginid, str) or not deriv_loginid.strip():
            raise ValueError("DERIV_LOGINID_REQUIRED")
        with self._locked():
            records = self._read_records_unlocked()
            matches = [
                row for row in records.values()
                if row["deriv_account"]["deriv_loginid"] == deriv_loginid
            ]
            if len(matches) > 1:
                raise RuntimeError("AMBIGUOUS_DERIV_LOGINID_BINDING")
            return _deserialize_identity(matches[0]) if matches else None
