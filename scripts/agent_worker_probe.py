from __future__ import annotations

# This CI check is deliberately inventory-only. A temporary supervisor can
# create local test leases; those leases do not prove that Claude, Grok, Kimi,
# JEV, or any other external provider is installed, authenticated, or running.
# A provider may be reported CONNECTED only from a separately verified runtime
# identity, provider-authentication health check, and attributable task result.

ADVISORY_WORKERS = (
    "ClaudeCode",
    "KimiK3",
    "GrokBot",
    "GoogleAgentSkills",
    "GLM",
    "PlaywrightCLI",
    "JEV",
)
CAPITAL_AUTHORITY = "AURELIA"


def main() -> int:
    not_verified = ",".join(sorted(ADVISORY_WORKERS))
    print("AGENT_PROVIDER_CONNECTIVITY=NOT_VERIFIED")
    print("AGENT_PROVIDER_CONNECTED=NONE_CONFIRMED")
    print("AGENT_PROVIDER_NOT_VERIFIED=" + not_verified)
    print("AGENT_WORKER_PROCESS_LEASES=NOT_PROBED_IN_CI")
    print("AGENT_WORKER_TASK_EVIDENCE=NOT_VERIFIED")
    print("AGENT_WORKER_PROBE_MODE=INVENTORY_ONLY")
    print("CAPITAL_AUTHORITY_WORKER=INTENTIONALLY_DISABLED")
    print("CAPITAL_AUTHORITY_RUNTIME=DETERMINISTIC_CONTROL_PLANE")
    print("CAPITAL_AUTHORITY_HEARTBEAT=NOT_A_WORKER")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
