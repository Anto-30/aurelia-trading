import io
import unittest
from contextlib import redirect_stdout

from assurance.certification_evidence import _provenance_valid
from scripts.verify_deriv_session import run
from runtime.adapters.session_manager import derive_ws_environment, redact_ws_url


class DerivAuthEvidenceContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_evidence_is_blocked_without_documented_read_only_scope(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = run()
        self.assertEqual(result, 3)
        self.assertIn(
            "DERIV_AUTH_SESSION_REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            output.getvalue(),
        )
        self.assertIn("DERIV_ORDERS_SUBMITTED=0", output.getvalue())
        self.assertIn("DERIV_CAPITAL_AUTHORITY_GRANTED=false", output.getvalue())

    def test_ci_environment_matches_certification_schema(self):
        source_commit = "a" * 40
        record = {
            "environment": "ci",
            "source_hash": source_commit,
            "artifact_hash": "b" * 64,
            "config_hash": "c" * 64,
            "data_hash": "d" * 64,
            "provenance": {
                "origin": "ci",
                "issuer": "test",
                "source_commit": source_commit,
                "generated_at_utc": "2026-10-03T10:00:00Z",
            },
        }
        self.assertTrue(_provenance_valid(record)[0])
        record["environment"] = "ci-real"
        self.assertFalse(_provenance_valid(record)[0])

    def test_otp_is_never_present_in_safe_url(self):
        raw = "wss://api.derivws.com/trading/v1/options/ws/real?otp=TOP-SECRET"
        safe = redact_ws_url(raw)
        self.assertNotIn("TOP-SECRET", safe)
        self.assertEqual(derive_ws_environment(raw), "real")


if __name__ == "__main__":
    unittest.main()
