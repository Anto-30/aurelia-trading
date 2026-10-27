from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "agent_runtime_provider_matrix.json"
DEFAULT_LEASE_PATH = "/tmp/aurelia/agent-federation-leases.json"


def _active_lease(
    lease_path: str | Path,
    agent: str,
    *,
    now: datetime,
) -> tuple[bool, str]:
    path = Path(lease_path)
    if not path.is_file():
        return False, "LEASE_FILE_MISSING"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return False, "LEASE_FILE_INVALID"
    if not isinstance(payload, dict) or not isinstance(payload.get("leases"), dict):
        return False, "LEASE_SCHEMA_INVALID"
    lease = payload["leases"].get(agent)
    if not isinstance(lease, dict):
        return False, "LEASE_MISSING"
    if str(lease.get("origin", "")) != "WORKER":
        return False, "LEASE_ORIGIN_NOT_WORKER"
    if not str(lease.get("worker_id", "")).strip():
        return False, "LEASE_WORKER_ID_MISSING"
    try:
        expires_at = datetime.fromisoformat(str(lease.get("expires_at", "")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False, "LEASE_EXPIRY_INVALID"
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        return False, "LEASE_EXPIRY_MUST_BE_TIMEZONE_AWARE"
    reference = now.astimezone(timezone.utc)
    if expires_at.astimezone(timezone.utc) <= reference:
        return False, "LEASE_EXPIRED"
    return True, "ACTIVE_WORKER_LEASE"


def _skill_presence(
    skill_names: list[str],
    *,
    repo_root: Path,
    skill_roots: list[str],
) -> dict[str, list[str]]:
    """Separate canonical system-catalog registration from local worker loading.

    The global skill inventory describes skills available to this assistant/plugin
    environment. It does not automatically install/inject those skills into a
    local Claude, DeepSeek or Hermes process. A local bundle counts as loaded
    only when a folder with the canonical final URI component exists in one of
    the configured local skill roots.
    """
    inventory_path = repo_root / "config" / "agent_skill_inventory.json"
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "catalog_available": [],
            "catalog_missing": list(skill_names),
            "local_loaded": [],
            "local_not_loaded": list(skill_names),
        }
    if inventory.get("schema") != "aurelia.agent_skill_inventory.v1":
        return {
            "catalog_available": [],
            "catalog_missing": list(skill_names),
            "local_loaded": [],
            "local_not_loaded": list(skill_names),
        }
    items = inventory.get("items", [])
    catalog_uris = {
        str(item.get("uri"))
        for item in items
        if isinstance(item, dict) and str(item.get("uri", "")).strip()
    }
    available = [uri for uri in skill_names if uri in catalog_uris]
    missing = [uri for uri in skill_names if uri not in catalog_uris]
    loaded: list[str] = []
    not_loaded: list[str] = []
    for uri in available:
        slug = uri.rstrip("/").rsplit("/", 1)[-1]
        if any((repo_root / root / slug).is_dir() for root in skill_roots):
            loaded.append(uri)
        else:
            not_loaded.append(uri)
    not_loaded.extend(missing)
    return {
        "catalog_available": available,
        "catalog_missing": missing,
        "local_loaded": loaded,
        "local_not_loaded": not_loaded,
    }


def _release_status(lock_path: Path) -> dict[str, object]:
    """Read only the public non-secret release flags; never mutate them."""
    try:
        lines = lock_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {
            "lock_file_readable": False,
            "live_execution": "UNKNOWN",
            "final_execution_authorization": "UNKNOWN",
        }
    values: dict[str, str] = {}
    for line in lines:
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return {
        "lock_file_readable": True,
        "live_execution": values.get("LIVE_EXECUTION", "UNKNOWN"),
        "final_execution_authorization": values.get("FINAL_EXECUTION_AUTHORIZATION", "UNKNOWN"),
        "capital_plane_mode": values.get("capital_plane_mode", "UNKNOWN"),
    }


def build_availability_report(
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
    lease_path: str | Path | None = None,
    now: datetime | None = None,
    repo_root: str | Path = ROOT,
) -> dict[str, object]:
    """Report local runtime availability without executing provider commands or reading secret values.

    A key-name marker only shows that an environment variable is present. A CLI
    binary only shows that an executable exists. Neither proves authentication,
    model reachability, task processing, or a broker session.
    """
    source_env = os.environ if env is None else env
    find_executable = shutil.which if which is None else which
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("AVAILABILITY_REFERENCE_TIME_MUST_BE_TIMEZONE_AWARE")
    current_time = current_time.astimezone(timezone.utc)
    config_file = Path(config_path)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schema") != "aurelia.agent_runtime_provider_matrix.v1":
        raise ValueError("AGENT_RUNTIME_PROVIDER_MATRIX_SCHEMA_INVALID")
    runtimes = config.get("runtimes")
    if not isinstance(runtimes, list) or not runtimes:
        raise ValueError("AGENT_RUNTIME_PROVIDER_MATRIX_EMPTY")

    lease_file = Path(
        lease_path
        or source_env.get("AURELIA_FEDERATION_LEASE_PATH", "")
        or config.get("default_lease_file", DEFAULT_LEASE_PATH)
    )
    project_root = Path(repo_root)
    skill_roots = [str(item) for item in config.get("local_skill_roots", [])]
    report_items: list[dict[str, object]] = []

    for spec in runtimes:
        if not isinstance(spec, dict):
            raise ValueError("AGENT_RUNTIME_SPEC_INVALID")
        name = str(spec.get("name", "")).strip()
        worker_agent = str(spec.get("worker_agent", "")).strip()
        command_env = str(spec.get("command_env", "")).strip()
        healthcheck_env = str(spec.get("healthcheck_env", "")).strip()
        if not name or not worker_agent or not command_env or not healthcheck_env:
            raise ValueError("AGENT_RUNTIME_SPEC_MISSING_REQUIRED_FIELD")

        explicit_command_configured = bool(str(source_env.get(command_env, "")).strip())
        explicit_healthcheck_configured = bool(str(source_env.get(healthcheck_env, "")).strip())
        adapter_relative = str(spec.get("adapter_script", "")).strip()
        adapter_path = (project_root / adapter_relative).resolve() if adapter_relative else None
        builtin_adapter_available = bool(
            spec.get("default_adapter_enabled") is True
            and adapter_path is not None
            and adapter_path.is_file()
            and project_root.resolve() in adapter_path.parents
        )
        command_configured = explicit_command_configured or builtin_adapter_available
        healthcheck_configured = explicit_healthcheck_configured or builtin_adapter_available

        cli_path_env = str(spec.get("cli_path_env", "")).strip()
        configured_cli_path = str(source_env.get(cli_path_env, "")).strip() if cli_path_env else ""
        executable_name = None
        if configured_cli_path:
            candidate_path = Path(configured_cli_path).expanduser()
            if candidate_path.is_file() and os.access(candidate_path, os.X_OK):
                executable_name = candidate_path.name
        if executable_name is None:
            for candidate in spec.get("executable_candidates", []):
                if find_executable(str(candidate)):
                    executable_name = str(candidate)
                    break

        provider = str(source_env.get(str(spec.get("provider_env", "")), "")).strip().lower() if spec.get("provider_env") else ""
        provider_credential_map = spec.get("provider_required_env_by_provider")
        if isinstance(provider_credential_map, dict):
            expected_credential_names = [
                str(name) for name in provider_credential_map.get(provider, [])
            ] if provider else []
        else:
            expected_credential_names = [
                str(name) for name in (
                    spec.get("provider_required_env")
                    or spec.get("credential_env_pass_list")
                    or spec.get("credential_env_any", [])
                )
            ]
        credential_env_names = [
            name for name in expected_credential_names
            if str(source_env.get(name, "")).strip()
        ]
        missing_prerequisites: list[str] = []
        if builtin_adapter_available:
            if executable_name is None:
                missing_prerequisites.append("CLI_MISSING")
            if provider_credential_map is not None and not provider:
                missing_prerequisites.append("HERMES_PROVIDER_NOT_SELECTED")
            if provider_credential_map is not None and provider and not expected_credential_names:
                missing_prerequisites.append("HERMES_PROVIDER_UNSUPPORTED")
            if provider_credential_map is not None and not str(source_env.get("AURELIA_HERMES_MODEL", "")).strip():
                missing_prerequisites.append("HERMES_MODEL_NOT_SELECTED")
            if expected_credential_names and not credential_env_names:
                missing_prerequisites.append("PROVIDER_CREDENTIAL_MISSING")
        lease_is_active, lease_reason = _active_lease(
            lease_file, worker_agent, now=current_time
        )

        if lease_is_active:
            if command_configured and healthcheck_configured:
                status = "WORKER_HEALTHCHECK_LEASE_ACTIVE"
            else:
                status = "INCONSISTENT_ACTIVE_LEASE"
        elif builtin_adapter_available and missing_prerequisites:
            status = "BUILTIN_ADAPTER_BLOCKED"
        elif command_configured and not healthcheck_configured:
            status = "BLOCKED_HEALTHCHECK_MISSING"
        elif not command_configured and healthcheck_configured:
            status = "BLOCKED_WORKER_COMMAND_MISSING"
        elif command_configured and healthcheck_configured:
            status = "CONFIGURED_NOT_ACTIVE_OR_HEALTHCHECK_FAILED"
        elif executable_name and credential_env_names:
            status = "CLI_AND_CREDENTIAL_MARKERS_PRESENT_AUTH_NOT_VERIFIED"
        elif executable_name:
            status = "CLI_PRESENT_CONNECTION_UNVERIFIED"
        elif credential_env_names:
            status = "CREDENTIAL_MARKERS_PRESENT_RUNTIME_MISSING"
        else:
            status = "RUNTIME_AND_CREDENTIAL_MISSING"

        skill_status = _skill_presence(
            [str(item) for item in spec.get("assigned_skills", spec.get("skills", []))],
            repo_root=project_root,
            skill_roots=skill_roots,
        )
        report_items.append({
            "name": name,
            "worker_agent": worker_agent,
            "status": status,
            "executable_found": executable_name is not None,
            "executable_name": executable_name,
            "builtin_adapter_available": builtin_adapter_available,
            "adapter_script": adapter_relative or None,
            "explicit_worker_command_configured": explicit_command_configured,
            "explicit_healthcheck_command_configured": explicit_healthcheck_configured,
            "worker_command_configured": command_configured,
            "healthcheck_command_configured": healthcheck_configured,
            "missing_prerequisites": missing_prerequisites,
            "worker_lease_active": lease_is_active,
            "lease_block_reason": lease_reason,
            "provider_session": "NOT_INDEPENDENTLY_VERIFIED" if lease_is_active else "UNKNOWN",
            "credential_env_present": credential_env_names,
            "assigned_skills": [str(item) for item in spec.get("assigned_skills", spec.get("skills", []))],
            "canonical_skill_catalog_available": skill_status["catalog_available"],
            "canonical_skill_catalog_missing": skill_status["catalog_missing"],
            "local_skills_loaded": skill_status["local_loaded"],
            "local_skills_not_loaded": skill_status["local_not_loaded"],
            "skill_bridge_status": str(spec.get("skill_bridge_status", "NOT_BRIDGED_TO_LOCAL_WORKER")),
            "assigned_plugins": [str(item) for item in spec.get("plugins", [])],
            "plugin_connection_status": str(spec.get("plugin_connection_status", "NOT_BRIDGED_TO_LOCAL_WORKER")),
            "capital_authority": False,
            "secret_values_emitted": False,
            "note": str(spec.get("note", "")),
        })

    release = _release_status(project_root / "config" / "LIVE_LOCK.yaml")
    return {
        "schema": "aurelia.agent_runtime_availability_report.v1",
        "generated_at_utc": current_time.isoformat(),
        "report_type": "LOCAL_RUNTIME_PRECHECK_NOT_AUTHENTICATION_PROOF",
        "runtime_protocol": config.get("runtime_protocol", {}),
        "release_lock": release,
        "capital_authority": False,
        "live_order_submission": False,
        "runtimes": report_items,
        "summary": {
            "total_runtimes": len(report_items),
            "active_worker_leases": sum(bool(item["worker_lease_active"]) for item in report_items),
            "worker_commands_configured": sum(bool(item["worker_command_configured"]) for item in report_items),
            "healthcheck_commands_configured": sum(bool(item["healthcheck_command_configured"]) for item in report_items),
            "local_executables_found": sum(bool(item["executable_found"]) for item in report_items),
            "builtin_adapters_available": sum(bool(item["builtin_adapter_available"]) for item in report_items),
            "provider_prerequisite_blockers": sum(item["status"] == "BUILTIN_ADAPTER_BLOCKED" for item in report_items),
            "credential_env_markers_present": sum(bool(item["credential_env_present"]) for item in report_items),
            "runtimes_blocked_or_unconfigured": sum(item["status"] != "WORKER_HEALTHCHECK_LEASE_ACTIVE" for item in report_items),
            "plugins_bridged_to_local_workers": sum(item["plugin_connection_status"] == "CONNECTED" for item in report_items),
        },
        "limitations": [
            "An environment-variable name is reported, never its value; presence is not authentication proof.",
            "A local executable is not proof of provider authorization or a usable model session.",
            "A worker lease is valid only for a live WORKER-origin lease with timezone-aware future expiry.",
            "An operator-defined healthcheck is only as strong as its command; this report does not independently authenticate the provider.",
            "ChatGPT-connected plugins are not automatically exposed to local Claude, DeepSeek, or Hermes processes.",
            "A local worker status never grants capital authority or live-order permission.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--lease-path", default=None)
    parser.add_argument("--output", default=None, help="Optional report path; secrets/command values are never included.")
    parser.add_argument("--require-active", action="store_true",
                        help="Exit nonzero unless every configured runtime has a live worker lease.")
    args = parser.parse_args()
    report = build_availability_report(args.config, lease_path=args.lease_path)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.require_active and report["summary"]["runtimes_blocked_or_unconfigured"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
