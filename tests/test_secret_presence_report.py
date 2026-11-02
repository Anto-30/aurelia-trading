from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "report_secret_presence.py"


def run_report(**env_overrides: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for name in (
        "DERIV_OAUTH_ACCESS_TOKEN",
        "DERIV_OAUTH_REFRESH_TOKEN",
        "DERIV_PAT",
        "DERIV_AUTH_TOKEN",
        "DERIV_REFRESH_TOKEN",
        "ACCOUNT_DERIV_AUTH_MODE",
    ):
        env.pop(name, None)
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_report_detects_equal_oauth_and_pat_without_echoing_values() -> None:
    marker = "SAME_SECRET_MUST_NOT_APPEAR"
    result = run_report(
        ACCOUNT_DERIV_AUTH_MODE="oauth",
        DERIV_OAUTH_ACCESS_TOKEN=marker,
        DERIV_PAT=marker,
        AURELIA_HOST="host.example.invalid",
        AURELIA_USER="runtime-user",
        AURELIA_SSH_KEY="PRIVATE_KEY_SENTINEL_DO_NOT_PRINT",
        AURELIA_KNOWN_HOSTS="HOST_KEY_SENTINEL_DO_NOT_PRINT",
        AURELIA_ATTESTATION_SIGNING_KEY="SIGNING_KEY_SENTINEL_DO_NOT_PRINT",
        AURELIA_OPERATOR_RESET_SIGNING_KEY="OPERATOR_RESET_KEY_SENTINEL_DO_NOT_PRINT_32_CHARS",
    )

    assert result.returncode == 0
    assert marker not in result.stdout
    assert "DERIV_OAUTH_ACCESS_TOKEN_PRESENT=true" in result.stdout
    assert "DERIV_PAT_PRESENT=true" in result.stdout
    assert "DERIV_OAUTH_PAT_IDENTICAL=true" in result.stdout
    assert "DERIV_CREDENTIALS_ISOLATED_IN_PROCESS=false" in result.stdout
    assert "DERIV_READ_ONLY_SCOPE_SUPPORTED=false" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=false" in result.stdout
    assert "AURELIA_DEPLOYMENT_SECRET_STORE_CONFIGURED=true" in result.stdout
    assert "AURELIA_PRODUCTION_PREREQUISITES_CONFIGURED=false" in result.stdout
    assert "FINAL_EXECUTION_AUTHORIZATION=false" in result.stdout
    assert "LIVE_EXECUTION=BLOCKED" in result.stdout
    assert "CAPITAL_MOVEMENT_PERMITTED=false" in result.stdout
    assert "PRIVATE_KEY_SENTINEL_DO_NOT_PRINT" not in result.stdout
    assert "HOST_KEY_SENTINEL_DO_NOT_PRINT" not in result.stdout
    assert "SIGNING_KEY_SENTINEL_DO_NOT_PRINT" not in result.stdout


def test_distinct_oauth_token_without_pat_isolated_but_not_read_only_qualified() -> None:
    marker = "OAUTH_TOKEN_SENTINEL"
    result = run_report(
        ACCOUNT_DERIV_AUTH_MODE="oauth",
        DERIV_OAUTH_ACCESS_TOKEN=marker,
    )
    assert result.returncode == 0
    assert "DERIV_OAUTH_ACCESS_TOKEN_PRESENT=true" in result.stdout
    assert "DERIV_PAT_PRESENT=false" in result.stdout
    assert "DERIV_OAUTH_PAT_IDENTICAL=false" in result.stdout
    assert "DERIV_CREDENTIALS_ISOLATED_IN_PROCESS=true" in result.stdout
    assert "DERIV_READ_ONLY_SCOPE_SUPPORTED=false" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=false" in result.stdout
    assert marker not in result.stdout


def test_generic_token_fallback_is_detected_and_not_echoed() -> None:
    marker = "GENERIC_TOKEN_SENTINEL"
    result = run_report(DERIV_AUTH_TOKEN=marker)
    assert result.returncode == 0
    assert "DERIV_AUTH_TOKEN_PRESENT=true" in result.stdout
    assert "DERIV_CREDENTIALS_ISOLATED_IN_PROCESS=false" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=false" in result.stdout
    assert marker not in result.stdout


def test_invalid_account_auth_mode_is_rejected() -> None:
    result = run_report(ACCOUNT_DERIV_AUTH_MODE="pat")
    assert result.returncode == 0
    assert "ACCOUNT_DERIV_AUTH_MODE_VALID=false" in result.stdout
    assert "DERIV_AUTH_CONFIGURED=false" in result.stdout


def test_missing_deployment_secrets_remain_unconfigured() -> None:
    result = run_report(
        AURELIA_HOST="",
        AURELIA_USER="",
        AURELIA_SSH_KEY="",
        AURELIA_KNOWN_HOSTS="",
        AURELIA_ATTESTATION_SIGNING_KEY="",
        AURELIA_OPERATOR_RESET_SIGNING_KEY="",
    )
    assert result.returncode == 0
    assert "AURELIA_DEPLOYMENT_SECRET_STORE_CONFIGURED=false" in result.stdout
    assert "AURELIA_OPERATOR_RESET_SIGNING_KEY_LENGTH_VALID=false" in result.stdout
    assert "AURELIA_PRODUCTION_PREREQUISITES_CONFIGURED=false" in result.stdout


def test_secret_presence_workflow_does_not_map_deriv_credentials() -> None:
    workflow = (ROOT / ".github" / "workflows" / "secret-presence-report.yml").read_text(
        encoding="utf-8"
    )
    for marker in (
        "secrets.DERIV_AUTH_TOKEN",
        "secrets.DERIV_PAT",
        "secrets.DERIV_OAUTH_ACCESS_TOKEN",
        "secrets.DERIV_OAUTH_READ_ONLY_TOKEN",
        "DERIV_AUTH_TOKEN:",
        "DERIV_PAT:",
    ):
        assert marker not in workflow
    assert 'ACCOUNT_DERIV_AUTH_MODE: "oauth"' in workflow


def test_secret_presence_workflow_binds_operator_reset_key_from_production_environment() -> None:
    workflow = (ROOT / ".github" / "workflows" / "secret-presence-report.yml").read_text(
        encoding="utf-8"
    )
    assert "AURELIA_OPERATOR_RESET_SIGNING_KEY: ${{ secrets.AURELIA_OPERATOR_RESET_SIGNING_KEY }}" in workflow


def test_short_operator_reset_signing_key_blocks_deployment_prerequisites() -> None:
    result = run_report(
        AURELIA_HOST="host.example.invalid",
        AURELIA_USER="runtime-user",
        AURELIA_SSH_KEY="PRIVATE_KEY_SENTINEL_DO_NOT_PRINT",
        AURELIA_KNOWN_HOSTS="HOST_KEY_SENTINEL_DO_NOT_PRINT",
        AURELIA_ATTESTATION_SIGNING_KEY="SIGNING_KEY_SENTINEL_DO_NOT_PRINT",
        AURELIA_OPERATOR_RESET_SIGNING_KEY="short-key",
    )
    assert result.returncode == 0
    assert "AURELIA_OPERATOR_RESET_SIGNING_KEY_PRESENT=true" in result.stdout
    assert "AURELIA_OPERATOR_RESET_SIGNING_KEY_LENGTH_VALID=false" in result.stdout
    assert "AURELIA_DEPLOYMENT_SECRET_STORE_CONFIGURED=false" in result.stdout


if __name__ == "__main__":
    pass
