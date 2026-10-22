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
| [harness/harness](https://github.com/harness/harness) | Full developer platform: source control, CI/CD, dev environments, artifact registry | **Defer** | Larger infrastructure footprint than the current agent-orchestration need. Its quick-start mounts `/var/run/docker.sock` and persistent data; any evaluation needs a dedicated isolated host, no production secrets, and a reviewed Docker privilege boundary. |
| [alibaba/open-code-review](https://github.com/alibaba/open-code-review) | LLM-assisted CLI code review with line-level findings and deterministic checks | **Priority candidate** for isolated PR review | Run read-only against a patch copy first; redact secrets and sensitive data before model submission; verify rule coverage and false-positive/negative behavior. |
| [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | Python agent SDK with tools, handoffs, guardrails, human-in-loop and tracing | **Priority candidate** as a framework reference | Do not replace AURELIA's deterministic risk/capital plane. Prototype only in a separate non-capital process with strict tool allowlists. |
| [browser-use/browser-harness](https://github.com/browser-use/browser-harness) | LLM-driven browser automation over CDP, with generated helpers and optional cloud scale | **Restricted sandbox evaluation only** | Browser sessions can expose authenticated websites. No production browser profile, credentialed broker UI, trading actions, downloads, or recordings by default. |
| [strands-agents/harness-sdk](https://github.com/strands-agents/harness-sdk) | Python/TypeScript agent SDK with MCP, tools, skills and framework scaffolding | **License verification required before trial** | The README calls the SDK open source, but the root `LICENSE` path returned `NOT_FOUND` in this inspection. Locate and verify the canonical license, dependency graph and sandbox behavior before testing; then compare with OpenAI Agents SDK and choose at most one for a non-capital prototype. |
| [HKUDS/DeepCode](https://github.com/HKUDS/DeepCode) | Multi-agent coding assistant positioned for repository-grounded implementation/research; README describes visual workspaces, goal-driven loops, evidence-driven completion, durable sessions, reusable skills and explicit permissions | **Developer-only candidate; source review required** | The root `LICENSE` inspected on the default branch is MIT. Inspect installation scripts, permission enforcement, child-process/network behavior, MCP/skill loading and dependencies; no production secrets or autonomous changes to canonical trading controls. |
| [MiniMax-AI/minimax-code](https://github.com/MiniMax-AI/minimax-code) | Terminal coding agent with model/provider choice, tools, subagents and sandbox/permission controls | **Optional engineering-host candidate** | Do not make it a persistent AURELIA daemon. Test permission enforcement, shell/network restrictions, telemetry, and credential isolation. |
| [coleam00/Archon](https://github.com/coleam00/Archon) | Workflow/harness builder for deterministic, repeatable AI coding | **Evaluate as developer workflow tooling** | Use isolated worktrees and reviewable plans. Confirm commands, hooks, generated files, and provider installation behavior before project use. |
| [HarnessRouter/harnessrouter](https://github.com/HarnessRouter/harnessrouter) | Unified API/router for agent harnesses, documenting UHP and an OpenAI Responses-compatible API with persistent sessions, streaming, files/artifacts, cancellation and structured failures | **Conditional separate-host prototype only** | README states the entrypoint and runner require root to manage per-session users and describes Docker-backed deployment. Treat this as privileged multi-tenant infrastructure: check auth, session isolation, cancellation, network egress and cleanup before testing. No shared broker credentials, writable AURELIA checkout or capital authority. |
| [QoderAI/better-harness](https://github.com/QoderAI/better-harness) | Evidence-oriented analysis of coding-agent workflows, task episodes, validation and delivery | **Priority candidate** for process audit | Its reports can inform engineering improvements but are not causal proof or a substitute for CI, review, or release gates. Use read-only/no-session mode first. |
| [openlit/openlit](https://github.com/openlit/openlit) | Observability/telemetry for LLM applications | **Evaluate after privacy review** | Confirm data collection, exporters, retention, redaction, and outbound network behavior. Never send broker secrets, account identifiers, or sensitive trading payloads. |
| [truefoundry/trueforge](https://github.com/truefoundry/trueforge) | Agent execution harness with MCP tools, skills, sandboxing, approvals and session state | **Compare; do not stack by default** | Local mode is documented as local-only and without login by default. Keep bound to localhost; assess auth and isolation before any shared deployment. |
| [CyberStrikeus/CyberStrike](https://github.com/CyberStrikeus/CyberStrike) | Offensive AI penetration-testing/red-team CLI; README advertises reconnaissance, vulnerability discovery, exploitation and post-exploitation workflows | **Out of scope for production AURELIA; defensive lab only if explicitly needed** | Do not run against external systems or AURELIA infrastructure without explicit authorization. Inspect license, install paths, skills/tools and network/execution controls in a disposable isolated lab; never provide production tokens or deploy permissions. |
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

## Source snapshot identifiers

The following are GitHub content **blob SHAs for the README.md files returned from each repository's default branch during this inspection**. These are not repository commit SHAs, release signatures, or security attestations. Exact source commit pins are still required before testing or adoption.

| Repository | Ref inspected | README blob SHA |
|---|---|---|
| [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness) | `main` | `c99de34235be4b9077a38c12beae225755c59127` |
| [harness/harness](https://github.com/harness/harness) | `main` | `43f09714b35603aad45d249171d8aeb52696604c` |
| [alibaba/open-code-review](https://github.com/alibaba/open-code-review) | `main` | `96b4e231298af0882d800d213b5f5881f601fdd9` |
| [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | `main` | `40f490c110cd584f7034bd221c6da37379fc41ff` |
| [browser-use/browser-harness](https://github.com/browser-use/browser-harness) | `main` | `96aaf211a58098d827da960acdd8f2d2cbdc396a` |
| [strands-agents/harness-sdk](https://github.com/strands-agents/harness-sdk) | `main` | `8deea9e1814068770e52cd91e729422eaa319a7e` |
| [HKUDS/DeepCode](https://github.com/HKUDS/DeepCode) | `main` | `536ac18b958e7da89b7f313c25f0c0fc88982fae` |
| [MiniMax-AI/minimax-code](https://github.com/MiniMax-AI/minimax-code) | `main` | `11e2a0e7165c99b882b6a0ec5b6a3004c34b56c1` |
| [coleam00/Archon](https://github.com/coleam00/Archon) | `dev` | `e27d7bca33a053c1fbdbc8340bf8cc48c6341484` |
| [HarnessRouter/harnessrouter](https://github.com/HarnessRouter/harnessrouter) | `main` | `8e4d318042504dde8e9911184f038aab8beb8b11` |
| [QoderAI/better-harness](https://github.com/QoderAI/better-harness) | `main` | `282656e456a0883c90b38bd5d062d57362dcc43e` |
| [openlit/openlit](https://github.com/openlit/openlit) | `main` | `500492467130d6dc772b0480fe8354254ddb3d68` |
| [truefoundry/trueforge](https://github.com/truefoundry/trueforge) | `main` | `abd80bd5c535490cfbb54f9bcc383f9da05e0a2d` |
| [CyberStrikeus/CyberStrike](https://github.com/CyberStrikeus/CyberStrike) | `main` | `f25d9ee208855ff4c30ed982f99d5fb06d3f0cb9` |
| [vercel/eve](https://github.com/vercel/eve) | `main` | `65268d2e5ddccf4f1317a42ece2b567287360286` |
| [the-open-agent/openagent](https://github.com/the-open-agent/openagent) | `master` | `64aac8f4a9d71e44e31415f74847bd07e3a50bac` |
| [cytostack/openwolf](https://github.com/cytostack/openwolf) | `main` | `dd58579c6ee4f86bd09a0c91cbd54edfb4ea4e17` |
| [thu-nmrc/OpenHarness](https://github.com/thu-nmrc/OpenHarness) | `main` | `68bb351a2ca728db46831ced16619a767787a577` |
| [whiteguo233/OpenBiliClaw](https://github.com/whiteguo233/OpenBiliClaw) | `main` | `eb4a26db57fcc6b03527d64152b4fc3f1f8ef229` |

## Honest completion status

Completed here: first-pass triage and staged adoption recommendations. Not completed: exact commit pinning for all 19 projects, source/dependency security audits, isolated runtime tests, license counsel, integration, CI evidence, or independent approval. No repository has been installed or activated by this triage. AURELIA's live lock and capital controls must remain unchanged.
