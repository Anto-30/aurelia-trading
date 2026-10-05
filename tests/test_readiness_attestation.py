import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.ops.attestations import sign_attestation
from runtime.ops.readiness_attestation import (
    REQUIRED_CAPABILITIES,
    verify_readiness_attestations,
)


class ReadinessAttestationIntegrationTests(unittest.TestCase):
    def _root(self, td: str) -> Path:
        root = Path(td)
        (root / "config").mkdir()
        (root / "config" / "LIVE_LOCK.yaml").write_text("live_trading_enabled: false\n", encoding="utf-8")
        (root / "config" / "agent_capability_boundary.json").write_text(
            '{"capital_authority": false}\n', encoding="utf-8"
        )
        return root

    def _write_all(self, root: Path, source_sha: str, runtime_id: str, cfg_hash: str, key: str) -> None:
        directory = root / "attestations"
        directory.mkdir()
        now = datetime.now(timezone.utc)
        for capability in REQUIRED_CAPABILITIES:
            record = sign_attestation(
                {
                    "issuer": "AURELIA-control-plane",
                    "subject": runtime_id,
                    "capability": capability,
                    "status": "PASS",
                    "issued_at_utc": now.isoformat(),
                    "expires_at_utc": (now + timedelta(minutes=5)).isoformat(),
                    "source_sha": source_sha,
                    "runtime_id": runtime_id,
                    "config_hash": cfg_hash,
                    "evidence_hash": f"evidence-{capability}",
                    "provenance": "control_plane",
                },
                key,
            )
            (directory / f"{capability.lower()}.json").write_text(
                json.dumps(record), encoding="utf-8"
            )

    def test_all_current_attestations_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            self._write_all(root, "source-1", "runtime-1", "cfg-1", "secret")
            result = verify_readiness_attestations(
                root,
                runtime_id="runtime-1",
                expected_source_sha="source-1",
                expected_config_hash="cfg-1",
                signing_key="secret",
                attestation_dir=root / "attestations",
            )
            self.assertTrue(result["all_passed"])
            self.assertEqual(set(result["verified"]), set(REQUIRED_CAPABILITIES))

    def test_environment_flags_cannot_replace_missing_attestations(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            result = verify_readiness_attestations(
                root,
                runtime_id="runtime-1",
                expected_source_sha="source-1",
                expected_config_hash="cfg-1",
                signing_key="secret",
                attestation_dir=root / "attestations",
            )
            self.assertFalse(result["all_passed"])
            self.assertEqual(result["failures"]["MARKET_DATA"], "MISSING_ATTESTATION")

    def test_missing_runtime_identity_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            result = verify_readiness_attestations(
                root,
                runtime_id="",
                expected_source_sha="source-1",
                expected_config_hash="cfg-1",
                signing_key="secret",
                attestation_dir=root / "attestations",
            )
            self.assertFalse(result["all_passed"])
            self.assertEqual(result["failures"]["runtime_id"], "RUNTIME_ID_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
