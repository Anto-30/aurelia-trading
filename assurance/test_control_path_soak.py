from __future__ import annotations

import unittest

from assurance.control_path_soak import run_control_path_soak


class ControlPathSoakTests(unittest.IsolatedAsyncioTestCase):
    async def test_3600_cycle_nonlive_control_path(self):
        result = await run_control_path_soak(3600)
        self.assertTrue(result["passed"], msg=str(result))
        self.assertEqual(result["iterations"], 3600)
        self.assertGreater(result["unknown_records"], 0)
        self.assertGreater(result["recovered"], 0)
        self.assertGreater(result["blocked"], 0)
        self.assertGreater(result["idempotent_effects_recorded"], 0)


if __name__ == "__main__":
    unittest.main()
