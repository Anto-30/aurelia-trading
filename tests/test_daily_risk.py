from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.core.daily_risk import PersistentDailyRiskGuard, derive_utc_day_start_balance


UTC = timezone.utc
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def rows_for_day():
    return [
        {"transaction_time": 1000, "transaction_id": "T1", "amount": -1.0,
         "balance_after": 99.0, "currency": "USD"},
        {"transaction_time": 1001, "transaction_id": "T2", "amount": 2.0,
         "balance_after": 101.0, "currency": "USD"},
    ]


class DailyRiskTests(unittest.TestCase):
    def test_statement_reconstructs_start_and_checks_latest_balance(self):
        reference, source = derive_utc_day_start_balance(
            current_balance=101.0, transactions=rows_for_day(), day_start_epoch=0,
            day_end_epoch=2000, currency="USD",
        )
        self.assertEqual(reference, 100.0)
        self.assertEqual(source, "DERIV_STATEMENT_RECONSTRUCTED")

    def test_missing_optional_row_currency_uses_authenticated_account_currency(self):
        rows = rows_for_day()
        rows[0].pop("currency")
        reference, _ = derive_utc_day_start_balance(
            current_balance=101, transactions=rows, day_start_epoch=0, day_end_epoch=2000,
            currency="USD",
        )
        self.assertEqual(reference, 100.0)
        mismatch = rows_for_day()
        mismatch[0]["currency"] = "EUR"
        with self.assertRaisesRegex(ValueError, "STATEMENT_CURRENCY_MISMATCH"):
            derive_utc_day_start_balance(
                current_balance=101, transactions=mismatch, day_start_epoch=0,
                day_end_epoch=2000, currency="USD",
            )

    def test_missing_identity_or_truncated_or_inconsistent_statement_is_unknown(self):
        with self.assertRaisesRegex(ValueError, "STATEMENT_FIELDS_UNVERIFIED"):
            derive_utc_day_start_balance(
                current_balance=101, transactions=[{"transaction_time": 1000,
                    "amount": 1, "balance_after": 101, "currency": "USD"}],
                day_start_epoch=0, day_end_epoch=2000, currency="USD",
            )
        with self.assertRaisesRegex(ValueError, "STATEMENT_LIMIT_REACHED"):
            derive_utc_day_start_balance(
                current_balance=101, transactions=rows_for_day(), day_start_epoch=0,
                day_end_epoch=2000, currency="USD", maximum_transactions=2,
            )
        bad = rows_for_day()
        bad[-1] = dict(bad[-1], balance_after=102.0)
        with self.assertRaisesRegex(ValueError, "BALANCE_CHAIN_BROKEN"):
            derive_utc_day_start_balance(
                current_balance=102, transactions=bad, day_start_epoch=0, day_end_epoch=2000,
                currency="USD",
            )

    def test_empty_day_uses_current_verified_balance(self):
        self.assertEqual(
            derive_utc_day_start_balance(current_balance=12, transactions=[], day_start_epoch=0,
                day_end_epoch=2000, currency="USD"),
            (12, "DERIV_CURRENT_BALANCE_NO_UTC_DAY_TRANSACTIONS"),
        )

    def test_drawdown_trip_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "risk.json"
            guard = PersistentDailyRiskGuard(path)
            guard.initialize_day(account_loginid="CR1", currency="USD", utc_day="2026-10-10",
                reference_balance=100, baseline_source="test", now=NOW)
            result = guard.permit(account_loginid="CR1", currency="USD", current_balance=97,
                captured_at=NOW, now=NOW)
            self.assertFalse(result["allowed"])
            self.assertEqual(result["reason"], "DAILY_DRAWDOWN_LIMIT")
            restarted = PersistentDailyRiskGuard(path)
            self.assertTrue(restarted.tripped)
            self.assertFalse(restarted.permit(account_loginid="CR1", currency="USD",
                current_balance=100, captured_at=NOW, now=NOW)["allowed"])

    def test_three_consecutive_closed_losses_trip_and_replay_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "risk.json"
            guard = PersistentDailyRiskGuard(path)
            guard.initialize_day(account_loginid="CR1", currency="USD", utc_day="2026-10-10",
                reference_balance=100, baseline_source="test", now=NOW)
            result = None
            for i in range(3):
                result = guard.record_closed_trade(intent_id=f"I{i}", contract_id=f"C{i}",
                    broker_transaction_id=f"T{i}", account_loginid="CR1", currency="USD",
                    net_pnl=-0.1, post_balance=99.7, closed_at=NOW + timedelta(seconds=i),
                    terminal=True, reconciled=True)
            self.assertFalse(result["allowed"])
            self.assertEqual(result["reason"], "CONSECUTIVE_LOSS_LIMIT")
            self.assertTrue(PersistentDailyRiskGuard(path).tripped)

    def test_unreconciled_or_conflicting_settlement_trips(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "risk.json"
            guard = PersistentDailyRiskGuard(path)
            guard.initialize_day(account_loginid="CR1", currency="USD", utc_day="2026-10-10",
                reference_balance=100, baseline_source="test", now=NOW)
            result = guard.record_closed_trade(intent_id="I", contract_id="C", broker_transaction_id="T",
                account_loginid="CR1", currency="USD", net_pnl=-0.1, post_balance=99.9,
                closed_at=NOW, terminal=True, reconciled=False)
            self.assertFalse(result["allowed"])
            self.assertEqual(result["reason"], "SETTLEMENT_OR_RECONCILIATION_UNVERIFIED")

    def test_unknown_corrupt_state_and_account_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "risk.json"
            path.write_text("{broken", encoding="utf-8")
            guard = PersistentDailyRiskGuard(path)
            self.assertFalse(guard.permit(account_loginid="CR1", currency="USD",
                current_balance=100, captured_at=NOW, now=NOW)["allowed"])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "risk.json"
            guard = PersistentDailyRiskGuard(path)
            guard.initialize_day(account_loginid="CR1", currency="USD", utc_day="2026-10-10",
                reference_balance=100, baseline_source="test", now=NOW)
            result = guard.permit(account_loginid="OTHER", currency="USD", current_balance=100,
                captured_at=NOW, now=NOW)
            self.assertFalse(result["allowed"])
            self.assertEqual(result["reason"], "DAILY_RISK_ACCOUNT_BINDING_MISMATCH")


if __name__ == "__main__":
    unittest.main()
