from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deriv-auth-evidence.yml"


def test_account_evidence_workflow_is_blocked_without_credentials() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "environment: production" not in workflow
    assert "${{ secrets." not in workflow
    assert "DERIV_AUTH_TOKEN" not in workflow
    assert "DERIV_PAT" not in workflow
    assert "verify_deriv_session.py" not in workflow
    assert "DERIV_ORDERS_SUBMITTED=0" in workflow
    assert "LIVE_EXECUTION=BLOCKED" in workflow
