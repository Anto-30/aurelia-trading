from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from runtime.core.models import AccountIdentity, CapitalSnapshot
from scripts.verify_deriv_read_only_state import (
    ReadOnlyVerificationError,
    collect_read_only_snapshot,
    read_persistent_runtime_controls,
)


UTC = timezone.utc


class ReadOnlyDerivAdapter:
    def __init__(self, *, balances=(100.0, 100.0), portfolio=None, statement=None):
        self.account = AccountIdentity("CRREAL", "real", "USD", "real")
        self.balances = list(balances)
        self.portfolio_rows = list(portfolio or [])
        self.statement_rows = list(statement or [])
        self.calls = []

    async def connect(self):
        self.calls.append("connect")
        return self.account

    async def get_balance(self):
        self.calls.append("balance")
        value = self.balances.pop(0) if len(self.balances) > 1 else self.balances[0]
        return CapitalSnapshot(
            balance=value,
            currency="USD",
            available_balance=value,
            captured_at=datetime.now(UTC),
            source="test:deriv-balance",
            account=self.account,
        )

    async def portfolio(self):
        self.calls.append("portfolio")
        return self.portfolio_rows

    async def statement(self, *, limit=999, date_from=None, date_to=None):
        self.calls.append(("statement", limit, date_from, date_to))
        return self.statement_rows

    async def request_proposal(self, *_args, **_kwargs):
        raise AssertionError("read-only verifier must never request a proposal")

    async def submit_authorized_order(self, *_args, **_kwargs):
        raise AssertionError("read-only verifier must never submit an order")


class DerivReadOnlyStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_uses_only_balance_portfolio_and_statement_reads(self):
        now = datetime.now(UTC)
        adapter = ReadOnlyDerivAdapter(
            portfolio=[{"contract_id": "123"}, {"contract_id": "456"}],
            statement=[],
        )

        result = await collect_read_only_snapshot(
            adapter,
            expected_loginid="CRREAL",
            expected_currency="USD",
            now=now,
        )

        self.assertEqual(
            adapter.calls,
            ["connect", "balance", "portfolio", ("statement", 999, int(
                datetime(now.year, now.month, now.day, tzinfo=UTC).timestamp()
            ), int(now.timestamp())), "balance"],
        )
        self.assertEqual(result["open_positions_count"], 2)
        self.assertEqual(result["statement_transaction_count"], 0)
        self.assertEqual(result["day_opening_balance"], 100.0)
        self.assertTrue(result["balance_stable_across_snapshot"])
        self.assertEqual(result["trade_api_calls"], [])
        self.assertEqual(result["orders_submitted"], 0)
        self.assertFalse(result["capital_movement"])

    async def test_balance_change_during_read_sequence_blocks_snapshot(self):
        adapter = ReadOnlyDerivAdapter(balances=(100.0, 99.0))
        with self.assertRaisesRegex(
            ReadOnlyVerificationError,
            "DERIV_READONLY_BALANCE_CHANGED_DURING_SNAPSHOT",
        ):
            await collect_read_only_snapshot(
                adapter,
                expected_loginid="CRREAL",
                expected_currency="USD",
            )

    async def test_statement_limit_reached_blocks_incomplete_history(self):
        adapter = ReadOnlyDerivAdapter(statement=[{}] * 999)
        with self.assertRaisesRegex(
            ReadOnlyVerificationError,
            "DERIV_READONLY_STATEMENT_LIMIT_REACHED",
        ):
            await collect_read_only_snapshot(
                adapter,
                expected_loginid="CRREAL",
                expected_currency="USD",
            )

    async def test_account_identity_or_currency_mismatch_blocks_snapshot(self):
        adapter = ReadOnlyDerivAdapter()
        with self.assertRaisesRegex(
            ReadOnlyVerificationError,
            "DERIV_READONLY_ACCOUNT_BINDING_MISMATCH",
        ):
            await collect_read_only_snapshot(
                adapter,
                expected_loginid="OTHER",
                expected_currency="USD",
            )

        adapter = ReadOnlyDerivAdapter()
        with self.assertRaisesRegex(
            ReadOnlyVerificationError,
            "DERIV_READONLY_ACCOUNT_BINDING_MISMATCH",
        ):
            await collect_read_only_snapshot(
                adapter,
                expected_loginid="CRREAL",
                expected_currency="EUR",
            )


