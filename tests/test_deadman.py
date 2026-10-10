from __future__ import annotations

import unittest

from runtime.ops.deadman import DeadManSwitch


class DeadManSwitchTests(unittest.TestCase):
    def test_successful_heartbeat_refreshes_deadline(self):
        clock = [0.0]
        switch = DeadManSwitch(60.0, clock=lambda: clock[0])
        clock[0] = 55.0
        self.assertTrue(switch.record_success("RUNTIME_HEARTBEAT"))
        clock[0] = 114.0
        self.assertFalse(switch.expired())
        clock[0] = 115.0
        self.assertTrue(switch.expired())
        self.assertTrue(switch.trip_if_expired())
        self.assertTrue(switch.tripped)

    def test_execution_event_is_accepted_before_trip(self):
        clock = [10.0]
        switch = DeadManSwitch(30.0, clock=lambda: clock[0])
        clock[0] = 35.0
        self.assertTrue(switch.record_success("TRADE_EXECUTION"))
        self.assertEqual(switch.last_event, "TRADE_EXECUTION")
        clock[0] = 64.0
        self.assertFalse(switch.expired())

    def test_trip_is_sticky_and_late_heartbeat_cannot_clear_it(self):
        clock = [0.0]
        switch = DeadManSwitch(5.0, clock=lambda: clock[0])
        clock[0] = 5.0
        self.assertTrue(switch.trip_if_expired())
        self.assertFalse(switch.trip_if_expired())
        clock[0] = 6.0
        self.assertFalse(switch.record_success("RUNTIME_HEARTBEAT"))
        self.assertTrue(switch.expired())
        self.assertTrue(switch.tripped)

    def test_invalid_timeout_and_success_event_are_rejected(self):
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    DeadManSwitch(timeout)
        switch = DeadManSwitch(10.0)
        with self.assertRaisesRegex(ValueError, "DEADMAN_EVENT_TYPE_NOT_A_SUCCESS"):
            switch.record_success("WATCHDOG_PROTECT")


if __name__ == "__main__":
    unittest.main()
