"""Authenticated-encryption account identity binding store.

This adapter is suitable only for a single-host deployment with a durable,
private local volume. The Fernet key must be injected by the caller from a
separate secret manager/KMS; it is never generated, persisted, or logged here.
For multiple replicas, use a transactional shared store with equivalent
encryption, uniqueness, locking, and recovery guarantees.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import UUID
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
        self.oauth_path = self.path.with_name(self.path.name + ".oauth")
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

    def _read_oauth_payload_unlocked(self) -> dict[str, object]:
        """Read the encrypted OAuth sidecar under the existing binding-store lock."""
        empty = {"schema": "aurelia.oauth_credentials.v1", "pending": {}, "credentials": {}}
        path = self.oauth_path
        if not path.exists():
            return empty
        if path.is_symlink():
            raise RuntimeError("OAUTH_STORE_SYMLINK_FORBIDDEN")
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError("OAUTH_STORE_NOT_REGULAR_FILE")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError("OAUTH_STORE_PERMISSIONS_TOO_BROAD")
        try:
            plaintext = self._cipher.decrypt(path.read_bytes())
        except (InvalidToken, OSError, ValueError) as exc:
            raise RuntimeError("OAUTH_STORE_AUTHENTICATION_FAILED") from exc
        try:
            payload = json.loads(plaintext.decode("utf-8"))
            if (
                not isinstance(payload, dict)
                or payload.get("schema") != "aurelia.oauth_credentials.v1"
                or not isinstance(payload.get("pending"), dict)
                or not isinstance(payload.get("credentials"), dict)
            ):
                raise ValueError("OAUTH_STORE_SCHEMA_INVALID")
            for section in ("pending", "credentials"):
                for key, row in payload[section].items():
                    if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key) or not isinstance(row, dict):
                        raise ValueError("OAUTH_STORE_RECORD_INVALID")
            return payload
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("OAUTH_STORE_FORMAT_INVALID") from exc

    def _write_oauth_payload_unlocked(self, payload: dict[str, object]) -> None:
        plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        ciphertext = self._cipher.encrypt(plaintext)
        fd, temp_name = tempfile.mkstemp(prefix=self.oauth_path.name + ".", suffix=".tmp", dir=self.oauth_path.parent)
        temp_path = Path(temp_name)
        try:
            os.fchmod(fd, _PRIVATE_MODE)
            with os.fdopen(fd, "wb") as handle:
                handle.write(ciphertext)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.oauth_path)
            os.chmod(self.oauth_path, _PRIVATE_MODE)
            dir_fd = os.open(self.oauth_path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            finally:
                raise

    @staticmethod
    def _oauth_timestamp(value: str) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("OAUTH_TIMESTAMP_INVALID")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("OAUTH_TIMESTAMP_INVALID") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("OAUTH_TIMESTAMP_MUST_BE_UTC")
        return parsed

    @staticmethod
    def _oauth_principal_uuid(value: str) -> str:
        try:
            return str(UUID(value))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("AURELIA_OAUTH_PRINCIPAL_UUID_INVALID") from exc

    @staticmethod
    def _oauth_record_key(principal_uuid: str, app_id: str) -> str:
        return hashlib.sha256((principal_uuid + "|" + app_id).encode("utf-8")).hexdigest()

    def create_pending_oauth_authorization(
        self, *, state: str, code_verifier: str, code_challenge: str,
        code_challenge_method: str, redirect_uri: str, session_binding: str,
        app_id: str, principal_uuid: str, requested_scopes: list[str],
        created_at_utc: str, expires_at_utc: str,
    ) -> None:
        if not isinstance(state, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", state):
            raise ValueError("OAUTH_STATE_INVALID")
        if not isinstance(code_verifier, str) or not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", code_verifier):
            raise ValueError("OAUTH_CODE_VERIFIER_INVALID")
        if not isinstance(code_challenge, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", code_challenge):
            raise ValueError("OAUTH_CODE_CHALLENGE_INVALID")
        if code_challenge_method != "S256":
            raise ValueError("OAUTH_PKCE_METHOD_FORBIDDEN")
        if not isinstance(redirect_uri, str) or not redirect_uri:
            raise ValueError("OAUTH_REDIRECT_URI_REQUIRED")
        if not isinstance(session_binding, str) or len(session_binding) < 32:
            raise ValueError("OAUTH_SERVER_SESSION_BINDING_REQUIRED")
        if not isinstance(app_id, str) or not app_id.strip():
            raise ValueError("DERIV_OAUTH_APP_ID_REQUIRED")
        principal = self._oauth_principal_uuid(principal_uuid)
        if requested_scopes != ["trade"]:
            raise ValueError("DERIV_OAUTH_SCOPE_MUST_BE_TRADE_ONLY")
        created = self._oauth_timestamp(created_at_utc)
        expires = self._oauth_timestamp(expires_at_utc)
        if expires <= created or (expires - created).total_seconds() > 1800:
            raise ValueError("OAUTH_PENDING_AUTHORIZATION_TTL_INVALID")
        state_hash = hashlib.sha256(state.encode("ascii")).hexdigest()
        row = {
            "code_verifier": code_verifier,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "redirect_uri": redirect_uri,
            "session_binding_sha256": hashlib.sha256(session_binding.encode("utf-8")).hexdigest(),
            "app_id": app_id,
            "principal_uuid": principal,
            "requested_scopes": ["trade"],
            "created_at_utc": created.isoformat(),
            "expires_at_utc": expires.isoformat(),
        }
        with self._locked():
            payload = self._read_oauth_payload_unlocked()
            if state_hash in payload["pending"]:
                raise ValueError("OAUTH_STATE_ALREADY_EXISTS")
            payload["pending"][state_hash] = row
            self._write_oauth_payload_unlocked(payload)

    def consume_pending_oauth_authorization(
        self, *, state: str, session_binding: str, consumed_at_utc: str
    ) -> dict[str, object]:
        if not isinstance(state, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", state):
            raise ValueError("OAUTH_STATE_INVALID")
        if not isinstance(session_binding, str) or len(session_binding) < 32:
            raise ValueError("OAUTH_SERVER_SESSION_BINDING_REQUIRED")
        consumed = self._oauth_timestamp(consumed_at_utc)
        state_hash = hashlib.sha256(state.encode("ascii")).hexdigest()
        session_hash = hashlib.sha256(session_binding.encode("utf-8")).hexdigest()
        with self._locked():
            payload = self._read_oauth_payload_unlocked()
            row = payload["pending"].get(state_hash)
            if row is None:
                raise ValueError("OAUTH_STATE_UNKNOWN_OR_REPLAYED")
            expected = row.get("session_binding_sha256")
            if not isinstance(expected, str) or not hmac.compare_digest(expected, session_hash):
                raise ValueError("OAUTH_STATE_SESSION_MISMATCH")
            expires = self._oauth_timestamp(row.get("expires_at_utc"))
            payload["pending"].pop(state_hash, None)
            self._write_oauth_payload_unlocked(payload)
            if consumed >= expires:
                raise ValueError("OAUTH_STATE_EXPIRED")
            return dict(row)

    def store_oauth_access_token(
        self, *, principal_uuid: str, app_id: str, access_token: str,
        token_type: str, scopes: list[str], scope_source: str,
        issued_at_utc: str, expires_at_utc: str,
    ) -> None:
        principal = self._oauth_principal_uuid(principal_uuid)
        if not isinstance(app_id, str) or not app_id.strip():
            raise ValueError("DERIV_OAUTH_APP_ID_REQUIRED")
        if not isinstance(access_token, str) or not access_token.strip() or len(access_token) > 8192 or any(ch.isspace() for ch in access_token):
            raise ValueError("DERIV_OAUTH_ACCESS_TOKEN_INVALID")
        if not isinstance(token_type, str) or token_type.lower() != "bearer":
            raise ValueError("DERIV_OAUTH_TOKEN_TYPE_UNSUPPORTED")
        if scopes != ["trade"]:
            raise ValueError("DERIV_OAUTH_SCOPE_MUST_BE_TRADE_ONLY")
        if scope_source not in {"provider_response", "authorization_request"}:
            raise ValueError("DERIV_OAUTH_SCOPE_SOURCE_INVALID")
        issued = self._oauth_timestamp(issued_at_utc)
        expires = self._oauth_timestamp(expires_at_utc)
        if expires <= issued:
            raise ValueError("DERIV_OAUTH_TOKEN_EXPIRY_INVALID")
        key = self._oauth_record_key(principal, app_id)
        row = {
            "principal_uuid": principal, "app_id": app_id,
            "access_token": access_token, "token_type": "Bearer",
            "scopes": ["trade"], "scope_source": scope_source,
            "issued_at_utc": issued.isoformat(), "expires_at_utc": expires.isoformat(),
        }
        with self._locked():
            payload = self._read_oauth_payload_unlocked()
            payload["credentials"][key] = row
            self._write_oauth_payload_unlocked(payload)

    def get_oauth_access_token(
        self, *, principal_uuid: str, app_id: str, now_utc: str | None = None
    ) -> dict[str, object] | None:
        principal = self._oauth_principal_uuid(principal_uuid)
        if not isinstance(app_id, str) or not app_id.strip():
            raise ValueError("DERIV_OAUTH_APP_ID_REQUIRED")
        now = self._oauth_timestamp(now_utc or datetime.now(timezone.utc).isoformat())
        key = self._oauth_record_key(principal, app_id)
        with self._locked():
            payload = self._read_oauth_payload_unlocked()
            row = payload["credentials"].get(key)
            if row is None:
                return None
            if row.get("principal_uuid") != principal or row.get("app_id") != app_id:
                raise RuntimeError("DERIV_OAUTH_CREDENTIAL_BINDING_MISMATCH")
            if row.get("token_type") != "Bearer" or row.get("scopes") != ["trade"]:
                raise RuntimeError("DERIV_OAUTH_CREDENTIAL_POLICY_INVALID")
            if now >= self._oauth_timestamp(row.get("expires_at_utc")):
                payload["credentials"].pop(key, None)
                self._write_oauth_payload_unlocked(payload)
                return None
            return dict(row)

    def delete_oauth_access_token(self, *, principal_uuid: str, app_id: str) -> bool:
        principal = self._oauth_principal_uuid(principal_uuid)
        if not isinstance(app_id, str) or not app_id.strip():
            raise ValueError("DERIV_OAUTH_APP_ID_REQUIRED")
        key = self._oauth_record_key(principal, app_id)
        with self._locked():
            payload = self._read_oauth_payload_unlocked()
            existed = payload["credentials"].pop(key, None) is not None
            if existed:
                self._write_oauth_payload_unlocked(payload)
            return existed


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
