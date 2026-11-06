from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "report_secret_presence.py"


def run_report(**env_overrides: str) -> subprocess.CompletedProcess[str]:
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


def test_report_does_not_inspect_or_echo_deriv_credentials() -> None:
    marker = "DERIV_SECRET_SENTINEL_MUST_NOT_BE_READ"
    result = run_report(
        ACCOUNT_DERIV_AUTH_MODE="oauth",
        DERIV_OAUTH_ACCESS_TOKEN=marker,
        DERIV_PAT=marker,
        DERIV_AUTH_TOKEN=marker,
    )
    assert result.returncode == 0
    assert marker not in result.stdout
    assert "DERIV_ACCOUNT_EVIDENCE=BLOCKED" in result.stdout
    assert "DERIV_ACCOUNT_BLOCK_REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE" in result.stdout
    assert "DERIV_ACCOUNT_CREDENTIALS=NOT_INSPECTED" in result.stdout
    assert "DERIV_READ_ONLY_SCOPE_SUPPORTED=false" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=false" in result.stdout


def test_report_does_not_inspect_or_echo_deployment_secrets() -> None:
    marker = "DEPLOYMENT_SECRET_SENTINEL_MUST_NOT_BE_READ"
    result = run_report(
        AURELIA_HOST=marker,
        AURELIA_SSH_KEY=marker,
        AURELIA_KNOWN_HOSTS=marker,
        AURELIA_ATTESTATION_SIGNING_KEY=marker,
        AURELIA_OPERATOR_RESET_SIGNING_KEY=marker,
    )
    assert result.returncode == 0
    assert marker not in result.stdout
    assert "AURELIA_HOST_PRESENCE=NOT_INSPECTED" in result.stdout
    assert "AURELIA_SSH_KEY_PRESENCE=NOT_INSPECTED" in result.stdout
    assert "AURELIA_DEPLOYMENT_SECRET_STORE_CONFIGURED=UNKNOWN" in result.stdout
    assert "AURELIA_PRODUCTION_PREREQUISITES_CONFIGURED=UNKNOWN" in result.stdout


def test_report_is_independent_of_environment_contents() -> None:
    without_values = run_report()
    with_values = run_report(
        DERIV_PAT="SENTINEL_A",
        AURELIA_SSH_KEY="SENTINEL_B",
        AURELIA_OPERATOR_RESET_SIGNING_KEY="SENTINEL_C",
    )
    assert without_values.returncode == 0
    assert with_values.returncode == 0
    assert without_values.stdout == with_values.stdout


def test_report_preserves_capital_lock() -> None:
    result = run_report()
    assert result.returncode == 0
    assert "FINAL_EXECUTION_AUTHORIZATION=false" in result.stdout
    assert "LIVE_EXECUTION=BLOCKED" in result.stdout
    assert "CAPITAL_MOVEMENT_PERMITTED=false" in result.stdout


def test_secret_presence_workflow_maps_no_secrets_or_production_environment() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "secret-presence-report.yml"
    ).read_text(encoding="utf-8")
    assert "environment: production" not in workflow
    assert "${{ secrets." not in workflow
    assert "secrets." not in workflow
    assert 'ACCOUNT_DERIV_AUTH_MODE: "oauth"' in workflow
    assert 'FINAL_EXECUTION_AUTHORIZATION: "false"' in workflow
    assert 'LIVE_EXECUTION: "BLOCKED"' in workflow


if __name__ == "__main__":
    pass
