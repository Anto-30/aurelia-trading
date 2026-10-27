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

PROVIDER = "Hermes Agent"
CLI_ENV = "AURELIA_HERMES_CLI"
PROVIDER_ENV = "AURELIA_HERMES_PROVIDER"
MODEL_ENV = "AURELIA_HERMES_MODEL"
PINNED_VERSION = "v0.22.5"
HEALTH_MARKER = "AURELIA_HERMES_ADAPTER_HEALTH_OK"
PROVIDER_KEY_ENV = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai-api": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "xai": "XAI_API_KEY",
    "zai": "ZAI_API_KEY",
}


def _settings() -> tuple[str, str, str]:
    provider = os.environ.get(PROVIDER_ENV, "").strip().lower()
    model = os.environ.get(MODEL_ENV, "").strip()
    cli_candidates = parse_cli_path(CLI_ENV, "hermes")
    if not cli_candidates:
        return "", provider, model
    return str(cli_candidates[0]), provider, model


def _provider_ready(provider: str) -> bool:
    key_name = PROVIDER_KEY_ENV.get(provider)
    return bool(key_name and os.environ.get(key_name, "").strip())


def _version_ok(cli: str) -> bool:
    try:
        result = subprocess.run(
            [cli, "--version"],
            cwd=str(Path.home()),
            input=prompt,
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
    cli, provider, model = _settings()
    if not cli:
        return False, "", "HERMES_CLI_NOT_FOUND"
    if not provider or not model:
        return False, "", "HERMES_PROVIDER_AND_MODEL_REQUIRED"
    if not _provider_ready(provider):
        return False, "", "HERMES_PROVIDER_CREDENTIAL_MISSING"
    if not _version_ok(cli):
        return False, "", "HERMES_VERSION_NOT_PINNED"
    # --safe-mode disables plugins, MCP, rules and user customizations.
    # --toolsets "" is the explicit defense-in-depth setting: no shell, browser,
    # filesystem-edit, or other action tool is available to this advisory adapter.
    # It is not enough to say "no tools" in the prompt; enforcement is CLI-level.
    command = [
        cli, "chat",
        "--safe-mode",
        "--ignore-user-config",
        "--ignore-rules",
        "--provider", provider,
        "--model", model,
        "--toolsets", "",
        "--max-turns", "1",
        "--quiet",
        "-q", prompt,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=str(Path.home()),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            env=dict(os.environ),
        )
    except subprocess.TimeoutExpired:
        return False, "", "HERMES_REQUEST_TIMEOUT"
    except OSError:
        return False, "", "HERMES_PROCESS_START_FAILED"
    ok, answer, _error = validate_model_output(
        completed.stdout, completed.stderr or "", completed.returncode, "hermes"
    )
    if not ok:
        return False, "", "HERMES_PROVIDER_CALL_FAILED"
    return True, answer, ""


def main() -> int:
    if "--healthcheck" in sys.argv[1:]:
        ok, answer, _error = _run_prompt(
            f"Reply with exactly {HEALTH_MARKER} and no other text.",
            timeout_seconds=45.0,
        )
        return 0 if ok and HEALTH_MARKER in answer else 1

    try:
        request = read_request()
        task_id = str(request["task"]["task_id"])
        prompt = render_prompt(request, agent_name="HermesAgent", provider_name="Hermes Agent")
    except (ValueError, KeyError, TypeError) as exc:
        failure_for_request({"task": {}}, str(exc) or "HERMES_REQUEST_INVALID")
        return 0

    ok, answer, error = _run_prompt(prompt, timeout_seconds=105.0)
    if not ok:
        emit_response(task_id=task_id, status="FAILED", result={"error_code": error})
        return 0
    cli, provider, model = _settings()
    emit_response(
        task_id=task_id,
        status="COMPLETED",
        result={
            "provider": provider,
            "runtime": "hermes-agent-cli",
            "version": PINNED_VERSION,
            "model": model,
            "mode": "SAFE_MODE_NO_TOOLSETS",
            "answer": answer,
            "action_claims": "NOT_AUTHORIZED",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
