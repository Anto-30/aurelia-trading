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

## Deriv account authorization boundary — current blocker

Deriv's documented account-list endpoint and authenticated OTP endpoint require OAuth `trade` scope. The documented OAuth scopes do not include a genuinely read-only account-data scope. OAuth is an authentication mechanism; it does not make an account endpoint read-only.

Therefore:
- Do **not** provision, enable, or pass a trade-scoped OAuth token or PAT to an AURELIA `VERIFY_ONLY` account-verification worker.
- Keep account identity, balance, permissions, stake affordability, broker lifecycle, and transaction evidence blocked with `DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE`.
- Do not invoke the authenticated account-list or OTP endpoints to attempt verification.
- Do not treat public market-data access or a public proposal quote as evidence of account identity, balance, permissions, execution readiness, or realized economics.
- Public research uses only `DerivAuthenticationGate(plane="research").get_client()` and the credential-free public WebSocket endpoint. This client must reject account credentials in its process environment and enforce its public action whitelist.
- Reconsider account verification only if Deriv documents a genuinely read-only account-data endpoint/scope and an independent security review approves a design that keeps trade-capable permissions outside the research and VERIFY_ONLY processes.

The previous secret-provisioning instructions for Deriv account OAuth/PAT are superseded and must not be used for this workflow. Do not paste tokens into chat, source code, workflow inputs, issues, commits, artifacts, or a temporary public service. The GitHub connector does not need to access or modify protected Actions secrets for public market-data research.

## Verification

1. Verify public market data independently: R_100 appears in `active_symbols`, the public client retrieves valid 1-minute candles, and a live tick subscription returns at least two ordered R_100 ticks.
2. Record this as `PUBLIC_MARKET_DATA_VERIFIED` only. Store the source SHA, endpoint, timestamps, schema, tick/candle counts, no-auth boundary, and evidence hash. Do not include account secrets or account data.
3. Keep account evidence `BLOCKED` until a genuine read-only account-data API/scope exists and is independently approved.
4. Strategy OOS, calibration, production economics, durable runtime/recovery, security audit, and release authorization remain separate gates.

The canonical release controls remain `live_trading_enabled: false`, `FINAL_EXECUTION_AUTHORIZATION: false`, `LIVE_EXECUTION: BLOCKED`, and `capital_plane_mode: VERIFY_ONLY`.

## Freebuff-related sources

Nineteen Freebuff/Codebuff-related repositories were added to the same federation registry. They are reference-only or sandbox-only; not production dependencies. Several implement compatibility proxies, session/token management, or request-shape adaptations; one upstream repository explicitly warns about Terms-of-Service risk. AURELIA will not implement usage-limit or ban evasion, deploy these proxies, or pass Deriv/production secrets through them. Use the official provider client or supported API routes where available. All sources are assigned to canonical agents with security review first; the label “Dev” routes to ClaudeCode unless a distinct Dev runtime is registered and verified.
