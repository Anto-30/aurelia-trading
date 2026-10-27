from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from scripts.deploy.validate_agent_provider_secrets import validate_provider_secret_file


def write_secure(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)
    return path


def test_missing_provider_secret_file_is_optional_and_does_not_claim_connected(tmp_path):
    report = validate_provider_secret_file(tmp_path / "absent.env")
    assert report["status"] == "ABSENT"
    assert report["credential_count"] == 0
    assert report["credential_names"] == []
    assert report["secret_values_emitted"] is False
    assert report["broker_credentials_allowed"] is False


def test_accepts_allowlisted_provider_keys_without_echoing_values(tmp_path):
    secret = "provider-key-marker-do-not-print-7852"
    path = write_secure(
        tmp_path / "agent-provider-secrets.env",
        f"ANTHROPIC_API_KEY={secret}\nDEEPSEEK_API_KEY=deepseek-marker-9863\n",
    )
    report = validate_provider_secret_file(path)
    rendered = json.dumps(report)
    assert report["status"] == "VALID"
    assert report["credential_count"] == 2
    assert report["credential_names"] == ["ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"]
    assert secret not in rendered
    assert "deepseek-marker-9863" not in rendered


@pytest.mark.parametrize(
    ("line", "error"),
    [
        ("DERIV_AUTH_TOKEN=broker-secret-value", "AGENT_PROVIDER_SECRET_NAME_NOT_ALLOWED:DERIV_AUTH_TOKEN"),
        ("GITHUB_TOKEN=github-secret-value", "AGENT_PROVIDER_SECRET_NAME_NOT_ALLOWED:GITHUB_TOKEN"),
        ("AURELIA_AGENT_CLAUDECODE_COMMAND=/bin/sh -c danger", "AGENT_PROVIDER_SECRET_NAME_NOT_ALLOWED:AURELIA_AGENT_CLAUDECODE_COMMAND"),
        ("ANTHROPIC_API_KEY=", "AGENT_PROVIDER_SECRET_VALUE_INVALID:ANTHROPIC_API_KEY"),
        ("ANTHROPIC_API_KEY= contains-whitespace", "AGENT_PROVIDER_SECRET_VALUE_INVALID:ANTHROPIC_API_KEY"),
    ],
)
def test_rejects_broker_tokens_arbitrary_commands_and_invalid_values(tmp_path, line, error):
    path = write_secure(tmp_path / "agent-provider-secrets.env", line + "\n")
    with pytest.raises(ValueError, match=error.replace(":", r"\:")):
        validate_provider_secret_file(path)


def test_rejects_duplicate_provider_keys(tmp_path):
    path = write_secure(
        tmp_path / "agent-provider-secrets.env",
        "ANTHROPIC_API_KEY=first-marker\nANTHROPIC_API_KEY=second-marker\n",
    )
    with pytest.raises(ValueError, match="AGENT_PROVIDER_SECRET_NAME_DUPLICATE"):
        validate_provider_secret_file(path)


def test_rejects_insecure_file_permissions(tmp_path):
    path = tmp_path / "agent-provider-secrets.env"
    path.write_text("ANTHROPIC_API_KEY=marker\n", encoding="utf-8")
    path.chmod(0o644)
    with pytest.raises(ValueError, match="AGENT_PROVIDER_SECRET_FILE_PERMISSIONS_MUST_BE_0600"):
        validate_provider_secret_file(path)



def test_rejects_read_only_mode_when_deployment_contract_requires_exact_0600(tmp_path):
    path = tmp_path / "agent-provider-secrets.env"
    path.write_text("ANTHROPIC_API_KEY=marker\n", encoding="utf-8")
    path.chmod(0o400)
    with pytest.raises(ValueError, match="AGENT_PROVIDER_SECRET_FILE_PERMISSIONS_MUST_BE_0600"):
        validate_provider_secret_file(path)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unsupported")
def test_rejects_symlinked_secret_file(tmp_path):
    target = write_secure(tmp_path / "real.env", "ANTHROPIC_API_KEY=marker\n")
    link = tmp_path / "linked.env"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="AGENT_PROVIDER_SECRET_FILE_MUST_NOT_BE_SYMLINK"):
        validate_provider_secret_file(link)
