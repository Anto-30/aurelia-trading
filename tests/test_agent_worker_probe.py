from __future__ import annotations

import os

import pytest

from scripts.agent_worker_probe import run_worker_probe


@pytest.mark.asyncio
async def test_unconfigured_roster_reports_blocked_not_active_and_preserves_environment(monkeypatch):
    for key in list(os.environ):
        if key.startswith("AURELIA_AGENT_") and (
            key.endswith("_COMMAND") or key.endswith("_HEALTHCHECK_COMMAND")
        ):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "this-marker-must-not-appear-in-reports")
    before = dict(os.environ)
    report = await run_worker_probe(env=before, timeout_seconds=1.0)
    assert report["status"] == "PASS"
    assert report["active_worker_count"] == 0
    assert report["runtime_count"] == 9
    assert all(row["status"] == "BLOCKED_CONFIG" for row in report["runtimes"])
    assert "this-marker-must-not-appear-in-reports" not in str(report)
    assert dict(os.environ) == before


@pytest.mark.asyncio
async def test_strict_probe_fails_when_registered_worker_is_not_active(monkeypatch):
    for key in list(os.environ):
        if key.startswith("AURELIA_AGENT_") and (
            key.endswith("_COMMAND") or key.endswith("_HEALTHCHECK_COMMAND")
        ):
            monkeypatch.delenv(key, raising=False)
    report = await run_worker_probe(env=dict(os.environ), require_active=True, timeout_seconds=1.0)
    assert report["status"] == "FAIL"
    assert report["active_worker_count"] == 0
    assert all(any(row["name"] in failure for failure in report["failures"]) for row in report["runtimes"])
