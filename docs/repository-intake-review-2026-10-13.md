# Repository Intake — Source Review Addendum (2026-10-13)

This is a first-pass README review against each repository's default branch. Recorded SHA values are README blob SHAs, **not** upstream commit SHAs. No repository was cloned or executed, and no scanner or test suite was run.

## Findings

| Repository | README blob SHA | Observed scope | Decision |
|---|---|---|---|
| pasky/chrome-cdp-skill | `877d4d412b12d97304a524bde386027d7f99815a` | Connects an agent to the user's live Chrome session; supports page JavaScript evaluation, navigation, clicking, typing and raw CDP commands. | **Hold.** Do not enable on personal/authenticated sessions. Review scripts; use a disposable browser profile without logged-in accounts, broker portals or secrets. |
| anthropics/claude-quickstarts | `9cac84096b77c32521c718f5b507aa866ed232b1` | Example apps include customer support, financial analysis, browser use and computer-use demos; at least one toolset example is explicitly not production code. | **Reference only.** Select components individually; review API key handling, dependencies, shell and network permissions. |
| siteboon/claudecodeui | `d2e906c55fa2898e0ada8d9cbee63f4c4e00e8b9` | Desktop/mobile agent UI advertises chat, integrated shell, file explorer, Git operations and remote use. | **Blocked pending security review.** Verify current advisories, authentication/authorization, process spawning, path traversal, WebSocket protections and network binding before staging. |
| ChrisWiles/claude-code-showcase | `43a3fad0ec37545d1039dec81561e9515323de1e` | Claude Code skills, agents, hooks, test/format automation, scheduled GitHub Actions, MCP config and PR review automation. | **Pattern library only.** Inspect every hook/workflow; remove broad token scopes, unreviewed scheduled fixes and deployment permissions. |
| decebals/claude-code-java | `4a518847778e6d564e05d1ed77ffc6b075ef4a3b` | Java-specific Agent Skills, templates, MCP configs and setup scripts; README advertises MIT. | **Conditional / low priority.** Only if Java is in scope; prefer selective skills and inspect setup scripts. |
| d-kimuson/claude-code-viewer | `69ccaf6b50ecc6ec946ad46a45650964d3c93b7f` | Web client for sessions/history with integrated terminal. README flags vendor terms around Agent SDK chat sending and makes some actions opt-in. | **Observability evaluation only.** Review transcript storage, auth, remote exposure, terminal access and current terms. |
| intel/auto-round | `3e7e95219cb55888cc91705e19391dd6ad3610f0` | LLM/VLM post-training quantization toolkit; README advertises Apache-2.0 and Python 3.11+. | **Research benchmark only.** Not a trading strategy. Benchmark accuracy, calibration, latency, memory and hardware before changing model routing. |
| D4Vinci/Scrapling | `30425435c2f2833dfc5af7ea8e87aa8e926856bf` | Web scraping/extraction framework. | **Research ingestion candidate.** Review license/dependencies, parser isolation, network restrictions, rate limits, provenance and prompt-injection handling. |
| cyberchitta/scrapling-fetch-mcp | `0283b59290e79b0a6fe9370a71de1f5ac1547edf` | README labels Apache-2.0; MCP fetcher uses browser/network components to retrieve protected pages and provides fetch/extraction tools. | **Hold for MCP/network review.** Block private, loopback, link-local and metadata destinations; revalidate redirects; cap size/time/rate; read-only output; respect site terms and do not evade access controls. |
| popiliadam/platinum-seo-engine | `fff42794dc3724a7a9eeff4e27a1c3cc003decf2` | SEO plugin with skills, commands, hooks, MCP servers and append-only workflow state; README advertises AGPL-3.0 and notes some work-in-progress suites. | **Outside AURELIA.** Optional separate Tales and Trails Safaris marketing workspace after license/permission review; no trading-runtime integration. |

## Cross-cutting controls

1. Browser/CDP, terminal, file editing, Git write and remote UI capabilities are high privilege. Do not connect them to authenticated broker sessions or production secrets.
2. Scraped HTML is untrusted data, not instructions. It cannot authorize secret disclosure, file writes, configuration changes or orders.
3. Audit every hook, workflow trigger, command, token scope, artifact and network permission; apply least privilege and protected review.
4. Verify actual license files and transitive dependencies; README badges alone are insufficient. Pin immutable upstream commit SHAs and preserve notices.
5. None of these repositories may become AURELIA's capital authority, Risk Warden, Execution Firewall, broker source of truth, order router or release authority.

## Evidence status

**Verified:** README content fetched for all ten repositories; blob SHAs recorded above. This is a preliminary capability/risk assessment only.

**Not verified:** upstream commit SHAs, complete source trees, all license files, current security advisories, dependency health, exploitability, test results, installation, agent configuration, code integration, CI or production readiness.

## Remaining gates

- Resolve upstream default-branch commit SHAs.
- Inspect actual licenses, package manifests, install scripts, hooks, MCP definitions, CI workflows and entrypoints.
- Check current advisories and dependency vulnerabilities.
- Run static analysis, secret scanning and focused tests in an isolated environment.
- Submit only selected changes through reviewed PRs; do not auto-merge.
