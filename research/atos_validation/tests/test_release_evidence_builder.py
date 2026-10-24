from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.build_release_evidence import git_blob_sha1, percentile


class EvidenceBuilderTests(unittest.TestCase):
    def test_percentile(self):
        self.assertIsNone(percentile([], .99))
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], .99), 4.0)

    def test_git_blob_sha1(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "LIVE_LOCK.yaml"
            path.write_text("live_trading_enabled: false\n")
            self.assertEqual(len(git_blob_sha1(path)), 40)

    def test_incomplete_output_has_nine_exact_schemas_and_nulls(self):
        root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as td:
            out, missing_lock = Path(td) / "evidence", Path(td) / "no-lock.yaml"
            run = subprocess.run([sys.executable, str(root / "scripts/build_release_evidence.py"),
                                  "--evidence-dir", str(out), "--lock-path", str(missing_lock)],
                                 cwd=root, text=True, capture_output=True, check=False)
            self.assertEqual(run.returncode, 3, run.stdout + run.stderr)
            expected = {
                "broker_lifecycle.json": {"app_id", "connection_start_utc", "connection_end_utc", "total_heartbeats_received", "missed_heartbeats", "unplanned_disconnects", "data_gap_seconds"},
                "recovery_matrix.json": {"simulated_disconnects", "successful_reconnections", "failed_reconnections", "average_recovery_time_ms", "max_recovery_time_ms", "phantom_orders_generated"},
                "soak_3600s.json": {"duration_seconds", "total_ticks_processed", "average_latency_ms", "p95_latency_ms", "p99_latency_ms", "max_latency_ms", "memory_leak_detected"},
                "prospective_oos.json": {"data_artifact_sha256", "oos_start_date", "oos_end_date", "total_trades", "net_expectancy_r", "profit_factor", "max_drawdown_percent", "win_rate_percent", "sharpe_ratio"},
                "calibration.json": {"model_type", "number_of_states", "training_iterations_to_converge", "in_sample_expectancy_r", "out_of_sample_expectancy_r", "performance_degradation_percent"},
                "execution_economics.json": {"symbol", "average_spread_pips", "average_slippage_bps", "total_commission_paid_simulated", "total_slippage_cost_simulated", "cost_as_percent_of_gross_profit"},
                "security_audit.json": {"read_only_token_auth_success", "trade_attempt_with_read_only_token", "secrets_masked_in_logs", "live_lock_yaml_blob_hash"},
                "deployment.json": {"ci_pipeline_status", "execution_environment", "live_execution_blocked", "final_execution_authorization"},
                "strategy_eligibility.json": {"meets_minimum_expectancy", "meets_minimum_profit_factor", "meets_max_drawdown_limit", "walk_forward_stable", "eligible_for_live_unlock"},
            }
            for filename, fields in expected.items():
                self.assertEqual(set(json.loads((out / filename).read_text())), fields)
            self.assertTrue((out / "evidence_notes.md").is_file())


if __name__ == "__main__":
    unittest.main()
