from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "report_secret_presence.py"


def run_report(**env_overrides: str) -> subprocess.CompletedProcess[str]:
    import os

    env = os.environ.copy()
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_report_is_boolean_only_and_preserves_capital_lock() -> None:
    fake_token = "FAKE_DERIV_TOKEN_SHOULD_NEVER_APPEAR"
    fake_login = "CR123456_SHOULD_NEVER_APPEAR"

    result = run_report(
        DERIV_AUTH_TOKEN=fake_token,
        DERIV_APP_ID="12345",
        DERIV_EXPECTED_LOGINID=fake_login,
        DERIV_EXPECTED_CURRENCY="USD",
        DERIV_AUTH_MODE="pat",
    )

    assert result.returncode == 0
    assert fake_token not in result.stdout
    assert fake_login not in result.stdout
    assert "DERIV_AUTH_TOKEN_PRESENT=true" in result.stdout
    assert "DERIV_APP_ID_PRESENT=true" in result.stdout
    assert "DERIV_EXPECTED_LOGINID_PRESENT=true" in result.stdout
    assert "DERIV_EXPECTED_CURRENCY_PRESENT=true" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=true" in result.stdout
    assert "FINAL_EXECUTION_AUTHORIZATION=false" in result.stdout
    assert "LIVE_EXECUTION=BLOCKED" in result.stdout
    assert "CAPITAL_MOVEMENT_PERMITTED=false" in result.stdout


def test_invalid_auth_mode_is_rejected_and_not_echoed() -> None:
    invalid_mode = "deriv_auth_token"
    result = run_report(
        DERIV_AUTH_TOKEN="FAKE_TOKEN",
        DERIV_APP_ID="12345",
        DERIV_EXPECTED_LOGINID="CRTEST",
        DERIV_EXPECTED_CURRENCY="USD",
        DERIV_AUTH_MODE=invalid_mode,
    )

    assert result.returncode == 0
    assert invalid_mode not in result.stdout
    assert "DERIV_AUTH_MODE_VALID=false" in result.stdout
    assert "DERIV_AUTH_MODE_EFFECTIVE=INVALID" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=false" in result.stdout
    assert "FINAL_EXECUTION_AUTHORIZATION=false" in result.stdout
    assert "LIVE_EXECUTION=BLOCKED" in result.stdout


def test_missing_bindings_report_false_without_defaults() -> None:
    result = run_report(
        DERIV_AUTH_TOKEN="",
        DERIV_APP_ID="",
        DERIV_EXPECTED_LOGINID="",
        DERIV_EXPECTED_CURRENCY="",
        DERIV_AUTH_MODE="pat",
    )

    assert result.returncode == 0
    assert "DERIV_AUTH_TOKEN_PRESENT=false" in result.stdout
    assert "DERIV_APP_ID_PRESENT=false" in result.stdout
    assert "DERIV_EXPECTED_LOGINID_PRESENT=false" in result.stdout
    assert "DERIV_EXPECTED_CURRENCY_PRESENT=false" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=false" in result.stdout
