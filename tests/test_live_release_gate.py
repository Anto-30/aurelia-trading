import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import scripts.live_release_gate as gate
from runtime.core.release_gate import read_live_release
from runtime.core.events import sha256
from runtime.ops.readiness_attestation import config_hash as readiness_config_hash
from pathlib import Path
import tempfile


class LiveReleaseGateTests(unittest.TestCase):
    def test_current_repository_is_fail_closed(self):
        with self.assertRaises(RuntimeError) as ctx:
            gate.check_certification_evidence()
        self.assertIn("strict certification evidence block", str(ctx.exception))

    def test_invalid_deriv_auth_mode_is_rejected(self):
        env = {
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
            "DERIV_AUTH_MODE": "deriv_auth_token",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(RuntimeError, "DERIV_AUTH_MODE must be pat or oauth"):
                gate.check_environment()

    def test_oauth_mode_does_not_require_pat_application_id(self):
        env = {
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
            "DERIV_AUTH_MODE": "oauth",
            "DERIV_APP_ID": "",
        }
        with patch.dict(os.environ, env, clear=False):
            gate.check_environment()

    def test_readiness_is_recomputed_and_never_trusted_from_a_snapshot(self):
        current = {
            "final_execution_authorization": False,
            "live_execution": "BLOCKED",
            "blockers": [{"gate": "LIVE_RELEASE", "status": "FAIL"}],
        }
        with patch.object(gate, "evaluate_readiness", return_value=current) as evaluate:
            with self.assertRaisesRegex(RuntimeError, "dynamic readiness final_execution_authorization is false"):
                gate.check_readiness()
        evaluate.assert_called_once_with(gate.ROOT)

    def test_dynamic_readiness_rejects_blockers_even_if_authorization_flag_is_true(self):
        current = {
            "final_execution_authorization": True,
            "live_execution": "ENABLED",
            "blockers": [{"gate": "PROSPECTIVE_OOS", "status": "FAIL"}],
        }
        with patch.object(gate, "evaluate_readiness", return_value=current):
            with self.assertRaisesRegex(RuntimeError, "dynamic readiness blockers present"):
                gate.check_readiness()

    def test_dynamic_readiness_requires_a_well_formed_payload(self):
        with patch.object(gate, "evaluate_readiness", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "invalid payload"):
                gate.check_readiness()

    def test_unsupported_currency_is_rejected(self):
        env = {
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "EUR",
            "DERIV_ENVIRONMENT": "real",
            "DERIV_AUTH_MODE": "oauth",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(RuntimeError, "DERIV_EXPECTED_CURRENCY must be USD"):
                gate.check_environment()

    def test_release_gate_cannot_use_missing_session_evidence(self):
        original = gate.SESSION_EVIDENCE_PATH
        try:
            gate.SESSION_EVIDENCE_PATH = gate.ROOT / "artifacts" / "definitely-missing-session.json"
            with self.assertRaises(RuntimeError):
                gate.check_session_evidence()
        finally:
            gate.SESSION_EVIDENCE_PATH = original

    def test_live_release_requires_all_canonical_and_independent_safety_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "LIVE_LOCK.yaml"
            lock.write_text(
                "schema: aurelia.live_lock.v1\n"
                "live_trading_enabled: true\n"
                "FINAL_EXECUTION_AUTHORIZATION: true\n"
                "LIVE_EXECUTION: ENABLED\n"
                "capital_plane_mode: LIVE\n"
                "research_capital_authority: false\n"
                "external_repositories_capital_forbidden: true\n"
                "blind_resubmission: false\n"
                "kill_switch_independent: true\n",
                encoding="utf-8",
            )
            self.assertTrue(read_live_release(lock).may_move_capital)

    def test_live_release_blocks_missing_or_blocked_live_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "LIVE_LOCK.yaml"
            prefix = (
                "live_trading_enabled: true\n"
                "FINAL_EXECUTION_AUTHORIZATION: true\n"
                "capital_plane_mode: LIVE\n"
            )
            lock.write_text(prefix + "LIVE_EXECUTION: BLOCKED\n", encoding="utf-8")
            self.assertFalse(read_live_release(lock).may_move_capital)
            lock.write_text(prefix, encoding="utf-8")
            self.assertFalse(read_live_release(lock).may_move_capital)


    def test_live_release_blocks_safety_invariant_mismatch_and_duplicate_keys(self):
        valid = (
            "schema: aurelia.live_lock.v1\n"
            "live_trading_enabled: true\n"
            "FINAL_EXECUTION_AUTHORIZATION: true\n"
            "LIVE_EXECUTION: ENABLED\n"
            "capital_plane_mode: LIVE\n"
            "research_capital_authority: false\n"
            "external_repositories_capital_forbidden: true\n"
            "blind_resubmission: false\n"
            "kill_switch_independent: true\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "LIVE_LOCK.yaml"
            self.assertTrue((lock.write_text(valid, encoding="utf-8") or True) and read_live_release(lock).may_move_capital)
            invalid_variants = (
                valid.replace("research_capital_authority: false", "research_capital_authority: true"),
                valid.replace("external_repositories_capital_forbidden: true", "external_repositories_capital_forbidden: false"),
                valid.replace("blind_resubmission: false", "blind_resubmission: true"),
                valid.replace("kill_switch_independent: true", "kill_switch_independent: false"),
                valid + "LIVE_EXECUTION: ENABLED\n",
                valid.replace("schema: aurelia.live_lock.v1", "schema: unknown.v1"),
            )
            for payload in invalid_variants:
                with self.subTest(payload=payload[-80:]):
                    lock.write_text(payload, encoding="utf-8")
                    self.assertFalse(read_live_release(lock).may_move_capital)


    def test_script_release_gate_rejects_capital_plane_invariant_mismatches(self):
        original = gate.LIVE_LOCK_PATH
        valid = (
            "schema: aurelia.live_lock.v1\n"
            "live_trading_enabled: true\n"
            "FINAL_EXECUTION_AUTHORIZATION: true\n"
            "LIVE_EXECUTION: ENABLED\n"
            "capital_plane_mode: LIVE\n"
            "research_capital_authority: false\n"
            "external_repositories_capital_forbidden: true\n"
            "blind_resubmission: false\n"
            "kill_switch_independent: true\n"
        )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                gate.LIVE_LOCK_PATH = Path(tmp) / "LIVE_LOCK.yaml"
                gate.LIVE_LOCK_PATH.write_text(valid, encoding="utf-8")
                gate.check_live_lock()
                invalid = (
                    valid.replace("research_capital_authority: false", "research_capital_authority: true"),
                    valid.replace("external_repositories_capital_forbidden: true", "external_repositories_capital_forbidden: false"),
                    valid.replace("blind_resubmission: false", "blind_resubmission: true"),
                    valid.replace("kill_switch_independent: true", "kill_switch_independent: false"),
                    valid.replace("schema: aurelia.live_lock.v1", "schema: invalid"),
                )
                for payload in invalid:
                    with self.subTest(payload=payload[-80:]):
                        gate.LIVE_LOCK_PATH.write_text(payload, encoding="utf-8")
                        with self.assertRaises(RuntimeError):
                            gate.check_live_lock()
        finally:
            gate.LIVE_LOCK_PATH = original



    def _valid_readiness_fixture(self, source_sha: str = "test-source-sha") -> dict:
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(minutes=5)).isoformat()
        capabilities = (
            "MARKET_DATA", "PROBABILITY", "RISK_WARDEN", "EXECUTION_FIREWALL",
            "EXPOSURE", "RECONCILIATION", "WATCHDOG", "IDEMPOTENCY", "PERSISTENT_WORKER",
        )
        verified = {
            name: {
                "status": "PASS", "issuer": "test-issuer", "subject": "test-subject",
                "evidence_hash": "hash-" + name, "provenance": "test",
                "expires_at_utc": expires,
            }
            for name in capabilities
        }
        return {
            "schema": "aurelia.readiness.v1",
            "generated_at_utc": now.isoformat(),
            "final_execution_authorization": True,
            "live_execution": "ENABLED",
            "live_orders": 0,
            "blockers": [],
            "strategy_live_eligible": True,
            "controls": {
                "risk_warden": True, "execution_firewall": True, "exposure": True,
                "reconciliation": True, "watchdog": True, "idempotency": True,
            },
            "evidence": {
                "market_data": True, "prospective_oos": True, "calibration": True,
                "economics": True, "soak_3600s": True,
            },
            "live_lock": {
                "live_trading_enabled": True,
                "final_execution_authorization": True,
                "capital_plane_mode": "LIVE",
            },
            "deriv": {
                "account_loginid": "CRTEST", "account_type": "real",
                "environment": "real", "currency": "USD",
                "balance": 200.0, "balance_fresh": True,
            },
            "attestations": {
                "source_sha": source_sha,
                "config_hash": readiness_config_hash(gate.ROOT),
                "runtime_id": "test-runtime",
                "all_passed": True,
                "verified": verified,
                "failures": {},
            },
        }

    def test_readiness_rejects_string_booleans_cross_account_and_stale_source(self):
        report = self._valid_readiness_fixture()
        env = {
            "GITHUB_SHA": "test-source-sha",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "AURELIA_READINESS_MAX_AGE_SECONDS": "30",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch.object(gate, "evaluate_readiness", return_value=report):
                gate.check_readiness()

            report["final_execution_authorization"] = "true"
            with patch.object(gate, "evaluate_readiness", return_value=report):
                with self.assertRaisesRegex(RuntimeError, "literal true"):
                    gate.check_readiness()

            report["final_execution_authorization"] = True
            report["deriv"]["account_loginid"] = "CROTHER"
            with patch.object(gate, "evaluate_readiness", return_value=report):
                with self.assertRaisesRegex(RuntimeError, "account identity mismatch"):
                    gate.check_readiness()

            report["deriv"]["account_loginid"] = "CRTEST"
            report["attestations"]["source_sha"] = "old-source"
            with patch.object(gate, "evaluate_readiness", return_value=report):
                with self.assertRaisesRegex(RuntimeError, "source revision mismatch"):
                    gate.check_readiness()

    def test_public_transport_gate_requires_fresh_hash_linked_read_only_evidence(self):
        original = gate.PUBLIC_TRANSPORT_EVIDENCE_PATH
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "transport.json"
            gate.PUBLIC_TRANSPORT_EVIDENCE_PATH = path
            evidence = {
                "schema": "aurelia.deriv_public_transport.v1",
                "source_sha": "test-source-sha",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "endpoint": "wss://api.derivws.com/trading/v1/options/ws/public",
                "active_symbol_count": 10,
                "capital_authority_granted": False,
                "order_submission_permitted": False,
            }
            evidence["record_hash"] = sha256(evidence)
            try:
                with patch.dict(os.environ, {"GITHUB_SHA": "test-source-sha"}, clear=False):
                    path.write_text(json.dumps(evidence), encoding="utf-8")
                    gate.check_runtime_verification_flags()
                    tampered = dict(evidence)
                    tampered["active_symbol_count"] = 0
                    path.write_text(json.dumps(tampered), encoding="utf-8")
                    with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                        gate.check_runtime_verification_flags()
            finally:
                gate.PUBLIC_TRANSPORT_EVIDENCE_PATH = original

if __name__ == "__main__":
    unittest.main()
