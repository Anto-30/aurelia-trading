from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.agent_federation import PersistentAgentFederation
from runtime.agent_workers import AgentWorkerSupervisor
from scripts.agent_runtime_availability import build_availability_report

MATRIX = ROOT / "config" / "agent_runtime_provider_matrix.json"


async def run_worker_probe(
    *,
    env: Mapping[str, str] | None = None,
    require_active: bool = False,
    timeout_seconds: float = 5.0,
) -> dict[str, object]:
    runtime_env = dict(os.environ if env is None else env)
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    if matrix.get("schema") != "aurelia.agent_runtime_provider_matrix.v1":
        raise RuntimeError("AGENT_RUNTIME_PROVIDER_MATRIX_SCHEMA_INVALID")
    specs = matrix.get("runtimes")
    roster = matrix.get("runtime_managed_agent_roster")
    if not isinstance(specs, list) or not isinstance(roster, list):
        raise RuntimeError("AGENT_RUNTIME_ROSTER_MISSING")
    names = [str(spec.get("name", "")) for spec in specs if isinstance(spec, dict)]
    if len(names) != len(specs) or set(names) != set(roster) or len(names) != len(set(names)):
        raise RuntimeError("AGENT_RUNTIME_ROSTER_PROFILE_MISMATCH")

    with tempfile.TemporaryDirectory(prefix="aurelia-agent-probe-") as tmp:
        root = Path(tmp)
        provider_preflight = build_availability_report(
            MATRIX, env=runtime_env, lease_path=root / "leases.json", repo_root=ROOT
        )
        preflight_by_name = {
            str(item["name"]): item for item in provider_preflight["runtimes"]
        }
        federation = PersistentAgentFederation(
            journal_path=root / "journal.ndjson",
            lease_path=root / "leases.json",
            task_path=root / "tasks.json",
            config_hash="probe",
            source_hash="probe",
            lease_seconds=max(10.0, timeout_seconds * 3.0),
        )
        supervisor = AgentWorkerSupervisor(
            federation,
            agents=tuple(roster),
            interval_seconds=0.2,
            env=runtime_env,
        )
        supervisor.start()
        try:
            deadline = asyncio.get_running_loop().time() + max(0.1, timeout_seconds)
            while asyncio.get_running_loop().time() < deadline:
                active_now = set(federation.active_agents())
                statuses_ready = True
                for spec in specs:
                    name = str(spec["name"])
                    preflight = preflight_by_name[name]
                    command_configured = bool(str(runtime_env.get(str(spec["command_env"]), "")).strip())
                    healthcheck_configured = bool(str(runtime_env.get(str(spec["healthcheck_env"]), "")).strip())
                    builtin_blocked = (
                        bool(preflight.get("builtin_adapter_available"))
                        and bool(preflight.get("missing_prerequisites"))
                    )
                    if name in active_now:
                        continue
                    messages = federation.messages_for(name, limit=100)
                    has_blocked = any(row.get("message_type") == "CONNECTOR_REQUIRED" for row in messages)
                    has_unhealthy = any(row.get("message_type") == "CONNECTOR_UNHEALTHY" for row in messages)
                    if builtin_blocked:
                        statuses_ready = statuses_ready and has_unhealthy
                    elif not command_configured and not preflight.get("builtin_adapter_available"):
                        statuses_ready = statuses_ready and has_blocked
                    elif command_configured and not healthcheck_configured:
                        statuses_ready = statuses_ready and has_blocked
                    else:
                        statuses_ready = False
                if statuses_ready:
                    break
                await asyncio.sleep(0.1)

            reports: list[dict[str, object]] = []
            failures: list[str] = []
            for spec in specs:
                name = str(spec["name"])
                command_raw = bool(str(runtime_env.get(str(spec["command_env"]), "")).strip())
                healthcheck_raw = bool(str(runtime_env.get(str(spec["healthcheck_env"]), "")).strip())
                preflight = preflight_by_name[name]
                builtin_available = bool(preflight.get("builtin_adapter_available"))
                command_configured = command_raw or builtin_available
                healthcheck_configured = healthcheck_raw or builtin_available
                active = name in federation.active_agents()
                messages = federation.messages_for(name, limit=100)
                connector_required = any(row.get("message_type") == "CONNECTOR_REQUIRED" for row in messages)
                connector_unhealthy = any(row.get("message_type") == "CONNECTOR_UNHEALTHY" for row in messages)

                if active:
                    status = "WORKER_HEALTHCHECK_LEASE_ACTIVE"
                elif builtin_available and preflight.get("missing_prerequisites"):
                    status = "BLOCKED_PROVIDER_PREREQUISITES"
                    # Missing CLI/key/provider-selection is an honest block, not
                    # a failed liveness assertion unless strict active mode was asked.
                    if not connector_unhealthy:
                        failures.append(f"{name}:MISSING_PROVIDER_BLOCK_STATUS")
                elif not command_configured:
                    status = "BLOCKED_CONFIG"
                    if not connector_required:
                        failures.append(f"{name}:MISSING_BLOCKED_STATUS:WORKER_COMMAND_MISSING")
                elif not healthcheck_configured:
                    status = "BLOCKED_CONFIG"
                    if not connector_required:
                        failures.append(f"{name}:MISSING_BLOCKED_STATUS:WORKER_HEALTHCHECK_COMMAND_MISSING")
                elif connector_unhealthy:
                    status = "HEALTHCHECK_FAILED"
                    failures.append(f"{name}:{status}")
                else:
                    status = "CONFIGURED_NOT_ACTIVE"
                    failures.append(f"{name}:{status}")
                if require_active and not active:
                    failures.append(f"{name}:ACTIVE_WORKER_REQUIRED")
                reports.append({
                    "name": name,
                    "status": status,
                    "worker_command_configured": command_configured,
                    "healthcheck_command_configured": healthcheck_configured,
                    "explicit_worker_command_configured": command_raw,
                    "explicit_healthcheck_command_configured": healthcheck_raw,
                    "builtin_adapter_available": builtin_available,
                    "missing_prerequisites": preflight.get("missing_prerequisites", []),
                    "worker_lease_active": active,
                    "provider_session": "NOT_INDEPENDENTLY_VERIFIED" if active else "UNKNOWN",
                    "capital_authority": False,
                })

            return {
                "schema": "aurelia.agent_worker_probe.v1",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "status": "PASS" if not failures else "FAIL",
                "strict_active_required": require_active,
                "capital_authority": False,
                "live_order_submission": False,
                "active_worker_count": sum(bool(item["worker_lease_active"]) for item in reports),
                "configured_worker_count": sum(bool(item["worker_command_configured"]) for item in reports),
                "runtime_count": len(reports),
                "runtimes": reports,
                "failures": failures,
                "notes": [
                    "BLOCKED_CONFIG means a provider adapter/readiness command is missing; this is not a running agent.",
                    "A lease proves only that a configured process is alive and its operator-defined healthcheck passed.",
                    "Provider identity, authenticated model session, and task quality require separate evidence.",
                    "AURELIA remains the deterministic control plane; ChatGPT and Dev are not local model-worker processes.",
                ],
            }
        finally:
            await supervisor.stop()


async def main_async() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-active", action="store_true",
                        help="Fail unless all provider runtimes have active healthchecked worker leases.")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    result = await run_worker_probe(
        require_active=args.require_active,
        timeout_seconds=args.timeout_seconds,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    availability = build_availability_report(env=os.environ)
    print("AGENT_RUNTIME_AVAILABLE=" + str(availability["summary"]["active_worker_leases"]))
    print("AGENT_RUNTIME_CONFIGURED=" + str(availability["summary"]["worker_commands_configured"]))
    print("AGENT_RUNTIME_ROSTER=" + str(availability["summary"]["total_runtimes"]))
    print("CAPITAL_AUTHORITY=FALSE_FOR_ALL_EXTERNAL_AGENTS")
    print("LIVE_EXECUTION=BLOCKED")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
