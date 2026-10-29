from __future__ import annotations

import unittest

from research.labs.setup_manager import SetupManager


class SetupManagerTests(unittest.TestCase):
    def test_setup_expires_after_configured_window(self):
        manager = SetupManager(default_expiry_bars=3)
        self.assertTrue(manager.register("A", "S1", 10, payload={"side": "LONG"}))
        self.assertEqual(manager.advance("S1", 13), ())
        self.assertIsNotNone(manager.get_active("A", "S1"))
        expired = manager.advance("S1", 14)
        self.assertEqual([item.setup_id for item in expired], ["A"])
        self.assertIsNone(manager.get_active("A", "S1"))

    def test_duplicate_id_rejected_even_after_expiry(self):
        manager = SetupManager(default_expiry_bars=1)
        self.assertTrue(manager.register("A", "S1", 0))
        manager.advance("S1", 2)
        self.assertFalse(manager.register("A", "S1", 2))
        self.assertEqual(manager.active_setups(), ())

    def test_same_id_allowed_in_a_different_session(self):
        manager = SetupManager()
        self.assertTrue(manager.register("A", "S1", 0))
        self.assertTrue(manager.register("A", "S2", 0))
        self.assertEqual(len(manager.active_setups()), 2)

    def test_trigger_removes_setup_and_duplicate_stays_blocked(self):
        manager = SetupManager()
        manager.register("A", "S1", 0)
        setup = manager.mark_triggered("A", "S1")
        self.assertEqual(setup.setup_id, "A")
        self.assertIsNone(manager.get_active("A", "S1"))
        self.assertFalse(manager.register("A", "S1", 1))

    def test_sessions_expire_independently(self):
        manager = SetupManager(default_expiry_bars=1)
        manager.register("A", "S1", 0)
        manager.register("B", "S2", 0)
        expired = manager.advance("S1", 2)
        self.assertEqual([item.setup_id for item in expired], ["A"])
        self.assertIsNotNone(manager.get_active("B", "S2"))

    def test_bar_index_cannot_move_backwards(self):
        manager = SetupManager()
        manager.register("A", "S1", 5)
        with self.assertRaisesRegex(ValueError, "SETUP_BAR_INDEX_OUT_OF_ORDER"):
            manager.advance("S1", 4)

    def test_invalid_expiry_and_identity_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "SETUP_EXPIRY_BARS_INVALID"):
            SetupManager(default_expiry_bars=0)
        manager = SetupManager()
        with self.assertRaisesRegex(ValueError, "SETUP_ID_REQUIRED"):
            manager.register("", "S1", 0)
        with self.assertRaisesRegex(ValueError, "SETUP_EXPIRY_BARS_INVALID"):
            manager.register("A", "S1", 0, expires_after_bars=-1)


if __name__ == "__main__":
    unittest.main()
