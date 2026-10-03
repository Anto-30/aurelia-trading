from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.ops.readiness_orchestrator import evaluate


class ReadinessReleaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = dict(os.environ)
        for key in (
            "DERIV_AUTH_TOKEN",
            "DERIV_APP_ID",
            "DERIV_EXPECTED_LOGINID",
            "AURELIA_DERIV_SESSION_VERIFIED",
            "AURELIA_BALANCE_VERIFIED",
            "AURELIA_RAILWAY_WORKER_HEALTHY",
            "AURELIA_STRATEGY_LIVE_ELIGIBLE",
            "AURELIA_PROSPECTIVE_OOS_PASS",
            "AURELIA_CALIBRATION_PASS",
            "AURELIA_ECONOMICS_PASS",
            "AURELIA_SOAK_3600S_PASS",
            "AURELIA_MARKET_DATA_VALIDATED",
            "AURELIA_PROBABILITY_VALID",
            "AURELIA_RISK_WARDEN_PASS",
            "AURELIA_EXECUTION_FIREWALL_PASS",
            "AURELIA_EXPOSURE_PASS",
            "AURELIA_RECONCILIATION_HEALTHY",
            "AURELIA_WATCHDOG_HEALTHY",
            "AURELIA_IDEMPOTENCY_HEALTHY",
            "AURELIA_DERIV_REST_VERIFIED",
        ):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.original)

    def _make_all_runtime_gates_pass(self) -> None:
        os.environ.update(
            {
                "DERIV_AUTH_TOKEN": "test-token",
                "DERIV_APP_ID": "test-app",
                "DERIV_EXPECTED_LOGINID": "test-login",
                "AURELIA_DERIV_SESSION_VERIFIED": "true",
                "AURELIA_BALANCE_VERIFIED": "true",
                "AURELIA_RAILWAY_WORKER_HEALTHY": "true",
                "AURELIA_STRATEGY_LIVE_ELIGIBLE": "true",
                "AURELIA_PROSPECTIVE_OOS_PASS": "true",
                "AURELIA_CALIBRATION_PASS": "true",
                "AURELIA_ECONOMICS_PASS": "true",
                "AURELIA_SOAK_3600S_PASS": "true",
                "AURELIA_MARKET_DATA_VALIDATED": "true",
                "AURELIA_PROBABILITY_VALID": "true",
                "AURELIA_RISK_WARDEN_PASS": "true",
                "AURELIA_EXECUTION_FIREWALL_PASS": "true",
                "AURELIA_EXPOSURE_PASS": "true",
                "AURELIA_RECONCILIATION_HEALTHY": "true",
                "AURELIA_WATCHDOG_HEALTHY": "true",
                "AURELIA_IDEMPOTENCY_HEALTHY": "true",
                "AURELIA_DERIV_REST_VERIFIED": "true",
                "AURELIA_VERIFIED_AVAILABLE_BALANCE": "1.45",
            }
        )

    def test_live_lock_always_blocks_capital(self) -> None:
        self._make_all_runtime_gates_pass()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "LIVE_LOCK.yaml").write_text(
                "live_trading_enabled: false\n"
                "FINAL_EXECUTION_AUTHORIZATION: false\n"
                "capital_plane_mode: VERIFY_ONLY\n",
                encoding="utf-8",
            )
            report = evaluate(root)
        self.assertFalse(report["final_execution_authorization"])
        self.assertEqual("BLOCKED", report["live_execution"])

    def test_missing_release_file_fails_closed(self) -> None:
        self._make_all_runtime_gates_pass()
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate(Path(tmp))
        self.assertFalse(report["final_execution_authorization"])
        self.assertEqual("BLOCKED", report["live_execution"])


if __name__ == "__main__":
    unittest.main()
