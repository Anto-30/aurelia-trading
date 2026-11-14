from __future__ import annotations

import unittest

from assurance.control_path_soak import run_control_path_soak


class ControlPathSoakTests(unittest.IsolatedAsyncioTestCase):
    async def test_3600_cycle_nonlive_control_path(self):
        result = await run_control_path_soak(3600)
        self.assertTrue(result["passed"], msg=str(result))
        self.assertEqual(result["iterations"], 3600)
        self.assertGreater(result["unknown_outcomes_observed"], 0)
        self.assertEqual(result["unknown_records"], 0)
        self.assertGreater(result["recovered"], 0)
        self.assertGreater(result["blocked"], 0)
        self.assertGreater(result["idempotent_effects_recorded"], 0)
        self.assertGreater(result["stale_authorization_blocked"], 0)
        self.assertGreater(result["kill_switch_blocked"], 0)
        self.assertGreater(result["concurrent_duplicate_checks"], 0)
        self.assertGreater(result["blind_resubmission_checks"], 0)
        self.assertEqual(result["blind_resubmissions"], 0)
        self.assertGreater(result["reconciliation_mismatch_checks"], 0)
        self.assertEqual(
            result["reconciliation_mismatch_failures"],
            result["reconciliation_mismatch_checks"],
        )
        self.assertEqual(result["duplicate_economic_effects"], 0)


if __name__ == "__main__":
    unittest.main()
