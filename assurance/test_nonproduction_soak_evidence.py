from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from assurance.certification_evidence import validate_evidence_file
from assurance.nonproduction_soak_evidence import write_nonproduction_soak_evidence


ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
EXPECTED_UNKNOWN = "CONTINUOUS_RUNTIME_UNAVAILABLE"


def _timestamps(duration_seconds: int = 3600) -> tuple[str, str]:
    ended = datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=2)
    started = ended - timedelta(seconds=duration_seconds)
    return started.isoformat().replace("+00:00", "Z"), ended.isoformat().replace("+00:00", "Z")


def _write_observations(path: Path, *, fault: str | None = None) -> None:
    rows = []
    for elapsed in range(0, 3600, 5):
        row = {
            "elapsed_seconds": elapsed,
            "status": "DEGRADED",
            "state": "CAPITAL_PROTECTED",
            "liveness": True,
            "capital_can_open_new_exposure": False,
            "critical_unknowns": [EXPECTED_UNKNOWN],
        }
        if fault == "unexpected_unknown" and elapsed == 150:
            row["critical_unknowns"] = ["UNKNOWN_CAPITAL_STATE"]
        elif fault == "capital_exposure" and elapsed == 150:
            row["capital_can_open_new_exposure"] = True
        elif fault == "silent_degradation" and elapsed == 150:
            row["critical_unknowns"] = []
        elif fault == "subsecond" and elapsed == 150:
            row["elapsed_seconds"] = 150.125
        rows.append(row)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


class NonProductionSoakEvidenceTests(unittest.TestCase):
    def test_one_hour_soak_is_manual_only_on_main(self):
        workflow = (ROOT / ".github" / "workflows" / "non-production-3600s-soak.yml").read_text(encoding="utf-8")
        self.assertIn("on:\n  workflow_dispatch:\n", workflow)
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("group: aurelia-non-production-soak", workflow)
        triggers = workflow.split("permissions:", 1)[0]
        self.assertNotIn("\n  push:", triggers)
        self.assertNotIn("\n  schedule:", triggers)

    def _write(self, root: Path, *, duration_seconds: int = 3600, fault: str | None = None) -> Path:
        observations = root / "observations.ndjson"
        _write_observations(observations, fault=fault)
        started, ended = _timestamps(duration_seconds)
        output = root / "evidence" / "soak_3600s.json"
        write_nonproduction_soak_evidence(
            observations_path=observations,
            output_path=output,
            source_commit="d04564aca0648201feff0326fe9af0fbcee92e94",
            runtime_image_id="sha256:" + ("a" * 64),
            runtime_instance_id="container-instance-test",
            deployment_id="github-actions:123456:1",
            config_hash="b" * 64,
            started_at_utc=started,
            ended_at_utc=ended,
            controlled_restarts=3,
        )
        return output

    def test_emits_validator_accepted_run_bound_nonproduction_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            output = self._write(Path(d))
            evidence = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(evidence["environment"], "ci")
            self.assertEqual(evidence["result"], "PROVEN")
            self.assertEqual(evidence["execution_mode"], "VERIFY_ONLY")
            self.assertEqual(evidence["classification"], "SIMULATION_VERIFIED")
            self.assertGreaterEqual(evidence["actual_elapsed_seconds"], 3600)
            self.assertGreaterEqual(evidence["duration_seconds"], 3600)
            self.assertTrue(evidence["continuous"])
            self.assertEqual(evidence["health_checks"], 720)
            self.assertEqual(evidence["controlled_restarts"], 3)
            self.assertEqual(evidence["invariant_violations"], 0)
            self.assertEqual(evidence["silent_degradations"], 0)
            self.assertEqual(evidence["capital_authority_escapes"], 0)
            self.assertEqual(evidence["unresolved_unknown_states"], 0)
            self.assertEqual(evidence["known_expected_unknowns"], [EXPECTED_UNKNOWN])
            self.assertFalse(evidence["final_execution_authorization"])
            self.assertEqual(evidence["live_execution"], "BLOCKED")
            status, detail = validate_evidence_file(Path(d), "evidence/soak_3600s.json")
            self.assertEqual(status, "PASS", detail)

    def test_accepts_subsecond_monotonic_observation_timestamps(self):
        with tempfile.TemporaryDirectory() as d:
            output = self._write(Path(d), fault="subsecond")
            status, detail = validate_evidence_file(Path(d), "evidence/soak_3600s.json")
            self.assertEqual(status, "PASS", detail)
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(record["health_checks"], 720)

    def test_unexpected_unknown_state_prevents_evidence_emission(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "UNEXPECTED_CRITICAL_UNKNOWN"):
                self._write(Path(d), fault="unexpected_unknown")

    def test_capital_exposure_prevents_evidence_emission(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "CAPITAL_EXPOSURE_NOT_BLOCKED"):
                self._write(Path(d), fault="capital_exposure")

    def test_unexplained_degraded_status_prevents_evidence_emission(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "DEGRADED_STATUS_WITHOUT_KNOWN_REASON"):
                self._write(Path(d), fault="silent_degradation")

    def test_less_than_3600_seconds_prevents_evidence_emission(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "SOAK_DURATION_BELOW_3600_SECONDS"):
                self._write(Path(d), duration_seconds=3599)


if __name__ == "__main__":
    unittest.main()
