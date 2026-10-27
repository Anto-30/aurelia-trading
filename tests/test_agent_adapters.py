from __future__ import annotations

import json
import subprocess
import os
import sys
from pathlib import Path

import pytest

from runtime.agent_adapters import claude_code, common, deepseek_harness, hermes_agent


def request():
    return {
        "schema": "aurelia.agent_task_request.v1",
        "protocol": "STDIO_JSON_TASK_V1",
        "agent": "AdapterTest",
        "task": {
            "task_id": "task-123",
            "task_type": "RESEARCH",
            "payload": {"instruction": "Summarize the evidence"},
        },
        "policy": {
            "capital_authority": False,
            "live_order_submission": False,
            "live_lock_mutation": False,
            "broker_credentials_are_not_provided": True,
            "response_schema": "aurelia.agent_task_response.v1",
        },
    }


def fake_completed(args, returncode=0, stdout="safe-response"):
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr="secret stderr must not be returned")


def test_request_rejects_missing_capital_boundary():
    bad = request()
    bad["policy"]["live_order_submission"] = True
    with pytest.raises(ValueError, match="WORKER_LIVE_ORDER_BOUNDARY_MISSING"):
        common.validate_request_object(bad)  # helper must validate direct test objects too


def test_rendered_prompt_is_bounded_and_contains_no_tool_authority():
    text = common.render_prompt(request(), agent_name="Test", provider_name="TestProvider")
    assert "cannot authorize, place, modify, or cancel broker orders" in text
    assert "Do not attempt writes, order changes, account actions" in text
    assert "Claude Code and Hermes have tools disabled" in text
    assert "DeepSeek Harness uses a read-only permission preset" in text
    assert "Task payload JSON" in text
    with pytest.raises(ValueError, match="WORKER_TASK_PAYLOAD_TOO_LARGE"):
        huge = request()
        huge["task"]["payload"] = {"x": "a" * 40000}
        common.render_prompt(huge, agent_name="Test", provider_name="TestProvider")


