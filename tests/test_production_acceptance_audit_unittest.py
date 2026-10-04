import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProductionAcceptanceAuditTests(unittest.TestCase):
    def test_production_acceptance_audit_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/production_acceptance_audit.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("AURELIA_PRODUCTION_ACCEPTANCE=AUDIT_PASS", result.stdout)
        self.assertIn("CAPITAL_MOVEMENT_PERMITTED=false", result.stdout)
        self.assertIn("LIVE_EXECUTION=BLOCKED", result.stdout)


if __name__ == "__main__":
    unittest.main()
