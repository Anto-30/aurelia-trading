# AURELIA local agent worker protocol v1

This interface connects a configured local adapter process to AURELIA's advisory/engineering task queue. It is not a provider SDK, provider-authentication proof, broker interface, or capital authorization mechanism.

## Process contract

Configure a worker command with the matching environment variable:

- ClaudeCode: AURELIA_AGENT_CLAUDECODE_COMMAND
- KimiK3: AURELIA_AGENT_KIMIK3_COMMAND
- GrokBot: AURELIA_AGENT_GROKBOT_COMMAND
- Use the agent name's uppercase alphanumeric form for other registered agents.

The command must launch a dedicated adapter that implements this JSONL protocol. A raw interactive Claude, DeepSeek, Hermes, Kimi, Grok or other CLI is not automatically compatible. The supervisor starts one subprocess per configured worker, connects stdin and stdout, discards stderr from protocol processing, and requires one JSON object per line.

The subprocess runs with the same operating-system user and filesystem permissions as AURELIA; this protocol is not a sandbox. Only configure trusted adapters. Production deployment must additionally isolate adapters with OS/container controls and restrict their writable/readable paths to the minimum required evidence and working directories.

The supervisor filters inherited environment variables containing common credential, token, secret, broker, account and cloud-provider markers. Do not put credentials in command-line arguments. An adapter that needs an external model API must authenticate independently using its own approved secret store. It must not receive broker credentials. A local process handshake does not establish provider identity or provider account authentication.

## Handshake

Supervisor sends:

    {"protocol":"aurelia.agent-task.v1","type":"HELLO","agent":"ClaudeCode","worker_id":"agent-worker:ClaudeCode:...","session_nonce":"..."}

Worker replies with the same values except type is READY:

    {"protocol":"aurelia.agent-task.v1","type":"READY","agent":"ClaudeCode","worker_id":"agent-worker:ClaudeCode:...","session_nonce":"..."}

The response must contain exactly those five fields. The random session nonce correlates a worker process session; it is not a cryptographic credential or substitute for OS process isolation.

No lease is published and no task is claimed until READY validates.

## Task request

Supervisor sends one task at a time:

    {
      "protocol":"aurelia.agent-task.v1",
      "type":"TASK",
      "agent":"ClaudeCode",
      "worker_id":"agent-worker:ClaudeCode:...",
      "session_nonce":"...",
      "claim_token":"<one-time-worker-claim-capability>",
      "task":{
        "task_id":"task:...",
        "task_type":"ENGINEERING_REVIEW",
        "priority":50,
        "assigned_agent":"ClaudeCode",
        "payload":{"scope":"non-capital engineering task"},
        "created_at":"2026-11-05T00:00:00+00:00",
        "correlation_id":"corr-...",
        "status":"CLAIMED",
        "claimed_at":"2026-11-05T00:00:01+00:00"
      }
    }

Input payloads with obvious credential-bearing field names (token, secret, password, API key, authorization, cookie, private key, credential, OTP, login ID or account token) are blocked before dispatch. The supervisor does not intentionally pass broker credentials. The top-level claim_token is a separate random, one-time capability for this exact task claim; it is not a broker or provider credential. It is not included in the nested task payload, task journal or durable task record. A SHA-256 verifier and worker ID are stored with the claim. The capability is invalidated when the task is completed, requeued or recovered after lease expiry.

## Task result

Worker replies:

    {
      "protocol":"aurelia.agent-task.v1",
      "type":"TASK_RESULT",
      "agent":"ClaudeCode",
      "worker_id":"agent-worker:ClaudeCode:...",
      "session_nonce":"...",
      "task_id":"task:...",
      "correlation_id":"corr-...",
      "claim_token":"<same-one-time-worker-claim-capability>",
      "status":"COMPLETED",
      "evidence_ref":"worker-output/review.json",
      "result":{"summary":"Review artifact written","artifact_type":"application/json"}
    }

The response must contain exactly the documented fields, including the original claim_token. A mismatched, missing or stale claim token is rejected even when the agent, worker ID, task ID, correlation ID and process nonce match. An unrecognized worker ID cannot renew, requeue or complete another worker claim. Allowed status values are COMPLETED, FAILED and BLOCKED. Summary is limited to 4,096 characters and artifact_type to 128 characters. Worker-supplied free-form summaries are not persisted as authoritative findings; only the artifact type is retained in task metadata.

COMPLETED requires evidence_ref to be a relative path resolving to a regular file under AURELIA_EVIDENCE_ROOT. Absolute paths, traversal, missing files and symlink escapes are rejected. Before task completion is committed, AURELIA copies the submitted bytes into an atomic content-addressed snapshot at agent-tasks/<sha256>.artifact. The task record retains both submitted_evidence_ref (the original relative path) and evidence_ref (the archived snapshot), plus the SHA-256 digest and byte count. Evaluation reads the archived snapshot, so later changes to the worker's source file do not change the recorded handoff. A file's existence or digest is not proof that its content is correct or that tests passed.

Workers must not add capital-authority, live-trading, final-execution-authorization or order-submission fields. Any such field is rejected even when its value is false.

## Limits and lifecycle

- Maximum request/handshake frame: 1 MiB.
- Maximum result frame: 64 KiB.
- Handshake timeout: 10 seconds by default.
- Task response timeout: 300 seconds by default.
- A task claim and worker lease are renewed while a task is executing.
- Invalid protocol responses and worker exits requeue the claim; they do not fabricate task completion.
- Unconfigured workers remain CONNECTOR_REQUIRED and do not emit worker leases or claim tasks.
- Worker restarts use bounded exponential backoff.

## Evidence and governance

A COMPLETED task means the adapter submitted a correlated artifact. It does not mean the artifact independently passed correctness, regression, reproducibility, security or strategy validation. The performance evaluator therefore awards no positive quality points based on worker self-attestation or file existence alone; independent deterministic validation must be implemented before scores are awarded.

All workers remain advisory. They cannot grant capital authority, access the broker execution plane, change LIVE_LOCK, qualify strategies, submit proposals/orders or authorize live execution. This protocol does not satisfy Deriv authenticated-account lifecycle evidence, OOS strategy qualification, costs, forward testing, production persistence, soak or independent human review.
