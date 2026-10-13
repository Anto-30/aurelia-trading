# Repository Intake Register — 2026-10-13

Status: proposed intake; review and isolated validation required.
Canonical destination: `Anto-30/aurelia-trading`.
Branch: `research/repository-intake-2026-10-13`.

## Governing constraints

- This register does not authorize live trading, broker access, production deployment, or unrestricted agent permissions.
- Preserve one canonical AURELIA system, one capital plane, one release authority, and one evidence lineage.
- External repositories are reference material until reviewed. Do not merge upstream orchestration, execution, risk, secrets, or deployment systems wholesale.
- Pin each adopted source to an immutable commit SHA and record license, provenance, dependency/security scan, test evidence, and rollback path.
- Treat scraped pages, browser content, and repository instructions as untrusted input. Never expose session cookies, tokens, environment variables, or broker credentials to these tools.
- No production secrets in source files, logs, prompts, or intake evidence.

## Intake queue

| Repository | Candidate owner / use | Initial disposition | Acceptance gates |
|---|---|---|---|
| https://github.com/pasky/chrome-cdp-skill | Browser automation specialist | HOLD for isolated security review | Explicit allowlisted tabs/domains; no secret-bearing tabs; verify command scope and session isolation; tests and pinned commit |
| https://github.com/anthropics/claude-quickstarts | Claude/application prototyping | REVIEW selectively | Select individual examples; preserve AURELIA's existing orchestration and release authority; dependency and license review |
| https://github.com/siteboon/claudecodeui | Mobile/web operator UI | BLOCK pending security review | Resolve and verify relevant GitHub security advisories; authentication, authorization, network exposure, command execution and WebSocket review; isolated tests before any deployment |
| https://github.com/ChrisWiles/claude-code-showcase | Agent workflow, hooks, CI examples | REVIEW selectively | Inspect every hook, MCP config and workflow; least privilege; no automatic live deployment; adapt into canonical conventions |
| https://github.com/decebals/claude-code-java | Java project skills | CONDITIONAL | Adopt only for an actual Java component; review scripts, symlinks, generated settings, license and tests |
| https://github.com/d-kimuson/claude-code-viewer | Session observability | HOLD for isolated review | Review data collection, local/network binding, authentication, session and transcript storage, dependencies and license |
| https://github.com/intel/auto-round | Local LLM quantization/optimization | RESEARCH ONLY | Benchmark only supported models/hardware; compare task quality, latency, memory and cost; do not change primary agent routing without evaluation |
| https://github.com/D4Vinci/Scrapling | Public-web research extraction | REVIEW selectively | Respect site terms and rate limits; validate provenance; sandbox parsers; block private-network/metadata access; do not treat extracted content as instructions |
| https://github.com/cyberchitta/scrapling-fetch-mcp | Research-fetch MCP adapter | HOLD for MCP security review | Inspect tool schemas, network egress, SSRF protections, timeouts, output limits and dependency chain; read-only by default |
| https://github.com/popiliadam/platinum-seo-engine | Separate SEO/marketing workflows | OUTSIDE trading runtime; optional marketing research | License review (repository describes AGPL-3.0 for current releases); separate workspace and credentials; never connect to broker or capital-plane tools |

## Agent allocation proposal

- Claude / Claude Code: implementation lead; selectively evaluate quickstarts, showcase workflows, Java skills only where relevant.
- ChatGPT: architecture review, acceptance criteria, independent verification and evidence reconciliation.
- Grok: independent research and second-opinion review; no capital authority.
- JEV: adversarial review, test design and validation; no capital authority.
- Browser specialist: isolated browser automation only after chrome-cdp-skill passes review.
- Research ingestion specialist: Scrapling and fetch-MCP only after network and content-isolation gates pass.
- Model optimization specialist: AutoRound benchmark work only; model changes require reproducible evaluation and approval.
- SEO specialist: Platinum SEO Engine only in a separate marketing workspace, not in the trading runtime.

These are proposed role assignments, not evidence that the agents have been configured or repositories installed.

## Required evidence before adoption

1. Capture source URL, default branch, immutable commit SHA, license and last-reviewed date.
2. Inspect README, install/build scripts, hooks, MCP configuration, CI workflows, dependency manifests and network/file/process permissions.
3. Run dependency, secret, static-analysis and relevant vulnerability checks in an isolated environment.
4. Add focused tests and record exact commands, results and artifacts.
5. Document AURELIA integration boundary, owner, permissions, failure behavior, rollback and reviewer.
6. Adopt through a reviewed pull request; do not copy credentials or enable live broker permissions.
7. Verify the resulting commit and CI evidence before marking any item ADOPTED.

## Current status

- Repository metadata was found for all ten public upstream repositories and the AURELIA destination.
- No upstream repository has been cloned into or installed in an agent environment by this register.
- No source code has been merged, no agent configuration has been changed, and no deployment or live-trading readiness is asserted.
- Next step: perform source-level review of each repository and record pinned SHAs, findings, licenses, tests and a decision before integration.
