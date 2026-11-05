# Implementation plan: agent worker JSONL task protocol

**Date:** 2026-11-05

## Task 1 — Prove the protocol contract in tests

1. Extend tests/test_agent_workers.py with a deterministic temporary worker adapter that reads one JSONL frame at a time.
2. Assert the HELLO/READY handshake binds protocol, agent, worker ID and session nonce.
3. Enqueue a task and assert the worker receives its exact task ID and correlation ID.
4. Make the worker write an evidence artifact under a temporary evidence root and return TASK_RESULT; assert only that correlated task becomes COMPLETED.
5. Add negative cases for handshake mismatch, wrong task/correlation, absent evidence, frame oversize, and unconfigured command. Ensure invalid/aborted claims return to PENDING.

## Task 2 — Harden evidence resolution and task persistence

1. Restrict evidence resolution to paths that resolve below the configured evidence root, including symlink resolution.
2. Add explicit task-claim renewal and safe requeue for a worker-owned CLAIMED task.
3. Require a real evidence file for COMPLETED; preserve FAILED/BLOCKED terminal results without a completion artifact.
4. Keep journal events attributable to task ID, agent and correlation ID, and never record raw exception text or frame contents.

## Task 3 — Implement the supervised JSONL adapter lifecycle

1. Start configured workers with stdin/stdout pipes, bounded stream limits and stderr excluded from protocol parsing.
2. Perform HELLO/READY before issuing a worker lease.
3. Claim and send one task at a time; concurrently renew its claim and worker lease while awaiting a bounded response.
4. Validate exact correlation fields, allowed status, response-size limits, result schema and authority-field exclusion.
5. Complete only after the evidence reference is verified; otherwise requeue or mark the protocol attempt failed without fabricating task success.
6. Restart failed workers using the existing restart policy and keep unconfigured providers visibly unavailable.

## Task 4 — Publish the adapter contract and verify

1. Document JSONL message examples, the adapter command contract, evidence root and operational limitations.
2. Run focused worker/federation tests, full Assurance, Agent Federation Audit and Continuity Watchdog on the exact head.
3. Inspect exact-head results and review the complete diff. Request independent human review; keep the PR draft until review and downstream release controls are satisfied.

## Global constraints

- Do not modify config/LIVE_LOCK.yaml, broker credentials, capital authority, order execution or release gates.
- Do not describe a configured local adapter as a connected model provider without external authentication and attributable provider evidence.
- Do not merge the feature branch or claim strategies/live trading are qualified.