from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
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
        self.broker_uuid = BrokerReturnedUUID(
            "f2ac691f-68d7-b467-6308-72d5ecaf9030", "balance", self.now
        )
        self.login_id = LoginID("CR123456", "balance")
        self.context = AccountContext("OPTIONS", "REAL", "USD", self.now)

    def test_each_identity_component_validates_independently(self) -> None:
        self.assertTrue(self.aurelia.validate())
        self.assertTrue(self.deriv.validate())
        self.assertTrue(self.broker_uuid.validate())
        self.assertTrue(self.login_id.validate())
        self.assertTrue(self.context.validate())

        self.assertFalse(AURELIAIdentity("not-a-uuid", self.now, "v1").validate())
        self.assertFalse(DerivAccountIdentifier("", "real", False, False).validate())
        self.assertFalse(BrokerReturnedUUID("not-a-uuid", "balance", self.now).validate())
        self.assertFalse(BrokerReturnedUUID(
            "f2ac691f-68d7-b467-6308-72d5ecaf9030", "", self.now
        ).validate())
        self.assertFalse(LoginID("", "balance").validate())
        self.assertFalse(AccountContext("OPTIONS", "LIVE", "USD", self.now).validate())

    def test_broker_uuid_must_have_source_and_utc_timestamp(self) -> None:
        broker_uuid = "f2ac691f-68d7-b467-6308-72d5ecaf9030"
        self.assertTrue(BrokerReturnedUUID(broker_uuid, "balance", self.now).validate())
        self.assertFalse(BrokerReturnedUUID("not-a-uuid", "balance", self.now).validate())
        self.assertFalse(BrokerReturnedUUID(broker_uuid, "", self.now).validate())

    def test_composite_creation_rejects_each_invalid_component(self) -> None:
        bad_components = (
            (AURELIAIdentity("bad", self.now, "v1"), self.deriv, self.broker_uuid, self.login_id, self.context),
            (self.aurelia, DerivAccountIdentifier("", "real", False, False), self.broker_uuid, self.login_id, self.context),
            (self.aurelia, self.deriv, BrokerReturnedUUID("not-a-uuid", "balance", self.now), self.login_id, self.context),
            (self.aurelia, self.deriv, self.broker_uuid, LoginID("", "balance"), self.context),
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

    def test_integrity_check_detects_verified_timestamp_tampering(self) -> None:
        identity = CompositeAccountIdentity.create(
            self.aurelia, self.deriv, self.broker_uuid, self.login_id, self.context
        )
        tampered = __import__("dataclasses").replace(
            identity, verified_at=identity.verified_at + timedelta(seconds=1)
        )
        self.assertFalse(tampered.validate_integrity())

    def test_identity_does_not_store_email_or_email_hash(self) -> None:
        identity = CompositeAccountIdentity.create(
            self.aurelia, self.deriv, self.broker_uuid, self.login_id, self.context
        )
        self.assertFalse(hasattr(identity.login_id, "email_hash"))
        self.assertFalse(hasattr(identity.login_id, "email"))


if __name__ == "__main__":
    unittest.main()
