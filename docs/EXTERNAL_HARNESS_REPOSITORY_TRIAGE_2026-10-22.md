# External Harness Repository Triage — 2026-10-22

## Status and scope

This is a first-pass, source-linked repository triage based on public repository landing pages and READMEs. It is **not** a completed source-code security audit, license compatibility review, dependency audit, reproducible build, or runtime test. No third-party source has been installed, executed, vendored, or granted access to AURELIA.

AURELIA remains the sole capital/execution authority. Keep `config/LIVE_LOCK.yaml` unchanged: `live_trading_enabled: false`, `FINAL_EXECUTION_AUTHORIZATION: false`, `LIVE_EXECUTION: BLOCKED`, and `capital_plane_mode: VERIFY_ONLY`. External code must not read production secrets, call authenticated broker write APIs, submit orders, mutate the lock, or deploy to production.

## Decision rules

1. Prefer narrow tools with an identifiable AURELIA use case over adopting another full agent runtime.
2. Treat README claims as leads, not proof. Pin exact commit SHAs before any evaluation; record license, dependency/SBOM, install scripts, network egress, permissions, tests, and maintenance status.
3. Inspect source before execution. Use an isolated disposable workspace/container, no production credentials, no host Docker socket, no browser profile, no SSH keys, and no writable AURELIA checkout.
4. Require deterministic tests and a human-reviewed diff before any change to canonical repository files. No automatic synchronization of upstream code.
5. A successful agent run, code-review report, CI check, or browser session is not evidence of broker truth or trading readiness.

## Triage matrix

