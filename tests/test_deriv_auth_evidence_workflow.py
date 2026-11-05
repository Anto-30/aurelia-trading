from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ROOT / ".github" / "workflows" / "aurelia-assurance.yml",
    ROOT / ".github" / "workflows" / "deriv-auth-evidence.yml",
    ROOT / ".github" / "workflows" / "deriv-verify-only-lifecycle.yml",
)
SAFE_AUTH_MODE_BINDING = (
    "${{ vars.DERIV_AUTH_MODE == 'oauth' && 'oauth' "
    "|| (vars.DERIV_AUTH_MODE == 'pat' && 'pat' || 'invalid') }}"
)


def test_all_deriv_auth_workflows_sanitize_auth_mode_before_runner_exposure() -> None:
    for path in WORKFLOWS:
        workflow = path.read_text(encoding="utf-8")
        assert f"DERIV_AUTH_MODE: {SAFE_AUTH_MODE_BINDING}" in workflow, path.name
        assert workflow.count("DERIV_AUTH_MODE:") == 1, path.name
        assert "secrets.DERIV_AUTH_MODE" not in workflow, path.name
        assert "vars.DERIV_AUTH_MODE || 'pat'" not in workflow, path.name


def test_scheduled_deriv_verifier_loads_production_environment_secrets() -> None:
    workflow = WORKFLOWS[1].read_text(encoding="utf-8")

    assert "environment: production" in workflow
    assert "DERIV_AUTH_TOKEN: ${{ secrets.DERIV_AUTH_TOKEN || secrets.DERIV_PAT }}" in workflow
    assert "DERIV_EXPECTED_LOGINID: ${{ secrets.DERIV_EXPECTED_LOGINID || secrets.DERIV_AUTHORIZED_ACCOUNT_ID }}" in workflow
    assert "DERIV_EXPECTED_CURRENCY: ${{ secrets.DERIV_EXPECTED_CURRENCY }}" in workflow
    assert "DERIV_AUTH_SESSION=BLOCKED_EXPECTED_CURRENCY_MISSING" in workflow
    assert "DERIV_AUTH_SESSION=BLOCKED_UNSUPPORTED_CURRENCY" in workflow
    assert "secrets.DERIV_EXPECTED_CURRENCY || 'USD'" not in workflow


def test_scheduled_workflow_generates_read_only_broker_account_evidence() -> None:
    workflow = WORKFLOWS[1].read_text(encoding="utf-8")
    assert "python scripts/verify_deriv_broker_evidence.py" in workflow
    assert "artifacts/deriv_broker_account_evidence.json" in workflow


def test_scheduled_deriv_verifier_keeps_capital_authority_blocked() -> None:
    workflow = WORKFLOWS[1].read_text(encoding="utf-8")

    assert 'FINAL_EXECUTION_AUTHORIZATION: "false"' in workflow
    assert 'LIVE_EXECUTION: "BLOCKED"' in workflow
    assert 'echo "DERIV_ORDERS_SUBMITTED=0"' in workflow
