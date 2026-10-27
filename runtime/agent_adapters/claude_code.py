from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.agent_adapters.common import (
    emit_response,
    failure_for_request,
    parse_cli_path,
    read_request,
    render_prompt,
    validate_model_output,
)

PROVIDER = "Claude Code"
HEALTH_MARKER = "AURELIA_CLAUDE_ADAPTER_HEALTH_OK"
CLI_ENV = "AURELIA_CLAUDE_CLI"
PINNED_VERSION = "2.1.312"


def _command_args(cli: str, prompt: str) -> list[str]:
    # Current Claude Code CLI supports --tools "" to disable built-in tools and
    # --disallowedTools "*" to deny all tools. Safe/bare mode also omits
    # discovered plugins, MCP servers, hooks, memory and project instructions.
    return [
        cli,
        "--safe-mode",
        "--bare",
        "--print",
        "--output-format", "text",
        "--max-turns", "1",
        "--tools", "",
        "--disallowedTools", "*",
        "--strict-mcp-config",
        "--permission-mode", "plan",
        "--no-session-persistence",
        prompt,
    ]


def _version_ok(cli: str) -> bool:
    # Refuse to execute an unreviewed CLI version; auto-updates are disabled in
    # the supervisor-created worker environment. The version pin changes only
    # through a reviewed configuration/source update.
    try:
        result = subprocess.run(
            [cli, "--version"],
            cwd=str(Path.home()),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
            env=dict(os.environ),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and PINNED_VERSION in (result.stdout or "")


def _run_prompt(prompt: str, timeout_seconds: float) -> tuple[bool, str, str]:
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return False, "", "ANTHROPIC_API_KEY_MISSING"
    cli_candidates = parse_cli_path(CLI_ENV, "claude")
    if not cli_candidates:
        return False, "", "CLAUDE_CODE_CLI_NOT_FOUND"
    cli = str(cli_candidates[0])
    if not _version_ok(cli):
        return False, "", "CLAUDE_CODE_VERSION_NOT_PINNED"
    runtime_env = dict(os.environ)
    runtime_env["DISABLE_AUTOUPDATER"] = "1"
    try:
        completed = subprocess.run(
            _command_args(cli, prompt),
            cwd=str(Path.home()),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            env=runtime_env,
        )
    except subprocess.TimeoutExpired:
        return False, "", "CLAUDE_CODE_REQUEST_TIMEOUT"
    except OSError:
        return False, "", "CLAUDE_CODE_PROCESS_START_FAILED"
    return validate_model_output(
        completed.stdout, completed.stderr or "", completed.returncode, "claude_code"
    )


def main() -> int:
    if "--healthcheck" in sys.argv[1:]:
        ok, answer, _error = _run_prompt(
            f"Reply with exactly the text {HEALTH_MARKER} and no other text.",
            timeout_seconds=20.0,
        )
        return 0 if ok and HEALTH_MARKER in answer else 1

    try:
        request = read_request()
        task_id = str(request["task"]["task_id"])
        prompt = render_prompt(request, agent_name="ClaudeCode", provider_name="Anthropic Claude Code")
    except (ValueError, KeyError, TypeError) as exc:
        failure_for_request({"task": {}}, str(exc) or "CLAUDE_REQUEST_INVALID")
        return 0

    ok, answer, error = _run_prompt(prompt, timeout_seconds=110.0)
    if not ok:
        emit_response(task_id=task_id, status="FAILED", result={"error_code": error})
        return 0
    emit_response(
        task_id=task_id,
        status="COMPLETED",
        result={
            "provider": "anthropic",
            "runtime": "claude-code-cli",
            "mode": "TEXT_ONLY_NO_TOOLS",
            "answer": answer,
            "action_claims": "NOT_AUTHORIZED",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
