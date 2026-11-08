from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deriv-auth-evidence.yml"


def test_authenticated_account_evidence_is_manual_main_only_no_order() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "environment: production" in workflow
    assert "DERIV_AUTH_TOKEN" + ":" in workflow
    assert "secrets.DERIV_AUTH_TOKEN || secrets.DERIV_PAT" in workflow
    assert 'DERIV_PAT: ""' in workflow
    assert "secrets.DERIV_APP_ID || vars.DERIV_APP_ID" in workflow
    assert "vars.DERIV_EXPECTED_LOGINID" in workflow
    assert "vars.DERIV_AUTHORIZED_ACCOUNT_ID" in workflow
    assert "vars.DERIV_EXPECTED_CURRENCY" in workflow
    assert "run: python scripts/verify_deriv_session.py" in workflow
    assert "LIVE_EXECUTION: BLOCKED" in workflow
    assert 'FINAL_EXECUTION_AUTHORIZATION: "false"' in workflow
    assert "buy:" not in workflow.lower()
    assert "sell:" not in workflow.lower()
    assert "pull_request:" not in workflow
    assert "schedule:" not in workflow
