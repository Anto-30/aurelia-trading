from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from runtime.agent_adapters.common import (
    emit_response,
    failure_for_request,
    parse_cli_path,
    read_request,
    render_prompt,
    validate_model_output,
)

PROVIDER = "DeepSeek Harness"
CLI_ENV = "AURELIA_DSH_CLI"
PINNED_VERSION = "0.2.1-rc.2"
HEALTH_MARKER = "AURELIA_DSH_ADAPTER_HEALTH_OK"


def _harness_environment() -> dict[str, str]:
    env = dict(os.environ)
    # Hard safety overrides, never inherit a persisted DSH profile's permission
    # mode or switch into Code Mode. The worker's OS identity and cwd are also
    # isolated by the supervisor.
    env["DSH_PERMISSION_MODE"] = "read-only"
    env["DSH_TOOLS_MODE"] = "native"
    env["DSH_HOME"] = str(Path.home() / ".dsh-aurelia-advisory")
    return env


def _cli_version(cli: str) -> tuple[bool, str]:
    try:
        version = subprocess.run(
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
            env=_harness_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    value = (version.stdout or "").strip()
    return version.returncode == 0 and PINNED_VERSION in value, value


def _run_prompt(prompt: str, timeout_seconds: float) -> tuple[bool, str, str]:
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return False, "", "DEEPSEEK_API_KEY_MISSING"
    cli_candidates = parse_cli_path(CLI_ENV, "dsh")
    if not cli_candidates:
        return False, "", "DEEPSEEK_HARNESS_CLI_NOT_FOUND"
    cli = str(cli_candidates[0])
    version_ok, version = _cli_version(cli)
    if not version_ok:
        return False, "", "DEEPSEEK_HARNESS_VERSION_NOT_PINNED"
    try:
        completed = subprocess.run(
            [
                cli, "--profile", "headless",
                "--permission-mode", "read-only",
                "--approval-policy", "never",
                prompt,
            ],
            cwd=str(Path.home()),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            env=_harness_environment(),
        )
    except subprocess.TimeoutExpired:
        return False, "", "DEEPSEEK_HARNESS_REQUEST_TIMEOUT"
    except OSError:
        return False, "", "DEEPSEEK_HARNESS_PROCESS_START_FAILED"
    ok, answer, _error = validate_model_output(
        completed.stdout, completed.stderr or "", completed.returncode, "deepseek_harness"
    )
    if not ok:
        return False, "", "DEEPSEEK_HARNESS_PROVIDER_CALL_FAILED"
    return True, answer, ""


def main() -> int:
    if "--healthcheck" in sys.argv[1:]:
        if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
            return 1
        cli_candidates = parse_cli_path(CLI_ENV, "dsh")
        if not cli_candidates:
            return 1
        version_ok, _version = _cli_version(str(cli_candidates[0]))
        if not version_ok:
            return 1
        ok, answer, _error = _run_prompt(
            f"Reply with exactly {HEALTH_MARKER} and no other text.",
            timeout_seconds=45.0,
        )
        return 0 if ok and HEALTH_MARKER in answer else 1

    try:
        request = read_request()
        task_id = str(request["task"]["task_id"])
        prompt = render_prompt(request, agent_name="DeepSeekHarness", provider_name="DeepSeek Harness")
    except (ValueError, KeyError, TypeError) as exc:
        failure_for_request({"task": {}}, str(exc) or "DEEPSEEK_REQUEST_INVALID")
        return 0

    ok, answer, error = _run_prompt(prompt, timeout_seconds=105.0)
    if not ok:
        emit_response(task_id=task_id, status="FAILED", result={"error_code": error})
        return 0
    emit_response(
        task_id=task_id,
        status="COMPLETED",
        result={
            "provider": "deepseek",
            "runtime": "deepseek-harness-headless",
            "mode": "READ_ONLY_NATIVE_TOOLS_NO_CODE_MODE",
            "harness_version": PINNED_VERSION,
            "answer": answer,
            "action_claims": "NOT_AUTHORIZED",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
