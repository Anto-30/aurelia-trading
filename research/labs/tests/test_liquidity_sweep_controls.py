import unittest
from datetime import datetime, timedelta, timezone

from research.labs.liquidity_sweep_controls import (
    LiveExecutionLock, Setup, SetupManager, validate_live_timestamp,
)

UTC = timezone.utc
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


class SetupControlsTests(unittest.TestCase):
    def test_long_and_short_setups_are_accepted(self):
        manager = SetupManager()
        self.assertTrue(manager.add_setup(Setup(NOW, "LONG", 100, 95, 110), NOW))
        self.assertTrue(manager.add_setup(Setup(NOW, "SHORT", 100, 105, 90), NOW))
        self.assertEqual(set(manager.active_setups), {"LONG", "SHORT"})

    def test_same_direction_duplicate_is_rejected_until_expiry(self):
        manager = SetupManager()
        self.assertTrue(manager.add_setup(Setup(NOW, "LONG", 100, 95, 110), NOW))
        self.assertFalse(manager.add_setup(
            Setup(NOW + timedelta(minutes=1), "LONG", 101, 96, 111),
            NOW + timedelta(minutes=1),
        ))
        self.assertEqual(manager.active_setups["LONG"].entry_price, 100)

    def test_expired_setup_is_removed_and_new_one_can_be_added(self):
        manager = SetupManager(expiry_minutes=10)
        manager.add_setup(Setup(NOW, "LONG", 100, 95, 110), NOW)
        later = NOW + timedelta(minutes=11)
        self.assertEqual(manager.check_expiry_and_edge_cases(later, None, False), ["LONG"])
        self.assertTrue(manager.add_setup(Setup(later, "LONG", 100, 95, 110), later))

    def test_gap_crossing_stop_invalidates_but_gap_inside_range_does_not(self):
        manager = SetupManager()
        manager.add_setup(Setup(NOW, "LONG", 100, 95, 110), NOW)
        self.assertEqual(
            manager.check_expiry_and_edge_cases(NOW + timedelta(minutes=1), 98, True), []
        )
        self.assertEqual(
            manager.check_expiry_and_edge_cases(NOW + timedelta(minutes=2), 90, True), ["LONG"]
        )

    def test_invalid_direction_prices_and_naive_timestamps_rejected(self):
        manager = SetupManager()
        with self.assertRaisesRegex(ValueError, "direction"):
            manager.add_setup(Setup(NOW, "BUY", 100, 95, 110), NOW)
        with self.assertRaisesRegex(ValueError, "ordering"):
            manager.add_setup(Setup(NOW, "LONG", 100, 105, 110), NOW)
        naive = datetime(2026, 10, 27, 12, 0)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            manager.add_setup(Setup(naive, "LONG", 100, 95, 110), NOW)

    def test_future_setup_is_rejected(self):
        manager = SetupManager()
        with self.assertRaisesRegex(ValueError, "Lookahead"):
            manager.add_setup(Setup(NOW + timedelta(seconds=1), "LONG", 100, 95, 110), NOW)

    def test_live_lock_cannot_be_unlocked_by_environment_flag(self):
        lock = LiveExecutionLock()
        self.assertFalse(lock.is_unlocked)
        with self.assertRaisesRegex(PermissionError, "no capital authority"):
            lock.can_execute()

    def test_timestamp_guard(self):
        self.assertTrue(validate_live_timestamp(NOW, NOW))
        with self.assertRaisesRegex(ValueError, "Lookahead"):
            validate_live_timestamp(NOW + timedelta(seconds=1), NOW)


if __name__ == "__main__":
    unittest.main()