class PersistentReadOnlyStateTests(unittest.TestCase):
    def write_states(self, directory: Path, *, loginid="CRREAL", currency="USD", utc_day=None):
        now = datetime.now(UTC)
        daily = {
            "schema_version": 1,
            "initialized": True,
            "account_loginid": loginid,
            "currency": currency,
            "utc_day": utc_day or now.date().isoformat(),
            "reference_balance": 100.0,
            "baseline_source": "DERIV_STATEMENT_RECONSTRUCTED",
            "current_balance": 100.0,
            "daily_realized_pnl": 0.0,
            "consecutive_losses": 0,
            "consecutive_broker_failures": 0,
            "settlements": {},
            "tripped": False,
            "reason": None,
            "updated_at_utc": now.isoformat(),
        }
        kill = {
            "schema": "aurelia.kill_switch_state.v1",
            "state": "STARTUP_LOCKED",
            "reason": "STARTUP_LOCKED",
            "generation": 0,
            "activated_at_utc": now.isoformat(),
            "last_reset_nonce": None,
            "source_sha": "source-sha",
            "fault_source_sha": None,
            "updated_at_utc": now.isoformat(),
        }
        daily_path = directory / "daily-risk.json"
        kill_path = directory / "kill-switch-state.json"
        daily_path.write_text(json.dumps(daily), encoding="utf-8")
        kill_path.write_text(json.dumps(kill), encoding="utf-8")
        return daily_path, kill_path

    def test_persisted_daily_risk_and_kill_switch_states_are_read_and_hash_linked(self):
        with tempfile.TemporaryDirectory() as td:
            daily_path, kill_path = self.write_states(Path(td))
            now = datetime.now(UTC)
            result = read_persistent_runtime_controls(
                account_loginid="CRREAL",
                currency="USD",
                utc_day=now.date().isoformat(),
                daily_risk_path=daily_path,
                kill_switch_path=kill_path,
            )
            self.assertTrue(result["daily_risk_state_persisted"])
            self.assertTrue(result["kill_switch_state_persisted"])
            self.assertEqual(result["kill_switch_state"], "STARTUP_LOCKED")
            self.assertEqual(len(result["daily_risk_state_sha256"]), 64)
            self.assertEqual(len(result["kill_switch_state_sha256"]), 64)

    def test_missing_or_mismatched_persistent_state_is_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            daily_path, kill_path = self.write_states(Path(td), loginid="OTHER")
            now = datetime.now(UTC)
            with self.assertRaisesRegex(
                ReadOnlyVerificationError,
                "PERSISTENT_DAILY_RISK_STATE_MISMATCH",
            ):
                read_persistent_runtime_controls(
                    account_loginid="CRREAL",
                    currency="USD",
                    utc_day=now.date().isoformat(),
                    daily_risk_path=daily_path,
                    kill_switch_path=kill_path,
                )

        with tempfile.TemporaryDirectory() as td:
            daily_path, kill_path = self.write_states(Path(td))
            kill_path.unlink()
            now = datetime.now(UTC)
            with self.assertRaisesRegex(
                ReadOnlyVerificationError,
                "PERSISTENT_RISK_OR_KILL_SWITCH_STATE_MISSING",
            ):
                read_persistent_runtime_controls(
                    account_loginid="CRREAL",
                    currency="USD",
                    utc_day=now.date().isoformat(),
                    daily_risk_path=daily_path,
                    kill_switch_path=kill_path,
                )


if __name__ == "__main__":
    unittest.main()
