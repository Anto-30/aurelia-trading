# Cloud-hosted AURELIA runtime alternative

This deployment path removes the dependency on a continuously connected personal desktop. It runs the existing Dockerized AURELIA runtime on a persistent private cloud service with a mounted data disk. It does not bypass the canonical runtime, capital-plane controls, live lock, or certification gates.

## Deployment state

- Blueprint is a proposed deployment configuration; it has not been deployed.
- Automatic deployment is disabled so changes do not silently restart a service.
- Runtime starts with explicit execution authorization disabled and live execution blocked.
- Journal, federation, readiness, performance, and Deriv evidence paths point to persistent storage.
- No broker credentials or provider secrets are included in this file. Add them only through the host's encrypted secret/environment-variable interface after a security review.
- A cloud process being online is not proof that external agents are authenticated, the broker account is verified, strategies are qualified, or live trading is permitted.

## Deploy using Render

1. Connect the canonical repository `Anto-30/aurelia-trading` to a Render account that you control.
2. Create a Blueprint deployment from this branch and review the service plan and persistent-disk cost before applying it.
3. Keep live execution blocked. Do not add Deriv credentials until the secret-storage audit is complete and the account/session verification path is ready.
4. After deployment, verify the service's `/health` and `/ready` endpoints from an authorized private-network diagnostic, inspect runtime logs, and confirm persistent evidence survives a controlled restart. The Blueprint uses a private service so runtime diagnostics are not exposed as public endpoints.
5. Complete authenticated provider request/result tests, Deriv verify-only lifecycle checks, failure/recovery tests, prospective out-of-sample qualification, calibration, execution economics, and the 3600-second soak before any release review.

## Limits

This is a persistent cloud runtime alternative, not a Desktop Commander connection. It can run AURELIA's server process on a host the owner authorizes, but it cannot access files or applications on the user's personal computer. It does not itself supply authenticated Claude/Grok/other provider sessions. The configured local agent-worker command protocol still needs a real, authenticated provider adapter that follows the JSONL contract documented in the code.


## Alternative hosting paths for the whole agent fleet

Use one canonical AURELIA control plane and one durable task queue. Do not deploy independent agent copies that can each act on the broker or maintain separate capital state.

### Option A — Persistent cloud VM (most flexible fallback)

Run the existing Docker Compose/runtime stack on a Linux VM from a provider you control. Use systemd to restart the runtime, a dedicated non-root OS user, encrypted attached storage or a managed database for durable state, firewall allowlists, SSH keys (not passwords), automatic security updates, and provider secret storage. Keep the machine private; expose only the minimum authenticated control interface. This can support the central scheduler plus long-running workers without relying on a desktop session. It requires the owner to create the VM/account and approve its cost.

### Option B — Render private service or background worker

The current `render.yaml` proposal uses a private service with persistent storage. This is appropriate only if the runtime's HTTP health/control listener is required and the Docker command actually binds the required port. If the runtime is a pure long-running consumer and does not need inbound private-network traffic, use a Render background worker instead. Render states that private services are reachable on its private network and require a listening port; background workers cannot receive inbound traffic and are intended for long-running queue consumers. A persistent disk is limited to one service instance, so do not scale this file-backed stateful worker horizontally without moving state/leases to a transactional shared store.

### Option C — Managed container worker / job queue

Use a managed container service with a durable queue and managed database. This is a better route if the fleet needs independent worker scaling and crash recovery. Keep orchestration, leases, retries, idempotency, evidence lineage and capital authority in the canonical AURELIA control plane; worker containers should receive bounded advisory tasks and return signed/attributable results. This option requires configuring the cloud account, IAM and billing.

### Option D — GitHub-hosted CI runners (verification only)

Continue using GitHub Actions for linting, tests, assurance and scheduled monitoring. Treat each hosted runner as disposable: it is not the persistent agent runtime, should not be used to store state between runs, and must not be treated as proof of a continuously running agent. A self-hosted runner can execute on an owner-managed VM, but then that VM—not GitHub Actions—is the persistent host to secure and monitor.

## Agent-by-agent execution model

All registered roles use the same durable queue, task schema, evidence lineage and least-privilege boundaries. Each role gets a distinct task allowlist and authenticated connector where applicable:

- **ClaudeCode:** code changes, tests and implementation tasks; no broker credentials.
- **KimiK3:** adversarial review, fail-open/race/replay/idempotency testing; read-only by default.
- **GrokBot:** coordination, research triage and backlog routing; no capital authority.
- **GoogleAgentSkills:** cloud/security/supply-chain checks; least-privilege cloud permissions.
- **GLM:** evidence freshness, provenance and certification review.
- **PlaywrightCLI:** authenticated UI/E2E tests only against approved environments.
- **JEV:** independent regression and release-gate verification.
- **AURELIA:** deterministic risk checks, broker-state reconciliation and execution firewall; it alone remains subject to the existing capital-plane policy, not an external LLM.
- **ChatGPT:** supervisory triage and cross-checks; no direct capital authority.
- **Dev:** host provisioning and authorized deployment operations, only after the owner grants cloud or device access.

A configured command or a running process is not sufficient evidence that an agent did work. The provider adapter must receive the versioned task request, authenticate with its own provider credential, return a task-ID-matched terminal result, and attach verifiable evidence. Timeouts, invalid responses and lost workers must leave the task failed/blocked or safely requeued, never silently marked complete.

## Minimum production-host controls

- Persistent task/evidence storage with atomic writes, backups and restore tests.
- Durable lease ownership, lease expiry/reclaim, idempotency keys, bounded retries and dead-letter handling.
- Structured logs, metrics, alerting and an authenticated health/readiness endpoint.
- Provider-specific credentials in a secret manager, with rotation and no secrets in prompts, logs, Git history or task payloads.
- Network egress allowlisting where practical; no public unauthenticated control endpoint.
- Separate research and capital planes; agents cannot disable live locks or bypass broker verification.
- A kill switch and reconciliation path that fail closed on stale/unknown account state.
- Automated CI and a documented rollback procedure before production changes.

## Current decision

The fastest viable route without the user's desktop is: (1) deploy the canonical runtime on a user-authorized persistent cloud host; (2) make the durable task queue and provider request/result protocol operational for all ten registered roles; (3) validate each connector and recovery behavior; (4) complete Deriv verify-only, strategy qualification and release certification. The owner must authorize the host account and its costs; do not claim provisioning or agent connectivity before the resulting evidence exists.