| Repository | Publicly described role / likely fit | Initial disposition | Key boundary / next check |
|---|---|---|---|
| [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness) | Multi-provider coding-agent harness and personal-agent workflow | **Evaluate in sandbox** for engineering workflow only | Inspect install scripts, tool permissions, subprocess/network behavior, and project write scope. Do not install into the trading runtime. |
| [harness/harness](https://github.com/harness/harness) | Full developer platform: source control, CI/CD, dev environments, artifact registry | **Defer** | Much larger infrastructure footprint than the immediate agent-orchestration need. Evaluate only if a concrete self-hosted SCM/CI requirement exists. |
| [alibaba/open-code-review](https://github.com/alibaba/open-code-review) | LLM-assisted CLI code review with line-level findings and deterministic checks | **Priority candidate** for isolated PR review | Run read-only against a patch copy first; redact secrets and sensitive data before model submission; verify rule coverage and false-positive/negative behavior. |
| [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | Python agent SDK with tools, handoffs, guardrails, human-in-loop and tracing | **Priority candidate** as a framework reference | Do not replace AURELIA's deterministic risk/capital plane. Prototype only in a separate non-capital process with strict tool allowlists. |
| [browser-use/browser-harness](https://github.com/browser-use/browser-harness) | LLM-driven browser automation over CDP, with generated helpers and optional cloud scale | **Restricted sandbox evaluation only** | Browser sessions can expose authenticated websites. No production browser profile, credentialed broker UI, trading actions, downloads, or recordings by default. |
| [strands-agents/harness-sdk](https://github.com/strands-agents/harness-sdk) | Python/TypeScript agent SDK and assembled harness with lifecycle controls, MCP, guardrails and evals | **Compare; do not stack by default** | Compare against OpenAI Agents SDK on cancellation, budgets, tool policy, observability, portability, and testability. Choose one runtime per prototype. |
| [HKUDS/DeepCode](https://github.com/HKUDS/DeepCode) | Coding/research agent project; exact capabilities need source-level confirmation | **Identity and scope verification required** | Verify current README, license, latest commit, dependency graph, and whether the project is maintained before ranking it against coding agents. |
| [MiniMax-AI/minimax-code](https://github.com/MiniMax-AI/minimax-code) | Terminal coding agent with model/provider choice, tools, subagents and sandbox/permission controls | **Optional engineering-host candidate** | Do not make it a persistent AURELIA daemon. Test permission enforcement, shell/network restrictions, telemetry, and credential isolation. |
| [coleam00/Archon](https://github.com/coleam00/Archon) | Workflow/harness builder for deterministic, repeatable AI coding | **Evaluate as developer workflow tooling** | Use isolated worktrees and reviewable plans. Confirm commands, hooks, generated files, and provider installation behavior before project use. |
| [HarnessRouter/harnessrouter](https://github.com/HarnessRouter/harnessrouter) | Repository identity and current purpose not yet independently confirmed | **Hold / verify first** | Do not infer function from the name. Inspect canonical README, license, recent commits, release history, and security policy before inclusion. |
| [QoderAI/better-harness](https://github.com/QoderAI/better-harness) | Evidence-oriented analysis of coding-agent workflows, task episodes, validation and delivery | **Priority candidate** for process audit | Its reports can inform engineering improvements but are not causal proof or a substitute for CI, review, or release gates. Use read-only/no-session mode first. |
| [openlit/openlit](https://github.com/openlit/openlit) | Observability/telemetry for LLM applications | **Evaluate after privacy review** | Confirm data collection, exporters, retention, redaction, and outbound network behavior. Never send broker secrets, account identifiers, or sensitive trading payloads. |
| [truefoundry/trueforge](https://github.com/truefoundry/trueforge) | Agent execution harness with MCP tools, skills, sandboxing, approvals and session state | **Compare; do not stack by default** | Local mode is documented as local-only and without login by default. Keep bound to localhost; assess auth and isolation before any shared deployment. |
| [CyberStrikeus/CyberStrike](https://github.com/CyberStrikeus/CyberStrike) | Exact project scope and current security posture not yet independently confirmed | **Hold / verify first** | Treat as potentially security-sensitive until repository contents, license, install behavior, capabilities and intended use are confirmed. No execution on AURELIA hosts. |
| [vercel/eve](https://github.com/vercel/eve) | Agent application framework with typed tools, human-in-the-loop, connections, channels, skills and state | **Optional architecture reference** | Evaluate only if building a separate user-facing agent surface; avoid duplicating AURELIA's canonical runtime or control plane. |
| [the-open-agent/openagent](https://github.com/the-open-agent/openagent) | Self-hostable personal AI assistant with RAG, browser/computer use and MCP-compatible tools | **Defer** | Broad personal-assistant scope is not a direct trading-system dependency. If later tested, isolate browser, shell and MCP permissions. |
| [cytostack/openwolf](https://github.com/cytostack/openwolf) | Local project memory, code maps and cross-agent handoff/usage records | **Optional, conditional** | AGPL-3.0 is indicated in its README; conduct license/compliance review before redistribution or incorporation. Review local session data and generated `.wolf/` files for sensitive content. |
| [thu-nmrc/OpenHarness](https://github.com/thu-nmrc/OpenHarness) | Current purpose and relationship to other similarly named projects not confirmed | **Hold / verify first** | Independently confirm project identity, license, maintainers, current activity, and security model. Do not conflate it with HKUDS/OpenHarness. |
| [whiteguo233/OpenBiliClaw](https://github.com/whiteguo233/OpenBiliClaw) | Local-first, cross-platform content-discovery/personalization agent; supports a separate DeepSeek Harness plugin | **Out of scope for AURELIA** | No clear trading-engine benefit. Keep as an unrelated personal discovery application; do not connect trading credentials, strategy data, or broker accounts. |

## Recommended adoption order

### Wave 1 — low-coupling engineering improvements
1. Evaluate Open Code Review on a redacted patch snapshot; compare findings with human review and deterministic linters/tests.
2. Evaluate Better Harness in read-only/no-session mode to identify evidence gaps in the agent work loop.
3. Compare OpenAI Agents SDK and Strands Harness SDK using a small, non-capital prototype. Pick at most one for that prototype; do not add both to the production runtime.

### Wave 2 — only if a measured need exists
4. Assess OpenHarness, Archon, and MiniMax Code for engineering workflow automation in disposable worktrees.
5. Assess OpenLit only after telemetry and data-minimization requirements are documented.
6. Assess OpenWolf only if cross-agent project memory is a demonstrated gap and its AGPL-3.0 implications are accepted.

### Hold / defer
- Full Harness platform, TrueForge, Vercel eve, OpenAgent and Browser Harness: require a specific use case and isolation design before deeper evaluation.
- DeepCode, HarnessRouter, CyberStrike, and thu-nmrc/OpenHarness: verify repository identity and source-level scope first.
- OpenBiliClaw: unrelated to the canonical trading engine.

## Required evidence before a candidate is promoted

For each candidate, add a separate record with:
- canonical URL, owner/name, default branch, exact reviewed commit SHA and review timestamp;
- license and dependency/SBOM scan;
- installation-script and network-egress review;
- secret access, filesystem access, subprocess, browser/CDP, MCP and tool-permission matrix;
- reproducible build/test output in an isolated environment;
- threat model, limitations and explicit use-case justification;
- reviewer sign-off and rollback plan.

Only after these are complete should a candidate be considered for the external-repository registry. Registry entry means non-authoritative availability only; it does not imply installation, agent connectivity, or capital authority.

## Source links reviewed

- OpenHarness: https://github.com/HKUDS/OpenHarness
- Harness platform: https://github.com/harness/harness
- Open Code Review: https://github.com/alibaba/open-code-review
- OpenAI Agents SDK: https://github.com/openai/openai-agents-python
- Browser Harness: https://github.com/browser-use/browser-harness
- Strands Harness SDK: https://github.com/strands-agents/harness-sdk
- DeepCode: https://github.com/HKUDS/DeepCode
- MiniMax Code: https://github.com/MiniMax-AI/minimax-code
- Archon: https://github.com/coleam00/Archon
- HarnessRouter: https://github.com/HarnessRouter/harnessrouter
- Better Harness: https://github.com/QoderAI/better-harness
- OpenLIT: https://github.com/openlit/openlit
- TrueForge: https://github.com/truefoundry/trueforge
- CyberStrike: https://github.com/CyberStrikeus/CyberStrike
- eve: https://github.com/vercel/eve
- OpenAgent: https://github.com/the-open-agent/openagent
- OpenWolf: https://github.com/cytostack/openwolf
- thu-nmrc/OpenHarness: https://github.com/thu-nmrc/OpenHarness
- OpenBiliClaw: https://github.com/whiteguo233/OpenBiliClaw

## Honest completion status

Completed here: first-pass triage and staged adoption recommendations. Not completed: exact commit pinning for all 19 projects, source/dependency security audits, isolated runtime tests, license counsel, integration, CI evidence, or independent approval. No repository has been installed or activated by this triage. AURELIA's live lock and capital controls must remain unchanged.
