from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "report_secret_presence.py"


def run_report(**env_overrides: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ.get("PATH", "")}
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_report_accepts_only_boolean_presence_flags_and_preserves_capital_lock() -> None:
    result = run_report(
        DERIV_AUTH_TOKEN_PRESENT="true",
        DERIV_APP_ID_PRESENT="true",
        DERIV_EXPECTED_LOGINID_PRESENT="true",
        DERIV_EXPECTED_CURRENCY_PRESENT="true",
        DERIV_EXPECTED_CURRENCY_SUPPORTED="true",
        DERIV_AUTH_MODE="pat",
        DERIV_ENVIRONMENT="real",
        AURELIA_HOST_PRESENT="true",
        AURELIA_USER_PRESENT="true",
        AURELIA_SSH_KEY_PRESENT="true",
        AURELIA_KNOWN_HOSTS_PRESENT="true",
        AURELIA_ATTESTATION_SIGNING_KEY_PRESENT="true",
        AURELIA_OPERATOR_RESET_SIGNING_KEY_PRESENT="true",
    )

    assert result.returncode == 0
    assert "DERIV_AUTH_TOKEN_PRESENT=true" in result.stdout
    assert "DERIV_APP_ID_PRESENT=true" in result.stdout
    assert "DERIV_EXPECTED_LOGINID_PRESENT=true" in result.stdout
    assert "DERIV_EXPECTED_CURRENCY_PRESENT=true" in result.stdout
    assert "DERIV_EXPECTED_CURRENCY_SUPPORTED=true" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=false" in result.stdout
    assert "DERIV_READ_ONLY_ACCOUNT_SCOPE_AVAILABLE=false" in result.stdout
    assert "DERIV_ENVIRONMENT_VALID=true" in result.stdout
    assert "DERIV_ENVIRONMENT_EFFECTIVE=REAL" in result.stdout
    assert "FINAL_EXECUTION_AUTHORIZATION=false" in result.stdout
    assert "LIVE_EXECUTION=BLOCKED" in result.stdout
    assert "CAPITAL_MOVEMENT_PERMITTED=false" in result.stdout
    assert "AURELIA_HOST_PRESENT=true" in result.stdout
    assert "AURELIA_USER_PRESENT=true" in result.stdout
    assert "AURELIA_SSH_KEY_PRESENT=true" in result.stdout
    assert "AURELIA_KNOWN_HOSTS_PRESENT=true" in result.stdout
    assert "AURELIA_ATTESTATION_SIGNING_KEY_PRESENT=true" in result.stdout
    assert "AURELIA_OPERATOR_RESET_SIGNING_KEY_PRESENT=true" in result.stdout
    assert "AURELIA_OPERATOR_RESET_SIGNING_KEY_LENGTH_VALID=UNVERIFIED" in result.stdout
    assert "AURELIA_DEPLOYMENT_SECRET_STORE_CONFIGURED=false" in result.stdout
    assert "AURELIA_PRODUCTION_PREREQUISITES_CONFIGURED=false" in result.stdout


def test_unknown_auth_mode_is_rejected_without_echoing_input() -> None:
    marker = "private-invalid-auth-mode"
    result = run_report(
        DERIV_AUTH_TOKEN_PRESENT="true",
        DERIV_AUTH_MODE=marker,
    )
    assert result.returncode == 0
    assert marker not in result.stdout
    assert "DERIV_AUTH_MODE_VALID=false" in result.stdout
    assert "DERIV_AUTH_MODE_EFFECTIVE=INVALID" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=false" in result.stdout


def test_missing_presence_flags_default_to_false() -> None:
    result = run_report()
    assert result.returncode == 0
    for name in (
        "DERIV_AUTH_TOKEN",
        "DERIV_APP_ID",
        "DERIV_EXPECTED_LOGINID",
        "DERIV_EXPECTED_CURRENCY",
        "AURELIA_HOST",
        "AURELIA_SSH_KEY",
        "AURELIA_OPERATOR_RESET_SIGNING_KEY",
    ):
        assert f"{name}_PRESENT=false" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=false" in result.stdout
    assert "AURELIA_PRODUCTION_PREREQUISITES_CONFIGURED=false" in result.stdout


def test_unsupported_currency_flag_does_not_configure_account_access() -> None:
    result = run_report(
        DERIV_AUTH_TOKEN_PRESENT="true",
        DERIV_APP_ID_PRESENT="true",
        DERIV_EXPECTED_LOGINID_PRESENT="true",
        DERIV_EXPECTED_CURRENCY_PRESENT="true",
        DERIV_EXPECTED_CURRENCY_SUPPORTED="false",
    )
    assert result.returncode == 0
    assert "DERIV_EXPECTED_CURRENCY_SUPPORTED=false" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=false" in result.stdout
    assert "DERIV_READ_ONLY_ACCOUNT_SCOPE_AVAILABLE=false" in result.stdout


def test_environment_and_boolean_flags_are_normalized() -> None:
    result = run_report(
        DERIV_ENVIRONMENT="invalid-environment",
        DERIV_AUTH_TOKEN_PRESENT="TRUE",
        AURELIA_HOST_PRESENT="yes",
    )
    assert result.returncode == 0
    assert "DERIV_AUTH_TOKEN_PRESENT=true" in result.stdout
    assert "AURELIA_HOST_PRESENT=false" in result.stdout
    assert "DERIV_ENVIRONMENT_VALID=false" in result.stdout
    assert "DERIV_ENVIRONMENT_EFFECTIVE=INVALID" in result.stdout


def test_workflow_passes_boolean_results_not_secret_values() -> None:
    workflow = (ROOT / ".github" / "workflows" / "secret-presence-report.yml").read_text(
        encoding="utf-8"
    )
    assert "workflow_dispatch:" in workflow
    assert "environment: production" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "DERIV_AUTH_TOKEN_PRESENT:" in workflow
    assert "secrets.DERIV_AUTH_TOKEN != ''" in workflow
    assert "secrets.DERIV_PAT != ''" in workflow
    assert "AURELIA_SSH_KEY_PRESENT:" in workflow
    assert "secrets.AURELIA_SSH_KEY != ''" in workflow
    assert "DERIV_AUTH_TOKEN: ${{ secrets.DERIV_AUTH_TOKEN" not in workflow
    assert "AURELIA_SSH_KEY: ${{ secrets.AURELIA_SSH_KEY }}" not in workflow
    assert "secrets.DERIV_AUTH_TOKEN || secrets.DERIV_PAT" not in workflow
    assert "vars.DERIV_AUTH_MODE" in workflow
    assert "vars.DERIV_ENVIRONMENT" in workflow
