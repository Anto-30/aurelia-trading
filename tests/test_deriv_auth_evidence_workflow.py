from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deriv-auth-evidence.yml"


def test_scheduled_workflow_has_no_account_or_pat_secret_mappings() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    forbidden = (
        "secrets.DERIV_AUTH_TOKEN",
        "secrets.DERIV_PAT",
        "secrets.DERIV_OAUTH_ACCESS_TOKEN",
        "secrets.DERIV_OAUTH_READ_ONLY_TOKEN",
        "DERIV_" + "AUTH_TOKEN" + ":",
        "DERIV_" + "PAT" + ":",
    )
    for marker in forbidden:
        assert marker not in workflow
    assert "environment: production" not in workflow
    assert 'ACCOUNT_DERIV_AUTH_MODE: "oauth"' in workflow


def test_workflow_verifies_public_market_data_not_authenticated_account_access() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/verify_deriv_public_transport.py" in workflow
    assert "R_100 M1 historical data" in workflow
    assert "scripts/verify_deriv_session.py" not in workflow
    assert "scripts/verify_deriv_broker_evidence.py" not in workflow
    assert "scripts/verify_deriv_transaction_lifecycle.py" not in workflow


def test_free_runtime_workflow_has_no_deriv_account_secret_mappings() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "aurelia-free-runtime.yml"
    ).read_text(encoding="utf-8")
    forbidden = (
        "secrets.DERIV_AUTH_TOKEN",
        "secrets.DERIV_PAT",
        "secrets.DERIV_OAUTH_ACCESS_TOKEN",
        "DERIV_AUTH_TOKEN:",
        "DERIV_PAT:",
        "environment: production",
    )
    for marker in forbidden:
        assert marker not in workflow
    assert "scripts/verify_deriv_public_transport.py" in workflow
    assert "account-evidence-status:" in workflow
    assert "scripts/verify_deriv_session.py" in workflow
    assert "scripts/verify_deriv_broker_evidence.py" in workflow
    assert "scripts/verify_deriv_transaction_lifecycle.py" in workflow
    assert 'ACCOUNT_DERIV_AUTH_MODE: "oauth"' in workflow


def test_account_scope_gate_workflow_has_no_trade_credential_mappings() -> None:
    for name in (
        "deriv-session-verification.yml",
        "deriv-verify-only-lifecycle.yml",
    ):
        workflow = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "secrets.DERIV_AUTH_TOKEN" not in workflow
        assert "secrets.DERIV_PAT" not in workflow
        assert "secrets.DERIV_OAUTH_ACCESS_TOKEN" not in workflow
        assert "environment: production" not in workflow
