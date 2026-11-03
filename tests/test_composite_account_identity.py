from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from runtime.core.models import (
    AURELIAIdentity,
    AccountContext,
    BrokerReturnedUUID,
    CompositeAccountIdentity,
    DerivAccountIdentifier,
    LoginID,
)


UTC = timezone.utc


class CompositeAccountIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(UTC)
        self.aurelia = AURELIAIdentity(str(uuid4()), self.now, "test-version")
        self.deriv = DerivAccountIdentifier("CR123456", "real", False, False)
        self.broker_uuid = BrokerReturnedUUID(None, "not_returned", None)
        self.login_id = LoginID(None, "not_returned")
        self.context = AccountContext("OPTIONS", "REAL", "USD", self.now)

    def test_each_identity_component_validates_independently(self) -> None:
        self.assertTrue(self.aurelia.validate())
        self.assertTrue(self.deriv.validate())
        self.assertTrue(self.broker_uuid.validate())
        self.assertTrue(self.login_id.validate())
        self.assertTrue(self.context.validate())

        self.assertFalse(AURELIAIdentity("not-a-uuid", self.now, "v1").validate())
        self.assertFalse(DerivAccountIdentifier("", "real", False, False).validate())
        self.assertFalse(BrokerReturnedUUID(None, "get_account_status", self.now).validate())
        self.assertFalse(LoginID(None, "authorize").validate())
        self.assertFalse(AccountContext("OPTIONS", "LIVE", "USD", self.now).validate())

    def test_broker_uuid_must_have_source_and_utc_timestamp(self) -> None:
        self.assertTrue(BrokerReturnedUUID("broker-uuid-1", "documented-source", self.now).validate())
        self.assertFalse(BrokerReturnedUUID("broker-uuid-1", "", self.now).validate())
        self.assertFalse(BrokerReturnedUUID("broker-uuid-1", "documented-source", None).validate())

    def test_composite_creation_rejects_each_invalid_component(self) -> None:
        bad_components = (
            (AURELIAIdentity("bad", self.now, "v1"), self.deriv, self.broker_uuid, self.login_id, self.context),
            (self.aurelia, DerivAccountIdentifier("", "real", False, False), self.broker_uuid, self.login_id, self.context),
            (self.aurelia, self.deriv, BrokerReturnedUUID(None, "unknown", None), self.login_id, self.context),
            (self.aurelia, self.deriv, self.broker_uuid, LoginID(None, "unknown"), self.context),
            (self.aurelia, self.deriv, self.broker_uuid, self.login_id, AccountContext("OPTIONS", "LIVE", "USD", self.now)),
        )
        for components in bad_components:
            with self.subTest(component=components):
                with self.assertRaises(ValueError):
                    CompositeAccountIdentity.create(*components)

    def test_composite_identity_checksum_is_stable_and_valid(self) -> None:
        identity = CompositeAccountIdentity.create(
            self.aurelia, self.deriv, self.broker_uuid, self.login_id, self.context
        )
        self.assertTrue(identity.validate_integrity())
        self.assertEqual(len(identity.identity_checksum), 64)

    def test_integrity_check_detects_nested_identity_tampering(self) -> None:
        identity = CompositeAccountIdentity.create(
            self.aurelia, self.deriv, self.broker_uuid, self.login_id, self.context
        )
        object.__setattr__(identity.deriv_account, "deriv_loginid", "CR999999")
        self.assertFalse(identity.validate_integrity())

    def test_identity_does_not_store_email_or_email_hash(self) -> None:
        identity = CompositeAccountIdentity.create(
            self.aurelia, self.deriv, self.broker_uuid, self.login_id, self.context
        )
        self.assertFalse(hasattr(identity.login_id, "email_hash"))
        self.assertFalse(hasattr(identity.login_id, "email"))


if __name__ == "__main__":
    unittest.main()
