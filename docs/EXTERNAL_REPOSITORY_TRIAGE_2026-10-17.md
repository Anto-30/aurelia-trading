# External Repository Triage and Integration Plan — 2026-10-17

## Scope and evidence level

This is a source-backed first-pass triage of the 12 unique repositories supplied by the project owner. The `earendil-works/pi` URL was duplicated in the submitted list, so it is counted once. The public README files and GitHub repository metadata were inspected through GitHub's read interface. This is **not** a local clone, dependency/SBOM scan, static-analysis run, test run, or complete license audit. No third-party code has been copied into AURELIA.

The decision is to retain one canonical AURELIA system and evaluate components selectively. Do not create twelve sidecar systems and do not grant any LLM or agent authority over the capital plane.

## Triage matrix

| Repository | Relevant capability | Current decision | Required checks / caveats |
|---|---|---|---|
| [RoversX/ThinkTerm](https://github.com/RoversX/ThinkTerm) | Rust terminal multiplexer; persistent local/remote sessions for coding agents | Optional operator workstation tool; not a runtime dependency | Android/iOS clients are in development; host must remain available for sessions. Review remote access, SSH trust, update path and permissions before use. |
| [raroque/boop-agent](https://github.com/raroque/boop-agent) | Personal agent, dispatcher/workers, memory and automations; Claude or Codex runtime | Reuse patterns only; do not deploy as-is | README explicitly calls it a starting point and warns it is not optimized for cost/security. iMessage/Sendblue and Mac-oriented integrations are not a fit for a phone-only AURELIA production dependency. Review third-party integrations and outbound action approvals. |
| [xerj-org/xerj](https://github.com/xerj-org/xerj) | Local code/document search, hybrid BM25/vector retrieval, agent memory, MCP | Candidate for offline/local code retrieval pilot | Its README warns that `--insecure` disables TLS and API-key authentication; never expose that mode on a non-loopback interface. Verify binary provenance, sandboxing, indexing scope, data deletion and license before use. |
| [CopilotKit/OpenBot](https://github.com/CopilotKit/OpenBot) | Self-hosted AI coworker template with browser/files/tools and action audit trail | Do not adopt as a core dependency; consider isolated UI/operator experiment only | Repository labels itself alpha/template. README says `OPENBOT_SINGLE_USER=true` admits every request as an administrator; disable and configure authentication before any shared deployment. Review browser/file permissions and model credential handling. |
| [superlinked/sie](https://github.com/superlinked/sie) | Self-hosted inference server for search, retrieval, document conversion, structured output and other model tasks | Defer until a measured model-serving need and viable host exist | Apache-2.0 badge in README; verify each model's own license. Measure RAM/VRAM, latency, model downloads, storage, egress and operating cost. Do not add a cluster to a free-only deployment without cost validation. |
| [earendil-works/pi](https://github.com/earendil-works/pi) | TypeScript agent toolkit, unified LLM API, agent loop, CLI/RPC/SDK | Preferred candidate for a bounded research-agent harness evaluation; not an execution authority | README indicates an active multi-package project with pinned dependency/build checks; inspect package boundaries, extension/tool permissions, provider data handling and license at the exact commit before adoption. Keep any shell/file tools sandboxed and read-only by default. |
| [anandanand84/technicalindicators](https://github.com/anandanand84/technicalindicators) | TypeScript/JavaScript technical-analysis indicators and pattern recognition | Candidate for parity tests only; do not replace canonical indicator calculations yet | README's installation guidance is old (Node.js >=10); verify maintenance, runtime compatibility, license and numerical behavior. Build golden-vector tests against AURELIA's Python/reference calculations, including warm-up, NaN/missing values, candle ordering and edge cases. No trade signals should be imported without independent validation. |
| [manu354/cryptocurrency-arbitrage](https://github.com/manu354/cryptocurrency-arbitrage) | Legacy Node.js cross-market price spread scanner | Research reference only; do not deploy | README says the maintained trading-bot code is private and the public project is no longer the author's focus. README lists GPL-3.0; assess copyleft obligations before copying or linking code. Old dependencies and stale exchange assumptions require review. Fees, transfer delays, liquidity, slippage and withdrawal constraints are not established by a displayed spread. |
| [nightly-labs/openbot](https://github.com/nightly-labs/openbot) | Local-first desktop agent workspace supporting several coding-agent CLIs | Do not use in production or with trading permissions | README identifies a development preview and warns agents currently run with `danger-full-access` and `approvalPolicy: never`. README badge identifies PolyForm Noncommercial 1.0.0; this is a material restriction for commercial use. Do not install until licensing and permissions are resolved. |
| [JerBouma/AlgorithmicTrading](https://github.com/JerBouma/AlgorithmicTrading) | Dual-listing, options and statistical arbitrage educational projects | Research/reading reference only; no direct strategy promotion | README explicitly warns that speed-sensitive arbitrage may require C++ and nanosecond connectivity and is not feasible for retail investors. Inspect individual notebooks, assumptions and file licenses. No evidence of edge on Deriv synthetic indices or AURELIA's target instruments. |
| [regnull/openbot](https://github.com/regnull/openbot) | Self-hosted persistent multi-bot actor/inbox workflows, memory, MCP and approvals | Candidate for architecture comparison; not to be deployed as-is | README indicates MIT, Python 3.12+ and Node 24+; validate host compatibility. It explicitly states `run_shell` is not sandboxed. Enforce tool allowlists, workspace confinement, hop/concurrency limits, authenticated webhooks and human approval for external actions. |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | Claude Code plugin marketplace with commands, skills, agents and MCP definitions | Use as a discovery catalogue only; install individual plugins only after review | Upstream README explicitly warns that plugins may include third-party MCP servers/software and may change. Review the individual plugin's source, license, network access, secrets handling and permissions; pin the source commit. The marketplace's presence is not a security certification. |

## Recommended architecture

1. Keep AURELIA's existing research, deterministic risk engine, execution firewall, broker verification, ledger/reconciliation, release authority and kill switch as the sole capital/execution path.
2. Evaluate Pi only as a replaceable research-agent harness behind a narrow interface. Agents may propose experiments, summarize evidence and create reviewable patches; they must not hold broker credentials or submit orders.
3. Evaluate XERJ as a local retrieval tool only after the security model is checked. Use it to search indexed source code and research notes, not to make execution decisions.
4. Evaluate `technicalindicators` with golden-vector parity tests. Keep the current canonical implementation until numerical parity and licensing are established.
5. Treat the two OpenBot projects as distinct repositories with distinct licenses and security profiles. Do not merge or confuse them.
6. Treat SIE as optional infrastructure, not an automatic dependency. No cluster or paid resource should be created without explicit budget approval and a costed deployment plan.
7. Keep external arbitrage projects as educational references. Never infer profitability from README claims or historical examples.

## Validation plan before any code reuse

- Record repository URL, exact commit SHA, release/tag, license and license of transitive assets/models.
- Inspect `LICENSE`, `SECURITY.md`, package manifests/lockfiles, install scripts, CI workflows, shell commands, network destinations and secret-handling code.
- Produce an SBOM and scan dependency vulnerabilities, secrets, malware indicators and known CVEs using pinned tool versions.
- Run tests in an isolated, unprivileged environment with no broker credentials and no write access to AURELIA production configuration.
- Add narrow adapter tests and golden vectors; compare numerical outputs and failure behavior against canonical AURELIA implementations.
- Require deterministic reproduction, data provenance, time-order/no-lookahead checks, realistic costs, out-of-sample/walk-forward evaluation and independent review for any trading research result.
- Integrate only through a reviewed pull request; no direct commit to `main`, no silent dependency updates and no automatic merge based solely on an agent's approval.

## Current AURELIA governance observations

At inspection time, GitHub reported the `main` branch as **unprotected** with required status checks disabled. This is a control gap and must be resolved by an authorized repository owner before production release. The default branch head observed was `29236aadb257dcd14bd9ba0b7d19127e4545cad8`.

Open PR #153, "security: harden Deriv account binding and WebSocket shutdown", was observed as a draft. Its body reports exact-head assurance success but says independent human review remains pending. Do not merge it based on this repository-triage document. Review PR #153 and any related security PRs separately against their exact current heads and the project release policy.

## Explicit non-achievements

This report does not claim that the repositories were cloned, built, tested, scanned, installed, benchmarked, or integrated. It does not claim a strategy is profitable or qualified. No live trading was enabled, no broker action was taken, no credential was accessed or copied, no deployment was created, and no production gate was changed.

## Sources

- https://github.com/RoversX/ThinkTerm
- https://github.com/raroque/boop-agent
- https://github.com/xerj-org/xerj
- https://github.com/CopilotKit/OpenBot
- https://github.com/superlinked/sie
- https://github.com/earendil-works/pi
- https://github.com/anandanand84/technicalindicators
- https://github.com/manu354/cryptocurrency-arbitrage
- https://github.com/nightly-labs/openbot
- https://github.com/JerBouma/AlgorithmicTrading
- https://github.com/regnull/openbot
- https://github.com/anthropics/claude-plugins-official
