from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BrokerEvidenceVerifierContractTests(unittest.TestCase):
    def test_verifier_fails_closed_before_any_account_api_call(self):
        source = (ROOT / "scripts" / "verify_deriv_broker_evidence.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        }
        self.assertNotIn("statement", called)
        self.assertNotIn("portfolio", called)
        self.assertNotIn("get_balance", called)
        self.assertNotIn("submit_authorized_order", called)
        self.assertIn("DerivAuthenticationGate(plane=\"account\")", source)

    def test_verifier_has_no_pat_or_generic_token_fallback(self):
        source = (ROOT / "scripts" / "verify_deriv_broker_evidence.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("DERIV_AUTH_TOKEN", source)
        self.assertNotIn("DERIV_PAT", source)

    def test_verifier_preserves_zero_capital_authority_status(self):
        source = (ROOT / "scripts" / "verify_deriv_broker_evidence.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('print("CAPITAL_AUTHORITY=false")', source)
        self.assertIn('print("ORDERS_SUBMITTED=0")', source)


if __name__ == "__main__":
    unittest.main()
