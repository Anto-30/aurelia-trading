import json
import unittest

from scripts.deriv_auth_prerequisites import build_evidence


class DerivAuthPrerequisiteEvidenceTests(unittest.TestCase):
    def test_public_research_is_ready_without_account_credentials(self):
        evidence = build_evidence({})
        self.assertEqual(evidence["schema_version"], "2")
        self.assertEqual(evidence["public_research"]["status"], "CONFIGURED")
        self.assertEqual(evidence["public_research"]["auth_mode"], "none")
        self.assertFalse(evidence["public_research"]["account_credentials_mapped"])
        self.assertFalse(evidence["account_evidence_ready"])
        self.assertTrue(evidence["account_evidence"]["credentials_isolated_in_process"])
        self.assertEqual(
            evidence["account_evidence"]["reason"],
            "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
        )
        self.assertFalse(evidence["secret_values_exposed"])
        self.assertFalse(evidence["public_research"]["account_credentials_present_in_process"])

    def test_identical_oauth_and_pat_values_are_reported_as_equal_without_exposure(self):
        evidence = build_evidence({
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "SAME_SECRET_SENTINEL",
            "DERIV_PAT": "SAME_SECRET_SENTINEL",
        })
        account = evidence["account_evidence"]
        self.assertTrue(account["oauth_pat_values_equal"])
        self.assertFalse(account["credentials_isolated_in_process"])
        self.assertEqual(account["reason"], "OAUTH_TOKEN_EQUALS_PAT")
        self.assertEqual(evidence["public_research"]["status"], "BLOCKED")
        self.assertTrue(evidence["public_research"]["account_credentials_present_in_process"])
        encoded = json.dumps(evidence)
        self.assertNotIn("SAME_SECRET_SENTINEL", encoded)

    def test_pat_is_rejected_even_when_its_value_differs_from_oauth(self):
        evidence = build_evidence({
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SENTINEL",
            "DERIV_PAT": "PAT_SENTINEL",
        })
        account = evidence["account_evidence"]
        self.assertFalse(account["credentials_isolated_in_process"])
        self.assertEqual(account["reason"], "ACCOUNT_PLANE_PAT_PRESENT")
        self.assertNotIn("OAUTH_SENTINEL", json.dumps(evidence))
        self.assertNotIn("PAT_SENTINEL", json.dumps(evidence))

    def test_generic_token_fallback_is_rejected(self):
        evidence = build_evidence({
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_AUTH_TOKEN": "AMBIGUOUS_SENTINEL",
        })
        self.assertEqual(
            evidence["account_evidence"]["reason"],
            "GENERIC_TOKEN_FALLBACK_BLOCKED",
        )
        self.assertNotIn("AMBIGUOUS_SENTINEL", json.dumps(evidence))

    def test_refresh_token_is_rejected(self):
        evidence = build_evidence({
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SENTINEL",
            "DERIV_OAUTH_REFRESH_TOKEN": "REFRESH_SENTINEL",
        })
        self.assertEqual(
            evidence["account_evidence"]["reason"],
            "DERIV_OAUTH_REFRESH_TOKEN_UNSUPPORTED",
        )
        self.assertFalse(evidence["account_evidence"]["credentials_isolated_in_process"])

    def test_oauth_presence_does_not_claim_read_only_account_authority(self):
        evidence = build_evidence({
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SENTINEL",
        })
        account = evidence["account_evidence"]
        self.assertTrue(account["credentials_isolated_in_process"])
        self.assertFalse(account["read_only_scope_supported"])
        self.assertFalse(evidence["account_evidence_ready"])
        self.assertEqual(account["reason"], "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")
        self.assertNotIn("OAUTH_SENTINEL", json.dumps(evidence))


if __name__ == "__main__":
    unittest.main()
