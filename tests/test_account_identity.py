from __future__ import annotations

from dataclasses import replace
import json
import unittest
from datetime import datetime, timezone

from runtime.core.account_identity import (
    AURELIAIdentity, AccountContext, BrokerReturnedUUID,
    CompositeAccountIdentity, DerivAccountIdentifier, EnvironmentType,
    LoginID, OPTIONS_ACCOUNTS_ENDPOINT, ProductType,
)

NOW = datetime.now(timezone.utc).isoformat()
UUID_AURELIA = "0e8b5f21-34d7-4e8c-9c1b-6cc2fe4c7c10"
UUID_BROKER = "f2ac691f-68d7-b467-6308-72d5ecaf9030"
HASH_A = "a" * 64
HASH_B = "b" * 64
WS_REAL = "wss://api.derivws.com/trading/v1/options/ws/real"


def valid_identity():
    return CompositeAccountIdentity.create(
        aurelia=AURELIAIdentity(UUID_AURELIA),
        deriv_account=DerivAccountIdentifier(
            "ROT92026649", "real", "active", OPTIONS_ACCOUNTS_ENDPOINT, HASH_A, NOW
        ),
        broker_uuid=BrokerReturnedUUID(UUID_BROKER, "balance", HASH_B, NOW),
        login_id=LoginID("ROT92026649", "balance", NOW),
        context=AccountContext(
            ProductType.OPTIONS, EnvironmentType.REAL, "USD", "USD", "USD",
            "active", OPTIONS_ACCOUNTS_ENDPOINT, WS_REAL, NOW,
        ),
    )


class CompositeAccountIdentityTests(unittest.TestCase):
    def test_identifiers_remain_distinct_and_checksum_validates(self):
        identity = valid_identity()
        self.assertTrue(identity.validate_integrity())
        self.assertNotEqual(identity.aurelia.internal_uuid, identity.broker_uuid.value)
        self.assertEqual(identity.deriv_account.account_id, "ROT92026649")
        self.assertEqual(identity.login_id.value, "ROT92026649")
        self.assertNotEqual(identity.deriv_account.source_endpoint, identity.login_id.source_method)

    def test_account_id_loginid_mismatch_is_rejected(self):
        identity = valid_identity()
        with self.assertRaisesRegex(ValueError, "DERIV_ACCOUNT_ID_LOGINID_MISMATCH"):
            CompositeAccountIdentity.create(
                aurelia=identity.aurelia,
                deriv_account=identity.deriv_account,
                broker_uuid=identity.broker_uuid,
                login_id=replace(identity.login_id, value="ROT00000000"),
                context=identity.context,
            )

    def test_broker_uuid_format_is_validated(self):
        identity = valid_identity()
        with self.assertRaisesRegex(ValueError, "ACCOUNT_IDENTITY_COMPONENT_INVALID"):
            CompositeAccountIdentity.create(
                aurelia=identity.aurelia,
                deriv_account=identity.deriv_account,
                broker_uuid=replace(identity.broker_uuid, value="not-a-uuid"),
                login_id=identity.login_id,
                context=identity.context,
            )

    def test_nonactive_account_status_is_rejected(self):
        identity = valid_identity()
        disabled = replace(identity.deriv_account, status="disabled")
        with self.assertRaisesRegex(ValueError, "ACCOUNT_IDENTITY_COMPONENT_INVALID"):
            CompositeAccountIdentity.create(
                aurelia=identity.aurelia, deriv_account=disabled,
                broker_uuid=identity.broker_uuid, login_id=identity.login_id,
                context=replace(identity.context, account_status="disabled"),
            )

    def test_environment_mismatch_is_rejected(self):
        identity = valid_identity()
        with self.assertRaisesRegex(ValueError, "DERIV_ACCOUNT_ENVIRONMENT_MISMATCH"):
            CompositeAccountIdentity.create(
                aurelia=identity.aurelia,
                deriv_account=identity.deriv_account,
                broker_uuid=identity.broker_uuid,
                login_id=identity.login_id,
                context=replace(
                    identity.context,
                    environment=EnvironmentType.DEMO,
                    environment_source_endpoint="wss://api.derivws.com/trading/v1/options/ws/demo",
                ),
            )

    def test_currency_mismatch_is_rejected(self):
        identity = valid_identity()
        with self.assertRaisesRegex(ValueError, "ACCOUNT_IDENTITY_COMPONENT_INVALID"):
            CompositeAccountIdentity.create(
                aurelia=identity.aurelia, deriv_account=identity.deriv_account,
                broker_uuid=identity.broker_uuid, login_id=identity.login_id,
                context=replace(identity.context, balance_currency="EUR"),
            )

    def test_internal_uuid_must_not_equal_broker_uuid(self):
        identity = valid_identity()
        with self.assertRaisesRegex(ValueError, "AURELIA_AND_BROKER_UUID_COLLISION"):
            CompositeAccountIdentity.create(
                aurelia=replace(identity.aurelia, internal_uuid=UUID_BROKER),
                deriv_account=identity.deriv_account,
                broker_uuid=identity.broker_uuid,
                login_id=identity.login_id,
                context=identity.context,
            )

    def test_internal_uuid_is_validated_independently(self):
        identity = valid_identity()
        with self.assertRaisesRegex(ValueError, "ACCOUNT_IDENTITY_COMPONENT_INVALID"):
            CompositeAccountIdentity.create(
                aurelia=replace(identity.aurelia, internal_uuid="options-account-001"),
                deriv_account=identity.deriv_account,
                broker_uuid=identity.broker_uuid,
                login_id=identity.login_id,
                context=identity.context,
            )

    def test_checksum_detects_source_hash_drift(self):
        identity = valid_identity()
        tampered = replace(
            identity,
            deriv_account=replace(identity.deriv_account, source_response_sha256=HASH_B),
        )
        self.assertFalse(tampered.validate_integrity())

    def test_serialization_excludes_unnecessary_pii(self):
        encoded = json.dumps(valid_identity().to_dict()).lower()
        self.assertNotIn("email", encoded)
        self.assertNotIn("phone", encoded)
        self.assertNotIn("address", encoded)


if __name__ == "__main__":
    unittest.main()
