"""Read-only AURELIA governance audit.

All non-PASS states fail the process. This module never authenticates to Deriv,
starts/stops workers, writes configuration, or submits orders.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# Tests are intentionally isolated from the user's live repository.
from scripts.audit.aurelia_read_only_audit import (
    Audit,
    check_live_lock,
    check_probability_policy,
)


class AuditGateTests(unittest.TestCase):
    def test_live_lock_requires_canonical_yaml_and_exact_invariants(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / "config" / "LIVE_LOCK.yaml"
            lock.parent.mkdir()
            lock.write_text(
                "schema: aurelia.live_lock.v1\n"
                "live_trading_enabled: false\n"
                "FINAL_EXECUTION_AUTHORIZATION: false\n"
                "LIVE_EXECUTION: BLOCKED\n"
                "capital_plane_mode: VERIFY_ONLY\n"
                "research_capital_authority: false\n"
                "external_repositories_capital_forbidden: true\n"
                "blind_resubmission: false\n"
                "kill_switch_independent: true\n",
                encoding="utf-8",
            )
            result = check_live_lock(root)
            self.assertEqual(result["status"], "PASS")

    def test_live_lock_mutation_fails(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / "config" / "LIVE_LOCK.yaml"
            lock.parent.mkdir()
            lock.write_text("LIVE_EXECUTION: ALLOWED\n", encoding="utf-8")
            self.assertEqual(check_live_lock(root)["status"], "FAIL")

    def test_missing_live_lock_fails(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(check_live_lock(Path(tmp))["status"], "FAIL")

    def test_probability_policy_must_match_canonical_source_and_expected_band(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authority = root / "runtime" / "core" / "authority.py"
            source = root / "AURELIA_SOURCE_OF_TRUTH.json"
            authority.parent.mkdir(parents=True)
            authority.write_text(
                "MIN_PROBABILITY = 0.50\nMAX_PROBABILITY = 0.75\n",
                encoding="utf-8",
            )
            source.write_text(
                json.dumps({"probability_min": 0.50, "probability_max": 0.75}),
                encoding="utf-8",
            )
            result = check_probability_policy(root)
            self.assertEqual(result["status"], "PASS")

    def test_probability_policy_mismatch_fails(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authority = root / "runtime" / "core" / "authority.py"
            source = root / "AURELIA_SOURCE_OF_TRUTH.json"
            authority.parent.mkdir(parents=True)
            authority.write_text(
                "MIN_PROBABILITY = 0.50\nMAX_PROBABILITY = 0.75\n",
                encoding="utf-8",
            )
            source.write_text(
                json.dumps({"probability_min": 0.55, "probability_max": 0.75}),
                encoding="utf-8",
            )
            self.assertEqual(check_probability_policy(root)["status"], "FAIL")

    def test_every_fail_or_unknown_blocks_exit(self):
        audit = Audit()
        audit.record("data", "UNKNOWN", "dataset unavailable")
        audit.record("lock", "PASS", "canonical lock intact")
        self.assertNotEqual(audit.exit_code, 0)

    def test_clean_audit_is_zero(self):
        audit = Audit()
        audit.record("lock", "PASS", "canonical lock intact")
        self.assertEqual(audit.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
