# AURELIA — LLM Gateway and Agent Infrastructure Integration Guide

Status as of 2026-10-09: **sources pinned; no gateway deployed**.

## Purpose and routing

The eight requested repositories are recorded in `config/external_repo_federation.json`, `config/agent_skill_federation.json`, and `config/agent_capability_matrix.json`. Exact source SHAs are provenance anchors, not evidence that a package was installed or executed.

- `BerriAI/litellm`: sandbox architecture reference for multi-provider routing, spend tracking, guardrails and observability.
- `LiteLLM-Labs/litellm-agent-control-plane`: sandbox reference for agent routing and session/schedule management.
- `BerriAI/litellm-docs`: reference-only documentation.
- `BerriAI/liteLLM-proxy`: deprecated legacy reference; do not install.
- `numman-ali/cc-mirror`: local developer-tooling reference only; no production credentials through modified coding-agent variants.
- `BerriAI/litellm-pgvector`: sandbox vector-memory reference; do not place broker or credential data in the vector store.
- `LiteLLM-Labs/litellm-rust`: proof-of-concept reference, not a production gateway.
- `langchain-ai/langchain-litellm`: sandbox adapter reference, pending compatibility and dependency review.

## Integration boundary

A future developer-only layout may use a pinned, secured LiteLLM service to standardize model-provider API calls made by Claude Code or other explicitly connected local agents. That gateway is optional and is not part of AURELIA's trading runtime.

ChatGPT in this conversation can consult the public source references and supervise reviews, but this does not install a connector into the ChatGPT product or create a persistent ChatGPT runtime. Claude Code and a separate developer machine/host are also **not verified as connected**. `CLAUDE.md` and `AGENTS.md` now direct repository agents to this guide; that updates repo instructions, not remote machines.

No gateway or agent-control-plane component may:
- receive Deriv tokens, account passwords, authenticated broker sessions, production SSH keys, or other AURELIA production secrets;
- read or write `config/LIVE_LOCK.yaml`, change `FINAL_EXECUTION_AUTHORIZATION`, or authorize broker transactions;
- submit orders, change stake limits, clear a kill switch, or bypass reconciliation;
- log prompts/results that contain credentials or account-sensitive broker data.

## Security gate before any gateway deployment

The LiteLLM project currently has high/critical upstream advisories. The federation registry tracks the specific advisories and links. Do not deploy from an unreviewed package or floating container tag. Before even a developer-only shared gateway is enabled:

1. Select an exact release and verify its signature/digest and patched-version status against all applicable upstream advisories.
2. Configure a strong `LITELLM_MASTER_KEY` in the gateway's secret store; never check secrets into Git or put them in request logs.
3. Disable client-supplied provider credential overrides (for example, `general_settings.allow_client_side_credentials: false`); allow only explicitly trusted model routes and identities.
4. Restrict management endpoints and ingress to loopback/private allowlisted networks; validate Host headers and restrict egress to approved model-provider endpoints.
5. Use separate low-scope development provider credentials. Never reuse AURELIA/Deriv credentials as model credentials.
6. Run the gateway and coding-agent plugins in a dedicated sandbox, inspect transitive dependencies, and perform negative tests for SSRF, arbitrary file reads, auth bypass, tool invocation and log redaction.
7. Require a human review and passing CI before promoting an adapter into AURELIA's ordinary engineering dependencies. No automatic promotion or capital-plane access.

## Supported Deriv secret-provisioning path

The GitHub connector used for repository edits cannot write Actions environment secrets. Do not try to get around this by putting tokens in source code, workflow inputs, issues, commits, artifacts or a temporary public service.

For a secure local route, run `bash scripts/provision_deriv_github_secrets.sh` on a trusted machine where GitHub CLI (`gh`) is authenticated to `Anto-30/aurelia-trading` with permission to write secrets for the `production` environment. The script first lists secret names only, then preserves any existing token/account/App ID/currency/mode aliases without overwriting them. It prompts with hidden input only for missing values, sends new values to GitHub's protected environment-secret API through `gh secret set` via stdin, verifies secret names only, and never prints values. It does not delete/revoke or overwrite existing secrets or modify the live lock. Do not use a shared/untrusted machine.

The provisioner cannot infer which of multiple saved token candidates is currently valid. Use the intended Deriv token and account binding from your own secure record; the next authenticated workflow is the validity check. A green secret-presence report means only that names/values are present, not that broker authentication is proven.

## Verification after configuration

1. Run `AURELIA Deriv Verify-Only Evidence` from GitHub Actions.
2. Require `DERIV_AUTH_SESSION=VERIFIED`, exact real-account login ID/currency/environment match, and a fresh valid balance snapshot.
3. Require broker-side account evidence and verify-only lifecycle evidence. Confirm no order submission and no capital authority was granted.
4. Re-run current assurance. Strategy OOS, calibration, production economics, production host/recovery and explicit release authorization remain separate gates.

The release control remains `live_trading_enabled: false`, `FINAL_EXECUTION_AUTHORIZATION: false`, `LIVE_EXECUTION: BLOCKED` until independent evidence and release authority say otherwise.


## Freebuff-related sources

Nineteen Freebuff/Codebuff-related repositories were added to the same federation registry. They are reference-only or sandbox-only; not production dependencies. Several implement compatibility proxies, session/token management, or request-shape adaptations; one upstream repository explicitly warns about Terms-of-Service risk. AURELIA will not implement usage-limit or ban evasion, deploy these proxies, or pass Deriv/production secrets through them. Use the official provider client or supported API routes where available. All sources are assigned to canonical agents with security review first; the label “Dev” routes to ClaudeCode unless a distinct Dev runtime is registered and verified.
