from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.atos_validation.audited_ledger import AuditedLedgerWriter, verify_ledger

DATA_HASH = hashlib.sha256(b"data").hexdigest()
CONFIG_HASH = hashlib.sha256(b"config").hexdigest()


class AuditedLedgerTests(unittest.TestCase):
    def test_decisions_trades_costs_and_chain(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trades.jsonl"
            writer = AuditedLedgerWriter(path, symbol="R_100", data_sha256=DATA_HASH, granularity_seconds=60)
            writer.record_decision(signal_bar_epoch=180, strategy="alpha_beta_hmm", model_config_sha256=CONFIG_HASH,
                                   fold_id="fold_1", action="ENTER_LONG", reason_codes=["probability_too_low"],
                                   hmm_regime_state="RANGE", accepted=False, probability=0.4)
            decision = writer.record_decision(signal_bar_epoch=240, strategy="alpha_beta_hmm", model_config_sha256=CONFIG_HASH,
                                              fold_id="fold_1", action="ENTER_LONG", reason_codes=["qualified"],
                                              hmm_regime_state="TREND", accepted=True, probability=0.7)
            with self.assertRaisesRegex(ValueError, "next candle open"):
                writer.record_trade(decision_event_id=decision, entry_epoch=240,
                                    exit_timestamp="1970-01-01T00:05:00Z", entry_price=100, exit_price=101,
                                    initial_risk_cash=10, gross_pnl_cash=20, spread_cost_cash=1,
                                    slippage_cost_cash=0.5)
            writer.record_trade(decision_event_id=decision, entry_epoch=300,
                                exit_timestamp="1970-01-01T00:06:00Z", entry_price=100, exit_price=102,
                                initial_risk_cash=10, gross_pnl_cash=20, spread_cost_cash=1,
                                slippage_cost_cash=0.5, commission_cost_cash=0.5,
                                spread_pips=0.2, slippage_bps=1.5,
                                entry_reference_price=100.0, exit_reference_price=102.0,
                                entry_spread_cost_cash=0.5, exit_spread_cost_cash=0.5,
                                entry_slippage_cost_cash=0.25, exit_slippage_cost_cash=0.25,
                                stop_reference_price=99.0, target_reference_price=103.0,
                                exit_reason="TARGET_HIT", cost_profile_status="EXPLORATORY_UNVERIFIED")
            manifest = writer.close()
            self.assertEqual(manifest["decision_record_count"], 2)
            self.assertEqual(manifest["closed_trade_record_count"], 1)
            verified = verify_ledger(path)
            self.assertTrue(verified["integrity_verified"])
            self.assertTrue(verified["manifest_verified"])
            records = [json.loads(line) for line in path.read_text().splitlines()]
            trade = next(row for row in records if row["record_type"] == "trade_closed")
            self.assertEqual(trade["entry_bar_epoch"], 300)
            self.assertEqual(trade["hmm_regime_state"], "TREND")
            self.assertAlmostEqual(trade["cost_r"], 0.2)
            self.assertAlmostEqual(trade["r_multiple"], 1.8)
            self.assertAlmostEqual(trade["entry_spread_cost_cash"] + trade["exit_spread_cost_cash"], trade["spread_cost_cash"])
            self.assertAlmostEqual(trade["entry_slippage_cost_cash"] + trade["exit_slippage_cost_cash"], trade["slippage_cost_cash"])
            self.assertEqual(trade["exit_reason"], "TARGET_HIT")
            self.assertEqual(records[1]["record_sha256"], records[2]["previous_record_sha256"])


    def test_execution_time_cancellation_resolves_accepted_decision_without_fake_trade(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cancel.jsonl"
            writer = AuditedLedgerWriter(path, symbol="R_100", data_sha256=DATA_HASH, granularity_seconds=60)
            decision_id = writer.record_decision(
                signal_bar_epoch=60, strategy="alpha_beta_hmm", model_config_sha256=CONFIG_HASH,
                fold_id="fold_1", action="ENTER_LONG", reason_codes=["valid_signal"],
                hmm_regime_state="TREND", accepted=True, probability=0.7,
            )
            writer.cancel_decision(
                decision_event_id=decision_id, cancellation_epoch=120,
                reason_codes=["ENTRY_GAP_INVALIDATES_STOP_TARGET_GEOMETRY"],
            )
            manifest = writer.close()
            verified = verify_ledger(path)
            self.assertEqual(manifest["cancelled_entry_count"], 1)
            self.assertEqual(verified["cancelled_entry_count"], 1)
            self.assertEqual(verified["closed_trade_record_count"], 0)
            self.assertTrue(verified["manifest_verified"])

    def test_rejects_misaligned_signal_and_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trades.jsonl"
            writer = AuditedLedgerWriter(path, symbol="R_100", data_sha256=DATA_HASH)
            with self.assertRaisesRegex(ValueError, "align"):
                writer.record_decision(signal_bar_epoch=181, strategy="alpha_beta_hmm",
                                       model_config_sha256=CONFIG_HASH, fold_id="fold_1",
                                       action="NO_TRADE", reason_codes=["x"], hmm_regime_state="TREND", accepted=False)
            writer.close()
            with self.assertRaises(FileExistsError):
                AuditedLedgerWriter(path, symbol="R_100", data_sha256=DATA_HASH)

    def test_rejects_trade_without_preceding_accepted_decision(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trades.jsonl"
            writer = AuditedLedgerWriter(path, symbol="R_100", data_sha256=DATA_HASH)
            with self.assertRaisesRegex(ValueError, "preceding accepted decision"):
                writer.record_trade(decision_event_id="absent", entry_epoch=60,
                                    exit_timestamp="1970-01-01T00:02:00Z", entry_price=100, exit_price=99,
                                    initial_risk_cash=10, gross_pnl_cash=-10, spread_cost_cash=0, slippage_cost_cash=0)
            writer.close()

    def test_detects_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trades.jsonl"
            writer = AuditedLedgerWriter(path, symbol="R_100", data_sha256=DATA_HASH)
            writer.record_decision(signal_bar_epoch=60, strategy="alpha_beta_hmm", model_config_sha256=CONFIG_HASH,
                                   fold_id="fold_1", action="NO_TRADE", reason_codes=["no_signal"],
                                   hmm_regime_state="RANGE", accepted=False)
            writer.close()
            path.write_text(path.read_text().replace("no_signal", "changed_signal"))
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_ledger(path)


if __name__ == "__main__":
    unittest.main()
