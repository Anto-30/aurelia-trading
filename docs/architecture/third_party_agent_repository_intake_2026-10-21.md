# Third-party agent repository intake and integration decisions

**Status:** preliminary repository-intake ADR; not a source-code security audit.
**Date:** 2026-10-21
**Canonical system:** AURELIA / ATOS in `Anto-30/aurelia-trading`.
**Decision:** no third-party runtime, agent, bridge, model, skill, or capital-control code is imported by this change.

## Governing constraints

AURELIA remains the only canonical execution and capital plane. Research models, coding agents, MCP servers, skills, messaging bridges, and external repositories may provide proposals or evidence, but they must not authorize capital, change risk limits, bypass the execution firewall, modify the canonical live lock, or resubmit orders. Deterministic risk and release authorities remain inside AURELIA.

The canonical `config/LIVE_LOCK.yaml` on `main` remains authoritative and fail-closed. Any future integration must be pinned to an immutable commit, license-reviewed, SBOM/dependency-scanned, secret-scanned, tested in isolation, and admitted through a separate reviewed PR. No `curl | sh`, unpinned `npx @latest`, global skill install, plugin install, or remote-control bridge is approved by this document.

This intake was based on repository metadata and README-level review of the 19 user-supplied public repositories. It did **not** clone or execute the repositories, inspect every source file, run their test suites, verify published binaries, or complete a license/security audit. A candidate designation is not a security approval.

## Repository-by-repository disposition

