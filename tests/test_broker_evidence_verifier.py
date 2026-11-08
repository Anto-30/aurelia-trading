from pathlib import Path
import ast
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BrokerEvidenceVerifierContractTests(unittest.TestCase):
    def test_broker_evidence_verifier_is_held_until_no_order_audit(self):
        source = (ROOT / "scripts" / "verify_deriv_broker_evidence.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        run = next(
            node for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "run"
        )
        first_statement = run.body[0]
        self.assertIsInstance(first_statement, ast.Return)
        self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", source)

    def test_held_verifier_returns_before_secret_reads(self):
        source = (ROOT / "scripts" / "verify_deriv_broker_evidence.py").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            source.index('return fail("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")'),
            source.index('get_optional_secret("DERIV_AUTH_TOKEN")'),
        )
        self.assertNotIn("submit_authorized_order", source)

    def test_verifier_declares_no_capital_authority(self):
        source = (ROOT / "scripts" / "verify_deriv_broker_evidence.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('enriched["capital_authority_granted"] = False', source)
        self.assertIn('enriched["orders_submitted"] = 0', source)
        self.assertIn('enriched["verification_scope"] = "REAL_DERIV_BROKER_ACCOUNT_READ_ONLY"', source)


if __name__ == "__main__":
    unittest.main()