def test_claude_adapter_disables_every_tool_and_mcp(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-secret")
    monkeypatch.setenv("AURELIA_CLAUDE_CLI", "/usr/bin/claude")
    captured = {}
    def run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_completed(args)
    monkeypatch.setattr(claude_code.subprocess, "run", run)
    ok, answer, error = claude_code._run_prompt("advisory", 1)
    assert ok and answer == "safe-response" and not error
    args = captured["args"]
    assert "--safe-mode" in args
    assert "--bare" in args
    assert "--tools" in args and args[args.index("--tools") + 1] == ""
    assert "--disallowedTools" in args and args[args.index("--disallowedTools") + 1] == "*"
    assert "--strict-mcp-config" in args
    assert "--max-turns" in args and args[args.index("--max-turns") + 1] == "1"
    assert "--no-session-persistence" in args
    assert captured["kwargs"]["stderr"] == subprocess.DEVNULL
    assert "test-anthropic-secret" not in str(captured["args"])


def test_claude_adapter_fails_closed_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AURELIA_CLAUDE_CLI", "/usr/bin/claude")
    ok, answer, error = claude_code._run_prompt("advisory", 1)
    assert not ok and not answer
    assert error == "ANTHROPIC_API_KEY_MISSING"


def test_deepseek_harness_is_pinned_read_only_and_not_code_mode(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-secret")
    monkeypatch.setenv("AURELIA_DSH_CLI", "/usr/bin/dsh")
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[-1] == "--version":
            return fake_completed(args, stdout="dsh 0.2.1-rc.2")
        return fake_completed(args)
    monkeypatch.setattr(deepseek_harness.subprocess, "run", run)
    ok, answer, error = deepseek_harness._run_prompt("advisory", 1)
    assert ok and answer == "safe-response" and not error
    command, kwargs = calls[-1]
    assert command[command.index("--permission-mode") + 1] == "read-only"
    assert command[command.index("--approval-policy") + 1] == "never"
    assert command[command.index("--profile") + 1] == "headless"
    assert kwargs["env"]["DSH_PERMISSION_MODE"] == "read-only"
    assert kwargs["env"]["DSH_TOOLS_MODE"] == "native"
    assert kwargs["env"]["DSH_HOME"].endswith(".dsh-aurelia-advisory")
    assert "test-deepseek-secret" not in str(command)


def test_deepseek_adapter_rejects_unpinned_cli_version(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-secret")
    monkeypatch.setenv("AURELIA_DSH_CLI", "/usr/bin/dsh")
    monkeypatch.setattr(
        deepseek_harness.subprocess, "run",
        lambda args, **kwargs: fake_completed(args, stdout="dsh 99.0.0"),
    )
    ok, answer, error = deepseek_harness._run_prompt("advisory", 1)
    assert not ok and not answer
    assert error == "DEEPSEEK_HARNESS_VERSION_NOT_PINNED"


def test_hermes_adapter_requires_provider_model_key_and_disables_toolsets(monkeypatch):
    monkeypatch.setenv("AURELIA_HERMES_CLI", "/usr/bin/hermes")
    monkeypatch.setenv("AURELIA_HERMES_PROVIDER", "deepseek")
    monkeypatch.setenv("AURELIA_HERMES_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-hermes-secret")
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[-1] == "--version":
            return fake_completed(args, stdout="Hermes Agent v0.22.5")
        return fake_completed(args)
    monkeypatch.setattr(hermes_agent.subprocess, "run", run)
    ok, answer, error = hermes_agent._run_prompt("advisory", 1)
    assert ok and answer == "safe-response" and not error
    command, kwargs = calls[-1]
    assert command[1] == "chat"
    assert "--safe-mode" in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert command[command.index("--toolsets") + 1] == ""
    assert "--max-turns" not in command
    assert command[command.index("--provider") + 1] == "deepseek"
    assert kwargs["env"]["HERMES_MAX_ITERATIONS"] == "1"
    assert command[command.index("--model") + 1] == "deepseek-chat"
    assert kwargs["stderr"] == subprocess.DEVNULL
    assert "test-hermes-secret" not in str(command)


def test_hermes_adapter_blocks_unknown_provider_or_missing_model(monkeypatch):
    monkeypatch.setenv("AURELIA_HERMES_CLI", "/usr/bin/hermes")
    monkeypatch.setenv("AURELIA_HERMES_PROVIDER", "unsupported")
    monkeypatch.setenv("AURELIA_HERMES_MODEL", "model-x")
    monkeypatch.setenv("OPENAI_API_KEY", "some-secret")
    ok, answer, error = hermes_agent._run_prompt("advisory", 1)
    assert not ok and not answer
    assert error == "HERMES_PROVIDER_CREDENTIAL_MISSING"
    monkeypatch.setenv("AURELIA_HERMES_PROVIDER", "openai-api")
    monkeypatch.delenv("AURELIA_HERMES_MODEL", raising=False)
    ok, answer, error = hermes_agent._run_prompt("advisory", 1)
    assert not ok and not answer
    assert error == "HERMES_PROVIDER_AND_MODEL_REQUIRED"



@pytest.mark.parametrize(
    "relative_script",
    [
        "runtime/agent_adapters/claude_code.py",
        "runtime/agent_adapters/deepseek_harness.py",
        "runtime/agent_adapters/hermes_agent.py",
    ],
)
def test_adapter_is_directly_executable_from_isolated_working_directory(tmp_path, relative_script):
    root = Path(__file__).resolve().parents[1]
    adapter = root / relative_script
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path)}
    for key in (
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN",
        "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "HERMES_API_KEY",
        "OPENAI_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY", "ZAI_API_KEY",
        "AURELIA_CLAUDE_CLI", "AURELIA_DSH_CLI", "AURELIA_HERMES_CLI",
        "AURELIA_HERMES_PROVIDER", "AURELIA_HERMES_MODEL",
    ):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, str(adapter), "--healthcheck"],
        cwd=tmp_path,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0  # prerequisites absent; must fail closed
    assert "ModuleNotFoundError" not in result.stderr
    assert "Traceback" not in result.stderr
    assert "ANTHROPIC_API_KEY" not in result.stdout
def test_emit_response_uses_required_json_envelope(capsys):
    common.emit_response(
        task_id="task-123", status="COMPLETED",
        result={"answer": "advisory only", "api_key": "must-redact"},
    )
    output = json.loads(capsys.readouterr().out)
    assert output["schema"] == "aurelia.agent_task_response.v1"
    assert output["task_id"] == "task-123"
    assert output["status"] == "COMPLETED"
    assert output["result"]["api_key"] == "[REDACTED]"
