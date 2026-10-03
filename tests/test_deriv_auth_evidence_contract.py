import unittest

from scripts.verify_deriv_session import OUTPUT
from runtime.adapters.session_manager import derive_ws_environment, redact_ws_url


class DerivAuthEvidenceContractTests(unittest.TestCase):
    def test_output_path_is_not_secret_dependent(self):
        self.assertTrue(str(OUTPUT).endswith("deriv_authenticated_session.json"))

    def test_otp_is_never_present_in_safe_url(self):
        raw = "wss://api.derivws.com/trading/v1/options/ws/real?otp=TOP-SECRET"
        safe = redact_ws_url(raw)
        self.assertNotIn("TOP-SECRET", safe)
        self.assertEqual(derive_ws_environment(raw), "real")


if __name__ == "__main__":
    unittest.main()
