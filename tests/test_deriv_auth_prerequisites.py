import json
import unittest

from scripts.deriv_auth_prerequisites import build_evidence


class DerivAuthPrerequisiteEvidenceTests(unittest.TestCase):
    def test_valid_pat_configuration_persists_only_safe_values(self):
        evidence = build_evidence({
            "DERIV_AUTH_TOKEN": "test-token-do-not-persist",
            "DERIV_APP_ID": "12345",
            "DERIV_EXPECTED_LOGINID": "CR123456",
            "DERIV_AUTH_MODE": "pat",
            "DERIV_EXPECTED_CURRENCY": "USD",
        })
        self.assertTrue(evidence["configured"])
        self.assertEqual(evidence["auth_mode"], "pat")
        self.assertEqual(evidence["expected_currency"], "USD")
        encoded = json.dumps(evidence)
        for raw in ("test-token-do-not-persist", "12345", "CR123456"):
            self.assertNotIn(raw, encoded)
        self.assertFalse(evidence["secret_values_exposed"])

    def test_invalid_auth_mode_is_redacted(self):
        marker = "private-auth-mode-marker"
        evidence = build_evidence({
            "DERIV_AUTH_TOKEN": "dummy-token",
            "DERIV_EXPECTED_LOGINID": "dummy-account",
            "DERIV_AUTH_MODE": marker,
            "DERIV_EXPECTED_CURRENCY": "USD",
        })
        self.assertEqual(evidence["auth_mode"], "invalid")
        self.assertFalse(evidence["configured"])
        self.assertNotIn(marker, json.dumps(evidence))

    def test_invalid_currency_is_redacted(self):
        marker = "private-currency-marker"
        evidence = build_evidence({
            "DERIV_AUTH_MODE": "oauth",
            "DERIV_EXPECTED_CURRENCY": marker,
        })
        self.assertEqual(evidence["expected_currency"], "invalid")
        self.assertFalse(evidence["configured"])
        self.assertNotIn(marker, json.dumps(evidence))

    def test_missing_configuration_fails_closed_without_raw_values(self):
        evidence = build_evidence({})
        self.assertFalse(evidence["configured"])
        self.assertEqual(evidence["auth_mode"], "pat")
        self.assertEqual(evidence["expected_currency"], "missing")
        self.assertEqual(
            evidence["requirements"],
            {
                "token_present": False,
                "expected_loginid_present": False,
                "auth_mode_valid": True,
                "app_id_present_when_pat": False,
                "expected_currency_present": False,
            },
        )

    def test_oauth_does_not_require_app_id(self):
        evidence = build_evidence({
            "DERIV_AUTH_TOKEN": "dummy-token",
            "DERIV_EXPECTED_LOGINID": "dummy-account",
            "DERIV_AUTH_MODE": "oauth",
            "DERIV_EXPECTED_CURRENCY": "usd",
        })
        self.assertTrue(evidence["configured"])
        self.assertEqual(evidence["expected_currency"], "USD")
        self.assertTrue(evidence["requirements"]["app_id_present_when_pat"])


if __name__ == "__main__":
    unittest.main()
