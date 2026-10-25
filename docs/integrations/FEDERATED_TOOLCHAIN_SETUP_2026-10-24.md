# Federated Toolchain Setup Plan — 2026-10-24

## Status and scope

This document defines the controlled setup path for the user's tool, skill, and plugin ecosystem across ChatGPT, Claude, DeepSeek Harness, and AURELIA. It is a configuration/runbook proposal, not proof that external accounts have been connected.

**Current verified boundary:** AURELIA remains `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, and `capital_plane_mode=VERIFY_ONLY`. Keep `config/LIVE_LOCK.yaml` unchanged. No LLM, tool, plugin, skill, or external repository receives capital authority or direct order-submission capability.

## Verified and unverified platform state

| Platform | What is available/known | What remains unverified or requires owner action |
|---|---|---|
| ChatGPT | Current conversation has access to the enabled tools/connectors exposed in this session; installed skill catalog includes Airtable, Dropbox, data analytics, Figma, HubSpot, investment banking, Notion, public-equity investing, Supabase, and Vercel skills, among others. | A complete account-wide inventory of every available/connected plugin is not exposed by this repository integration. Session tool access does not imply permanent agent access or cross-platform export. |
| Claude | Named as a desired federation peer. | No authenticated Claude account/session, MCP server config, installed skill list, or connection test is available here. Do not claim sync or installation. |
| DeepSeek Harness | Registered in AURELIA as `REGISTERED_SHADOW_ONLY`; prior recorded runtime binding is `NOT_CONNECTED`. | Runtime endpoint, authentication, model/provider credentials, tool invocation and round-trip test are outstanding. Registration is not connectivity. |
| AURELIA | Canonical repository is `Anto-30/aurelia-trading`; existing governance and external-repository intake PRs are separate, unmerged work. | A single verified live tool registry and provider connector configuration are not yet established. `config/agent_connectors.json` and `config/market_data_providers.json` were not found on main at this review. |

## Federation architecture

Use one canonical, version-controlled registry as the source of truth, with platform-specific adapters that consume an allowlisted subset. Do not attempt to copy secrets, provider sessions, or opaque plugin state between vendors.

1. **Inventory:** record tool/skill/plugin name, publisher, immutable version or commit, license, source, required scopes, data classes, network destinations, install hooks, and review status.
2. **Capability mapping:** assign tools by task and least privilege. A tool is not automatically granted to every agent just because it exists in ChatGPT.
3. **Provider adapters:** keep independent adapters/configuration for ChatGPT, Claude, and DeepSeek. Store provider secrets only in the approved secret manager and inject them at runtime; never put keys in Git, prompts, logs, generated files, or issue comments.
4. **AURELIA gateway:** agents call an authenticated, audited tool gateway with per-tool allowlists, argument schemas, timeouts, output limits, rate limits, and trace IDs. Default deny on missing identity, invalid schema, timeout, unknown state, or policy error.
5. **Policy enforcement:** tools may research, read, analyze, test in isolation, or propose changes. Only reviewed deterministic code may affect the canonical risk plane. LLMs and external tools cannot authorize, size, route, or submit trades.
6. **Evidence:** record registry version, source pin, configuration hash, provider/model identity, tool call ID, UTC timestamp, result status, and redacted error. Do not record secrets or unnecessary personal data.
7. **Release:** use an isolated test environment and synthetic/mock endpoints first; require security review, tests, human approval, and the existing protected assurance gates before any production deployment.

## Default assignment policy

| Tool category | ChatGPT | Claude | DeepSeek Harness | AURELIA runtime |
|---|---|---|---|---|
| Read-only web/research and documentation | Enable where available | Enable after owner config | Enable after adapter test | Research gateway only |
| Repository read/search and diff review | Enable where connected | Enable after owner config | Enable after adapter test | Read-only by default; writes require reviewed PR workflow |
| Coding, test generation, static analysis | Enable in disposable workspace | Enable in disposable workspace | Enable in disposable workspace | CI/sandbox only; no direct production mutation |
| Analytics, spreadsheets, reporting | Enable when task-relevant | Enable after owner config | Enable after adapter test | Read-only datasets and report artifacts |
| Browser/desktop/computer-use tools | Per-session consent and isolated profile | Per-provider policy | Disabled until separately reviewed | Never expose broker sessions, secrets, or production host |
| Email, messaging, CRM, calendar and file mutation | Explicit user approval for each consequential action | Same | Same | Notification/workflow gateway with scope limits; no silent external writes |
| Secret managers and credential access | No raw secret disclosure to model | No raw secret disclosure to model | No raw secret disclosure to model | Narrow runtime identity; secrets injected only to authorized service |
| Deriv/broker data | Public/read-only data first | No authenticated account by default | No authenticated account by default | Verify-only lifecycle under existing policy |
| Order execution, capital management, risk authorization | **Denied** | **Denied** | **Denied** | **Denied while LIVE_LOCK is blocked; deterministic risk engine remains sole veto authority** |

## Activation checklist

- [ ] Owner exports/reviews the current tool, skill, and plugin inventory from each provider UI/API, including versions, scopes and source.
- [ ] Approve the canonical inventory and each assignment; do not infer plugin availability from product names or past conversations.
- [ ] Create provider-specific credentials in the approved secret manager. No keys are pasted into ChatGPT, Claude, DeepSeek prompts, GitHub issues, or this repository.
- [ ] Configure the Claude MCP/skill connections in the Claude account/environment and run a harmless read-only health check.
- [ ] Configure DeepSeek Harness provider endpoint/model, authentication reference, and scoped tool adapter; run a no-secret, no-write round-trip test.
- [ ] Implement or validate the AURELIA registry schema and gateway with default-deny behavior, audit events, and independent permission boundaries.
- [ ] Test allow/deny, malformed arguments, timeouts, retries, prompt-injection/tool-output handling, secret redaction, and network-egress restrictions in an isolated environment.
- [ ] Verify ChatGPT connectors/plugins from the actual account settings; this repository cannot activate account-level connectors.
- [ ] Reconcile inventory drift on a schedule and fail closed when a source pin or capability schema changes.
- [ ] Obtain independent human review and exact-head CI before merging this documentation or any future implementation.
- [ ] Keep live execution blocked until all independent release gates are satisfied.

## Acceptance criteria

Setup is not considered complete until each provider has: (a) an owner-authorized configuration, (b) a least-privilege tool/skill inventory, (c) a successful harmless round-trip test, (d) a failure/timeout test, (e) auditable provenance and redaction, and (f) a reviewed rollback path. A green documentation CI check alone does not satisfy these criteria.

## Explicit non-claims

This document does not claim that tools or plugins have been installed into Claude or DeepSeek, that ChatGPT account-level settings were changed, that provider credentials exist, that agents can call one another, that every skill is secure, or that any external tool is authorized for trading. No package was installed, no provider secret was read or written, no live broker session was opened, and no order was submitted.


## Captured ChatGPT session inventory — 2026-10-24

A session-scoped inventory snapshot was added at [CHATGPT_SESSION_TOOL_SKILL_INVENTORY_2026-10-24.json](./CHATGPT_SESSION_TOOL_SKILL_INVENTORY_2026-10-24.json). At capture it contained **4,087 exposed tool entries, 548 skill records, and 135 connector/tool namespaces**. The file includes tool names, skill URIs/descriptions, and namespace counts.

This is a useful baseline for an inventory reconciliation; it is not a full ChatGPT account plugin export, does not prove every listed integration is connected to an external account, and does not make the tools portable to Claude, DeepSeek Harness, or the AURELIA runtime. Re-capture after connector changes and diff against a reviewed allowlist before granting access.
