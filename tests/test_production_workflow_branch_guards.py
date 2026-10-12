from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def job_body(workflow_text: str, job_name: str) -> str:
    lines = workflow_text.splitlines()
    marker = f"  {job_name}:"
    try:
        start = lines.index(marker)
    except ValueError as exc:
        raise AssertionError(f"missing job {job_name}") from exc
    body = []
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            break
        body.append(line)
    return "\n".join(body)


def test_secret_bearing_manual_workflows_are_main_branch_only() -> None:
    guarded_jobs = {
        "aurelia-free-runtime.yml": (
            "authenticated-deriv-evidence",
            "deriv-lifecycle-verify-only",
            "whatsapp-alert-smoke",
        ),
        "deriv-auth-evidence.yml": ("verify",),
        "deriv-session-verification.yml": ("verify",),
        "secret-presence-report.yml": ("report",),
        "self-hosted-runtime-deploy.yml": ("deploy",),
    }

    for workflow_name, jobs in guarded_jobs.items():
        workflow = (WORKFLOWS / workflow_name).read_text(encoding="utf-8")
        for name in jobs:
            body = job_body(workflow, name)
            assert "if: github.ref == 'refs/heads/main'" in body, (
                f"{workflow_name}:{name} can access production credentials "
                "without a job-level main-branch guard"
            )


def test_verify_only_lifecycle_dispatch_is_main_branch_only() -> None:
    workflow = (WORKFLOWS / "deriv-verify-only-lifecycle.yml").read_text(encoding="utf-8")
    body = job_body(workflow, "verify-only")
    assert "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'" in body


def test_assurance_only_uses_production_environment_on_main_push() -> None:
    workflow = (WORKFLOWS / "aurelia-assurance.yml").read_text(encoding="utf-8")
    assert "environment: ${{ github.event_name == 'push' && github.ref == 'refs/heads/main' && 'production' || 'ci' }}" in workflow
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/main' && env.DERIV_AUTH_CONFIGURED == 'true'" in workflow
