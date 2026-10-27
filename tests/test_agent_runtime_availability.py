from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.agent_runtime_availability import build_availability_report


def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "providers.json"
    path.write_text(json.dumps({
        "schema": "aurelia.agent_runtime_provider_matrix.v1",
        "runtimes": [{
            "name": "TestWorker",
            "worker_agent": "TestWorker",
            "command_env": "AURELIA_AGENT_TESTWORKER_COMMAND",
            "healthcheck_env": "AURELIA_AGENT_TESTWORKER_HEALTHCHECK_COMMAND",
            "credential_env_any": ["TEST_PROVIDER_API_KEY"],
            "executable_candidates": ["test-provider"],
            "skills": ["security-review"],
            "plugins": [],
        }],
    }), encoding="utf-8")
    return path


def write_lease(path: Path, *, origin: str, expires_at: str) -> None:
    path.write_text(json.dumps({
        "version": 1,
        "leases": {
            "TestWorker": {
                "worker_id": "TestWorker:unit-test",
                "origin": origin,
                "heartbeat_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at,
            }
        },
    }), encoding="utf-8")


def test_inventory_without_process_or_key_is_not_reported_as_connected(tmp_path):
    report = build_availability_report(
        config_file(tmp_path),
        env={},
        which=lambda _: None,
        lease_path=tmp_path / "missing-leases.json",
    )
    item = report["runtimes"][0]
    assert item["status"] == "RUNTIME_AND_CREDENTIAL_MISSING"
    assert item["worker_lease_active"] is False
    assert item["provider_session"] == "UNKNOWN"
    assert item["plugin_connection_status"] == "NOT_BRIDGED_TO_LOCAL_WORKER"
    assert report["summary"]["active_worker_leases"] == 0


def test_worker_command_without_healthcheck_is_blocked_even_if_cli_exists(tmp_path):
    report = build_availability_report(
        config_file(tmp_path),
        env={"AURELIA_AGENT_TESTWORKER_COMMAND": "test-provider --serve"},
        which=lambda name: "/usr/bin/test-provider" if name == "test-provider" else None,
        lease_path=tmp_path / "missing-leases.json",
    )
    item = report["runtimes"][0]
    assert item["status"] == "BLOCKED_HEALTHCHECK_MISSING"
    assert item["executable_found"] is True
    assert item["worker_command_configured"] is True
    assert item["healthcheck_command_configured"] is False


def test_only_unexpired_worker_origin_lease_counts_as_active(tmp_path):
    leases = tmp_path / "leases.json"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    write_lease(leases, origin="TEST", expires_at=expires)
    report = build_availability_report(
        config_file(tmp_path),
        env={
            "AURELIA_AGENT_TESTWORKER_COMMAND": "test-provider --serve",
            "AURELIA_AGENT_TESTWORKER_HEALTHCHECK_COMMAND": "test-provider check",
        },
        which=lambda _: "/usr/bin/test-provider",
        lease_path=leases,
    )
    item = report["runtimes"][0]
    assert item["worker_lease_active"] is False
    assert item["lease_block_reason"] == "LEASE_ORIGIN_NOT_WORKER"


def test_active_worker_and_healthcheck_are_distinguished_from_auth_proof(tmp_path):
    leases = tmp_path / "leases.json"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    write_lease(leases, origin="WORKER", expires_at=expires)
    secret_value = "never-report-this-secret"
    report = build_availability_report(
        config_file(tmp_path),
        env={
            "AURELIA_AGENT_TESTWORKER_COMMAND": "test-provider --serve",
            "AURELIA_AGENT_TESTWORKER_HEALTHCHECK_COMMAND": "test-provider check",
            "TEST_PROVIDER_API_KEY": secret_value,
        },
        which=lambda _: "/usr/bin/test-provider",
        lease_path=leases,
    )
    item = report["runtimes"][0]
    assert item["status"] == "WORKER_HEALTHCHECK_LEASE_ACTIVE"
    assert item["worker_lease_active"] is True
    assert item["provider_session"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert item["credential_env_present"] == ["TEST_PROVIDER_API_KEY"]
    assert secret_value not in json.dumps(report)


def test_expired_lease_never_counts_as_active(tmp_path):
    leases = tmp_path / "leases.json"
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    write_lease(leases, origin="WORKER", expires_at=expired)
    report = build_availability_report(
        config_file(tmp_path),
        env={
            "AURELIA_AGENT_TESTWORKER_COMMAND": "test-provider --serve",
            "AURELIA_AGENT_TESTWORKER_HEALTHCHECK_COMMAND": "test-provider check",
        },
        which=lambda _: "/usr/bin/test-provider",
        lease_path=leases,
    )
    item = report["runtimes"][0]
    assert item["worker_lease_active"] is False
    assert item["lease_block_reason"] == "LEASE_EXPIRED"
