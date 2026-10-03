import unittest
from runtime.core.concurrency import SingleExecutionSlot
from runtime.core.limits import ExecutionLimits
from runtime.security.config import credentials_allowed
from runtime.security.secrets import is_clean, scan_text


class SecurityConcurrencyTests(unittest.TestCase):
    def test_secret_scanner(self):
        self.assertTrue(is_clean("normal source text"))
        self.assertTrue(scan_text("Bearer SECRETSECRETSECRET"))

    def test_environment_policy(self):
        self.assertFalse(credentials_allowed("dev", "real"))
        self.assertTrue(credentials_allowed("production", "real"))
        self.assertFalse(credentials_allowed("production", "demo"))

    def test_limits(self):
        limits = ExecutionLimits()
        self.assertTrue(limits.validate(8.0, 8.0)[0])
        self.assertFalse(limits.validate(8.1, 8.0)[0])
        self.assertTrue(limits.validate(1.49, 8.0)[0])
        self.assertFalse(limits.validate(1.00, 0.99)[0])

    def test_single_slot(self):
        slot = SingleExecutionSlot()
        with slot.acquire():
            with self.assertRaises(RuntimeError):
                with slot.acquire():
                    pass


if __name__ == "__main__":
    unittest.main()
