# AURELIA agent worker task protocol

**Date:** 2026-11-05  
**Status:** Implementation proposal recorded on a draft branch  
**Scope:** Advisory and engineering workers only

## Intent

Replace the current process-liveness-only worker supervisor with a real, bounded, attributable task/result channel. A configured worker process must receive a task through an explicit protocol and return a response bound to the same agent, worker instance, session, task, and correlation ID. The federation may mark a task completed only when a valid completion response points to a verifiable evidence artifact inside the configured evidence root.

## Goals

- Keep the durable federation queue as the source of truth for PENDING, CLAIMED and terminal task state.
- Use newline-delimited JSON (JSONL) on subprocess stdin/stdout; stdout is protocol-only and stderr is not ingested.
- Require a per-process HELLO/READY handshake before publishing a worker lease or claiming work.
- Correlate each result to the exact task and worker session.
- Bound frame size, response size, handshake time and task-response time.
- Reject unknown protocol versions, malformed frames, mismatched identities/correlation, authority fields, invalid status and evidence paths outside the evidence root.
- Renew the claimed task while the worker is processing it; requeue on process loss or invalid protocol response.
- Preserve the invariant that advisory workers cannot authorize capital or submit orders.

## Non-goals

- This protocol does not connect or authenticate Claude, DeepSeek, Hermes, Kimi, Grok, JEV, Dev, or any external model provider.
- It does not grant worker processes broker credentials, capital authority or order-submission capability.
- It does not create a live trading runtime or qualify strategies.

## Approaches considered

1. **JSONL over stdin/stdout (selected):** Minimal dependency footprint, bounded framing, easy to implement with the existing asyncio subprocess supervisor. The trade-off is that each configured command must be a purpose-built adapter that speaks the protocol; arbitrary interactive CLIs are not automatically compatible.
2. **Local HTTP endpoint:** More flexible for long-running workers and multiple clients, but requires listener lifecycle, authentication, port management and network exposure controls not present in the current worker implementation.
3. **Direct federation journal polling:** Reuses existing persistence, but would require multiple processes to coordinate file locks, idempotency and acknowledgements. The current journal is append-only and does not provide a safe cross-process command/response queue.

## Protocol contract

Every frame is one UTF-8 JSON object followed by a newline. The supervisor enforces a 1 MiB maximum frame; worker result metadata is separately capped at 64 KiB.

1. Supervisor sends HELLO with protocol version, agent, worker ID and random process-session nonce.
2. Worker replies READY echoing protocol version, agent, worker ID and session nonce.
3. Supervisor renews the worker lease and sends TASK with task ID, correlation ID, task type and task payload.
4. Worker replies TASK_RESULT with matching protocol, agent, worker ID, session nonce, task ID and correlation ID; status is COMPLETED, FAILED or BLOCKED. COMPLETED requires a relative evidence reference that resolves to a file inside the configured evidence root. Result metadata is limited to a short summary and artifact type.
5. The supervisor rejects authority-bearing fields and never forwards worker-supplied claims such as verified, regression_free or reproducible as deterministic validation evidence.

The session nonce is a correlation value for a supervised local subprocess, not a substitute for OS isolation or external provider authentication. A provider adapter must independently authenticate to its provider and should not be given broker credentials.

## Failure behavior

- No command configured: publish CONNECTOR_REQUIRED; do not lease or claim tasks.
- Handshake failure, malformed/oversized frame, response timeout, correlation mismatch or evidence-path violation: publish sanitized protocol diagnostics and requeue the claim.
- Worker exits while idle: terminate/restart under the existing bounded restart policy; no completion is inferred.
- Worker exits during a claim: requeue the claim; do not fabricate a result.
- Invalid evidence reference: never mark the task COMPLETED.
- Keep LIVE_LOCK and all release gates unchanged.

## Verification

Regression coverage must include unconfigured workers, successful JSONL round-trip with an evidence artifact, handshake mismatch, task/correlation mismatch, evidence traversal/symlink escape, missing completion evidence, oversized frames, process exit and lease renewal. Exact-head Assurance, Agent Federation Audit and Continuity Watchdog must pass before requesting human review. A CI pass is not an independent human review or release authorization.