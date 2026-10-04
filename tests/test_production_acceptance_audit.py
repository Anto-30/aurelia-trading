from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_production_acceptance_audit_passes():
    result = subprocess.run(
        [sys.executable, "scripts/production_acceptance_audit.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "AURELIA_PRODUCTION_ACCEPTANCE=AUDIT_PASS" in result.stdout
    assert "CAPITAL_MOVEMENT_PERMITTED=false" in result.stdout
    assert "LIVE_EXECUTION=BLOCKED" in result.stdout