| Repository | What it appears to provide | Disposition for AURELIA |
|---|---|---|
| [can1357/oh-my-pi](https://github.com/can1357/oh-my-pi) | Local coding-agent harness with shell, tools, LSP/debugger, extensions, subagents, and MCP integrations. | **Developer-only candidate, not production runtime.** Review approval defaults, project hooks/extensions/MCP loading, shell privileges, and sandboxing. Use only in a disposable VM/container with always-ask permissions and no broker or deployment secrets; pin a release/commit before any trial. |
| [shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos) | Financial-candlestick foundation model trained on OHLCV sequences. | **Offline research candidate only.** Do not connect to execution. AURELIA's Deriv synthetic-index candle feed does not supply ordinary exchange volume; the existing pipeline intentionally leaves volume missing. No fit or performance claim is allowed until input semantics, preprocessing, model weights/license, time alignment, and leakage are verified. |
| [rubrikinc/kronos](https://github.com/rubrikinc/kronos) | Distributed monotonic time service/library for clustered systems. | **Not an agent or market model.** No current integration need identified. Consider only as infrastructure if an actual multi-node clock-ordering requirement is documented and its operations/failure modes are reviewed. |
| [ruvnet/ruflo](https://github.com/ruvnet/ruflo) | Agent meta-harness/plugins/MCP for Claude Code and Codex. | **Developer sandbox candidate only.** Its plugins and mods run with the host account's permissions. No production worker, broker credentials, release authority, or direct capital-plane access. Pin and inspect each plugin/MCP tool independently. |
| [ANative-Lab/Awesome-Self-Evolving-Agents](https://github.com/ANative-Lab/Awesome-Self-Evolving-Agents) | Survey and catalog of self-evolving-agent papers/projects. | **Reference material only.** No runtime dependency. Treat cited projects as leads requiring their own independent review. |
| [strands-agents/box](https://github.com/strands-agents/box) | OS sandbox engine for AI agents with policy controls. | **Highest-priority isolation proof-of-concept candidate.** Before use, review sandbox backend, privilege boundaries, mount policy, network egress, persistence, and failure-closed behavior. Prove that host secrets, Docker sockets, GitHub credentials, and Deriv tokens are inaccessible. Not yet a trusted security boundary. |
| [sylvesterkaczmarek/agent-boundary-check](https://github.com/sylvesterkaczmarek/agent-boundary-check) | CLI measuring effective agent read/write/execute/network boundary using synthetic canaries. | **Security-test candidate for a non-secret CI job.** Useful as diagnostic evidence only; its result cannot replace container hardening, threat modeling, or an independent security review. Run in a disposable environment and ensure canaries contain no real secrets. |
| [google/skill-reach](https://github.com/google/skill-reach) | Evaluation suite for agent skill routing, collisions, and multi-step tool trajectories. | **CI/evaluation candidate.** Can measure whether routing chooses the intended skill without redundant tool calls. No runtime capital permissions; pin dependencies and run with synthetic fixtures/no credentials. |
| [china-qijizhifeng/agentic-harness-engineering](https://github.com/china-qijizhifeng/agentic-harness-engineering) | Research framework for observability-driven optimization/evolution of coding-agent harnesses. | **Offline research only.** Harness optimization must never edit the canonical execution/risk/release controls automatically. Any generated patch requires a separate branch, tests, human review, and immutable evidence. Review remote sandbox/service dependencies before use. |
| [LilMGenius/paperthin](https://github.com/LilMGenius/paperthin) | Cross-agent skill catalog and installer/updater. | **Do not install globally or auto-update into AURELIA.** Individually review the exact skill files, licensing, shell/network effects, and prompt instructions; vendor only approved, pinned, minimal skills with provenance. |
| [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | Context compression/retrieval layer with local and MCP interfaces. | **Evaluation candidate after safety-preservation tests.** Verify system/developer rules, risk thresholds, broker identifiers, evidence hashes, and tool permissions are preserved exactly; test adversarial prompts and truncation. No external transmission of proprietary or account data without a separate data-flow review. |
| [Derpyu520/qq-bridge](https://github.com/Derpyu520/qq-bridge) | QQ messaging bridge into an agent harness, with session/authentication and tool-approval messages. | **Do not use for trading control or production commands.** A messaging bridge is a remote-control boundary. If ever considered for notifications, restrict it to outbound, sanitized status messages; no inbound execution commands, tokens, account data, or order intents. |
| [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) | Gives agents internet/search/browser/data-collection capabilities and installs connectors. | **Research sandbox only; not production.** External retrieval creates prompt-injection and exfiltration risks. Disable access to environment variables, secrets, local sensitive files, internal services, and unrestricted shell. All retrieved content is untrusted data, never instructions. |
| [raysonmeng/agent-bridge](https://github.com/raysonmeng/agent-bridge) | Local bidirectional Claude Code/Codex collaboration and cross-review bridge. | **Developer-only candidate.** Cross-review can suggest defects but is not independent authorization or proof. No unattended write/deploy capability; require human approval for mutations and keep agent credentials separated. |
| [areal-project/AReaL](https://github.com/areal-project/AReaL) | Large-scale asynchronous reinforcement-learning training infrastructure. | **Separate offline research/training environment only.** Not a production trading runtime and not required for the current release gates. Training must use approved datasets, no broker tokens, reproducible seeds/checkpoints, held-out evaluation, and explicit model provenance. |
| [shafiqahmed-786/ruflow-ai](https://github.com/shafiqahmed-786/ruflow-ai) | Resume/job-application multi-agent pipeline with web app and vector database. | **Out of scope; do not integrate.** No material AURELIA capability identified that justifies its dependencies and service surface. |
| [zarazhangrui/lark-coding-agent-bridge](https://github.com/zarazhangrui/lark-coding-agent-bridge) | Feishu/Lark bot that forwards messages, files, workspace changes, and commands to local coding agents. | **Do not connect to production AURELIA.** Inbound messaging, file transfer, workspace switching, and agent commands widen the control plane. A future notification-only use would require outbound-only design, ACL review, redaction, and no action execution. |
| [SeemSeam/claude_codex_bridge](https://github.com/SeemSeam/claude_codex_bridge) | Multi-agent CLI/TUI collaboration, remote/mobile control, and cross-provider orchestration. | **Developer-only candidate, not a release authority.** Keep remote control disabled for production hosts; no credentials, deploy rights, risk overrides, or order submission. Pin and audit protocol/session boundaries before trial. |
| [kronosnet/kronosnet](https://github.com/kronosnet/kronosnet) | Cluster communication/high-availability networking library with GPL/LGPL components. | **Not an agent framework; no current integration.** If later required for deployment networking, conduct platform/operations review and license compatibility analysis before linking or distributing it. |

## Prioritization

1. **Security validation first:** evaluate `agent-boundary-check` in an isolated CI job and assess Strands Box as a sandbox proof of concept. These are candidates, not trusted gates until independently validated.
2. **Agent evaluation next:** evaluate `skill-reach` using synthetic, deterministic tasks. Consider Headroom only after tests prove critical policy text and evidence metadata cannot be lost or altered.
3. **Research-only:** assess Kronos with Deriv-compatible inputs only after documenting its expected OHLCV schema and obtaining a valid volume strategy; use AReaL or harness-evolution work only in a separate research environment.
4. **Developer convenience only:** oh-my-pi, Ruflo, AgentBridge, and Claude/Codex bridge can be tested in disposable developer environments with no production secrets or execution access.
5. **No import:** the survey/catalog and unrelated job-intelligence, messaging, distributed-clock, and cluster-network projects do not currently justify production dependencies.

## Mandatory admission checklist for any future candidate

- [ ] Immutable upstream commit/tag and source archive hash recorded.
- [ ] License and all transitive/embedded licenses checked for intended use.
- [ ] SBOM, dependency vulnerability scan, secret scan, static analysis, and relevant tests completed.
- [ ] Threat model documents files, shell, network, process, mount, MCP, messaging, and credential access.
- [ ] No secret, broker token, GitHub PAT, production environment, or Docker socket exposed to the candidate.
- [ ] Untrusted repository content and retrieved web content treated as data, never as system instructions.
- [ ] Runtime permissions are least-privilege; all writes and external actions are explicitly approved.
- [ ] No direct writes to risk settings, capital ledger, release gate, or `config/LIVE_LOCK.yaml`.
- [ ] AURELIA's deterministic risk engine, execution firewall, ledger/reconciliation, kill switch, and release authority remain canonical.
- [ ] Tests run in isolated CI; artifacts bind results to the exact commit and dataset hash.
- [ ] Independent human review approves the specific integration PR.
- [ ] Rollback and disable procedure is documented and tested.

## Release boundary

This ADR does not change strategy eligibility, production deployment, risk limits, or broker permissions. It does not mark any third-party repository safe or integrated. AURELIA remains in `VERIFY_ONLY`; `LIVE_EXECUTION=BLOCKED`; `FINAL_EXECUTION_AUTHORIZATION=false`. No live order or capital movement is authorized.
