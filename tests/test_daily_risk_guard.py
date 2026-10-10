import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from runtime.core.daily_risk_guard import PersistentDailyRiskGuard
from runtime.core.models import AccountIdentity


class PersistentDailyRiskGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "DAILY_RISK_STATE.json"
        self.account = AccountIdentity("CRTEST", "real", "USD", "real")
        self.now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)

    def test_three_consecutive_losses_trip_and_persist_across_restart(self):
        guard = PersistentDailyRiskGuard(self.path)
        self.assertTrue(guard.check(account=self.account, verified_equity=100, now=self.now).allowed)
        guard.record_settlement(account=self.account, verified_pre_trade_equity=100, net_pnl=-1, now=self.now)
        guard.record_settlement(account=self.account, verified_pre_trade_equity=99, net_pnl=-1, now=self.now)
        result = guard.record_settlement(account=self.account, verified_pre_trade_equity=98, net_pnl=-1, now=self.now)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "CONSECUTIVE_LOSS_LIMIT_REACHED")
        restarted = PersistentDailyRiskGuard(self.path)
        blocked = restarted.check(account=self.account, verified_equity=97, now=self.now + timedelta(days=1))
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.reason, "CONSECUTIVE_LOSS_LIMIT_REACHED")

    def test_daily_drawdown_trips_at_three_percent_of_reference_equity(self):
        guard = PersistentDailyRiskGuard(self.path)
        guard.check(account=self.account, verified_equity=100, now=self.now)
        guard.record_settlement(account=self.account, verified_pre_trade_equity=100, net_pnl=-2, now=self.now)
        result = guard.record_settlement(account=self.account, verified_pre_trade_equity=98, net_pnl=-1, now=self.now)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "DAILY_DRAWDOWN_LIMIT_REACHED")

    def test_profit_resets_consecutive_losses_but_not_daily_pnl(self):
        guard = PersistentDailyRiskGuard(self.path)
        guard.check(account=self.account, verified_equity=100, now=self.now)
        guard.record_settlement(account=self.account, verified_pre_trade_equity=100, net_pnl=-1, now=self.now)
        guard.record_settlement(account=self.account, verified_pre_trade_equity=99, net_pnl=-1, now=self.now)
        self.assertTrue(guard.record_settlement(account=self.account, verified_pre_trade_equity=98, net_pnl=0.5, now=self.now).allowed)
        self.assertTrue(guard.record_settlement(account=self.account, verified_pre_trade_equity=98.5, net_pnl=-1, now=self.now).allowed)

    def test_account_switch_fails_closed(self):
        guard = PersistentDailyRiskGuard(self.path)
        guard.check(account=self.account, verified_equity=100, now=self.now)
        other = AccountIdentity("OTHER", "real", "USD", "real")
        result = guard.check(account=other, verified_equity=100, now=self.now)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "RISK_GUARD_ACCOUNT_IDENTITY_CHANGED")

    def test_corrupt_state_fails_closed(self):
        self.path.write_text("{not-json", encoding="utf-8")
        guard = PersistentDailyRiskGuard(self.path)
        result = guard.check(account=self.account, verified_equity=100, now=self.now)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "DAILY_RISK_STATE_UNREADABLE")

    def test_invalid_equity_and_naive_time_are_rejected(self):
        guard = PersistentDailyRiskGuard(self.path)
        self.assertFalse(guard.check(account=self.account, verified_equity=0, now=self.now).allowed)
        with self.assertRaisesRegex(ValueError, "RISK_GUARD_TIME_MUST_BE_TIMEZONE_AWARE"):
            guard.check(account=self.account, verified_equity=100, now=datetime(2026, 10, 10))


if __name__ == "__main__":
    unittest.main()
