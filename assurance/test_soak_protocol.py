import unittest

from assurance.soak_protocol import SoakResult, smoke_soak_is_not_full_soak, validate_full_soak

class SoakProtocolTest(unittest.TestCase):
    def test_full_soak_acceptance_contract(self):
        good = SoakResult(3600, 0, 0, 0, 0, 0, 0, 0)
        self.assertTrue(validate_full_soak(good))

    def test_any_failure_blocks(self):
        bad = SoakResult(3600, 1, 0, 0, 0, 0, 0, 0)
        self.assertFalse(validate_full_soak(bad))

    def test_short_run_is_not_evidence(self):
        smoke = SoakResult(30, 0, 0, 0, 0, 0, 0, 0)
        self.assertTrue(smoke_soak_is_not_full_soak(smoke))
        self.assertFalse(validate_full_soak(smoke))

if __name__ == "__main__":
    unittest.main()
