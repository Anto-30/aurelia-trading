from pathlib import Path
import ast
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BrokerEvidenceVerifierContractTests(unittest.TestCase):
    def test_broker_evidence_verifier_is_blocked_before_any_secret_or_transport_access(self):
        path = ROOT / "scripts" / "verify_deriv_broker_evidence.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        run = next(
            node for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "run"
        )
        self.assertIsInstance(run.body[0], ast.Return)
        self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", source)
        self.assertNotIn("get_optional_secret", source)
        self.assertNotIn("DerivSessionManager", source)
        self.assertNotIn("DerivAdapter", source)
        self.assertNotIn("DERIV_AUTH_TOKEN", source)
        self.assertNotIn("DERIV_PAT", source)

    def test_blocked_broker_evidence_never_claims_read_only_account_proof(self):
        source = (ROOT / "scripts" / "verify_deriv_broker_evidence.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("REAL_DERIV_BROKER_ACCOUNT_READ_ONLY", source)
        self.assertNotIn("available_balance", source)
        self.assertNotIn("statement(", source)
        self.assertNotIn("portfolio(", source)


if __name__ == "__main__":
    unittest.main()
