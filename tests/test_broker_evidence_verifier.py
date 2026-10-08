from pathlib import Path
import ast
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BrokerEvidenceVerifierContractTests(unittest.TestCase):
    def test_verifier_is_read_only_and_account_scoped(self):
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

        self.assertIn("statement", called)
        self.assertIn("portfolio", called)
        self.assertIn("get_balance", called)
        self.assertNotIn("submit_authorized_order", called)
        self.assertNotIn("buy", called)

    def test_verifier_declares_no_capital_authority(self):
        source = (ROOT / "scripts" / "verify_deriv_broker_evidence.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('capital_authority_granted\": False', source)
        self.assertIn('"orders_submitted": 0', source)
        self.assertIn(
            '"verification_scope": "REAL_DERIV_BROKER_ACCOUNT_READ_ONLY"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
