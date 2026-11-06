from __future__ import annotations

import json
import unittest

from runtime.security.deriv_auth_gate import ACCOUNT_CREDENTIAL_ENV_NAMES
from scripts.deriv_auth_prerequisites import build_evidence


class NoSecretValueReads(dict):
    def get(self, key, default=None):
        if key in ACCOUNT_CREDENTIAL_ENV_NAMES:
            raise AssertionError("credential values must never be read")
        return super().get(key, default)


class DerivAuthPrerequisiteEvidenceTests(unittest.TestCase):
    def test_public_research_is_configured_without_account_credential_keys(self):
        evidence = build_evidence({})
        self.assertEqual(evidence["schema_version"], "3")
        self.assertEqual(evidence["public_research"]["status"], "CONFIGURED")
        self.assertEqual(evidence["public_research"]["auth_mode"], "none")
        self.assertFalse(evidence["public_research"]["account_credentials_mapped"])
        self.assertFalse(evidence["public_research"]["account_credentials_present_in_process"])
        self.assertFalse(evidence["account_evidence_ready"])
        self.assertTrue(evidence["account_evidence"]["credentials_isolated_in_process"])
        self.assertEqual(
            evidence["account_evidence"]["reason"],
            "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
        )
        self.assertFalse(evidence["secret_values_exposed"])

    def test_credential_presence_is_detected_without_reading_any_value(self):
        evidence = build_evidence(NoSecretValueReads({
            "ACCOUNT_DERIV_AUTH_MODE": "none",
            "DERIV_OAUTH_ACCESS_TOKEN": "",
            "DERIV_PAT": "",
        }))
        self.assertEqual(evidence["public_research"]["status"], "BLOCKED")
        self.assertTrue(evidence["public_research"]["account_credentials_present_in_process"])
        self.assertFalse(evidence["account_evidence"]["credentials_isolated_in_process"])
        self.assertEqual(
            evidence["account_evidence"]["reason"],
            "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
        )

    def test_empty_credential_environment_key_still_blocks_public_research(self):
        evidence = build_evidence({"DERIV_PAT": ""})
        self.assertEqual(evidence["public_research"]["status"], "BLOCKED")
        self.assertTrue(evidence["public_research"]["account_credentials_present_in_process"])
        self.assertFalse(evidence["account_evidence"]["credentials_isolated_in_process"])

    def test_invalid_auth_mode_does_not_change_the_scope_blocker(self):
        evidence = build_evidence({"ACCOUNT_DERIV_AUTH_MODE": "oauth"})
        self.assertEqual(evidence["account_evidence"]["auth_mode"], "invalid")
        self.assertEqual(
            evidence["account_evidence"]["reason"],
            "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
        )
        self.assertFalse(evidence["account_evidence_ready"])


if __name__ == "__main__":
    unittest.main()
