from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
MAIN_REF_GUARD = "github.ref == 'refs/heads/main'"


def job_block(workflow: str, job_name: str) -> str:
    lines = workflow.splitlines()
    marker = f"  {job_name}:"
    try:
        start = lines.index(marker)
    except ValueError as exc:
        raise AssertionError(f"job not found: {job_name}") from exc
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            end = index
            break
    return "\n".join(lines[start:end])


def test_pull_request_assurance_does_not_load_production_credentials() -> None:
    workflow = (WORKFLOWS / "aurelia-assurance.yml").read_text(encoding="utf-8")
    assert "pull_request:" in workflow
    assert "environment: production" not in workflow
    assert "${{ secrets." not in workflow
    assert "DERIV_AUTH_CONFIGURED" not in workflow
    assert "python scripts/verify_deriv_session.py" not in workflow
    assert "python scripts/verify_deriv_transaction_lifecycle.py" not in workflow
    assert "production-environment workflows" in workflow


def test_all_secret_bearing_workflow_dispatch_jobs_are_main_only() -> None:
    cases = {
        "deriv-auth-evidence.yml": ("verify",),
        "deriv-session-verification.yml": ("verify",),
        "deriv-verify-only-lifecycle.yml": ("verify-only",),
        "secret-presence-report.yml": ("report",),
        "aurelia-free-runtime.yml": (
            "authenticated-deriv-evidence",
            "deriv-lifecycle-verify-only",
            "whatsapp-alert-smoke",
        ),
        "self-hosted-runtime-deploy.yml": ("deploy",),
    }
    for filename, jobs in cases.items():
        workflow = (WORKFLOWS / filename).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in workflow, filename
        for job in jobs:
            block = job_block(workflow, job)
            assert MAIN_REF_GUARD in block, f"{filename}:{job} must be main-only"


def test_secret_bearing_protected_jobs_keep_the_production_environment() -> None:
    cases = {
        "deriv-auth-evidence.yml": ("verify",),
        "deriv-session-verification.yml": ("verify",),
        "deriv-verify-only-lifecycle.yml": ("verify-only",),
        "secret-presence-report.yml": ("report",),
        "aurelia-free-runtime.yml": (
            "authenticated-deriv-evidence",
            "deriv-lifecycle-verify-only",
        ),
        "self-hosted-runtime-deploy.yml": ("deploy",),
    }
    for filename, jobs in cases.items():
        workflow = (WORKFLOWS / filename).read_text(encoding="utf-8")
        for job in jobs:
            block = job_block(workflow, job)
            assert "environment: production" in block or "environment:\n      name: production" in block, (
                filename,
                job,
            )


def test_live_execution_remains_blocked_in_workflow_contract() -> None:
    lock = (ROOT / "config" / "LIVE_LOCK.yaml").read_text(encoding="utf-8")
    assert "FINAL_EXECUTION_AUTHORIZATION: false" in lock
    assert "LIVE_EXECUTION: BLOCKED" in lock
    assert "capital_plane_mode: VERIFY_ONLY" in lock
