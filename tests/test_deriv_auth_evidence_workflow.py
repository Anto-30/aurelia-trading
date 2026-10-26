from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deriv-auth-evidence.yml"


def test_manual_deriv_verifier_loads_production_environment_secrets_on_main() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "environment: production" in workflow
    assert "DERIV_AUTH_TOKEN: ${{ secrets.DERIV_AUTH_TOKEN || secrets.DERIV_PAT }}" in workflow
    assert "DERIV_EXPECTED_LOGINID: ${{ secrets.DERIV_EXPECTED_LOGINID || secrets.DERIV_AUTHORIZED_ACCOUNT_ID }}" in workflow
    assert "DERIV_AUTH_MODE: ${{ vars.DERIV_AUTH_MODE || 'pat' }}" in workflow
    assert "secrets.DERIV_AUTH_MODE" not in workflow
    assert "DERIV_EXPECTED_CURRENCY: ${{ secrets.DERIV_EXPECTED_CURRENCY }}" in workflow
    assert "DERIV_AUTH_SESSION=BLOCKED_EXPECTED_CURRENCY_MISSING" in workflow
    assert "DERIV_AUTH_SESSION=BLOCKED_UNSUPPORTED_CURRENCY" in workflow
    assert "secrets.DERIV_EXPECTED_CURRENCY || 'USD'" not in workflow


def test_manual_workflow_generates_read_only_broker_account_evidence() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "python scripts/verify_deriv_broker_evidence.py" in workflow
    assert "artifacts/deriv_broker_account_evidence.json" in workflow


def test_manual_deriv_verifier_keeps_capital_authority_blocked() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'FINAL_EXECUTION_AUTHORIZATION: "false"' in workflow
    assert 'LIVE_EXECUTION: "BLOCKED"' in workflow
    assert 'echo "DERIV_ORDERS_SUBMITTED=0"' in workflow
