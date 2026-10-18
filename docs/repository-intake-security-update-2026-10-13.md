# Repository Intake — Security Findings Update (2026-10-13)

This update records targeted public-source checks after the initial README review. These are upstream public reports/documentation, not a local vulnerability scan. Version-specific applicability must be checked against the exact upstream commit/package selected for any future test.

## Blocking findings

### siteboon/claudecodeui — do not deploy or install into a privileged environment

GitHub's repository security page lists three critical advisories: shell command injection in Git user routes (GHSA-7fv4-fmmc-86g2), unauthenticated RCE via WebSocket shell injection (GHSA-gv8f-wpm2-m5wr), and command injection via Git endpoint (GHSA-f2fc-vc88-6w7q). One advisory states affected versions <=1.24.0 with patched version 1.25.0; another states <=1.23.0 with patched version 1.24.0. Do not infer that the repository's current default branch is safe merely because patches are listed. Verify the exact package version, all advisories, and regression tests before reconsideration.

Sources:
- https://github.com/siteboon/claudecodeui/security
- https://github.com/siteboon/claudecodeui/security/advisories/GHSA-gv8f-wpm2-m5wr
- https://github.com/siteboon/claudecodeui/security/advisories/GHSA-7fv4-fmmc-86g2

### d-kimuson/claude-code-viewer — do not expose remotely without explicit authentication

The upstream README states the default hostname is localhost, but if no password is configured, authentication is disabled and the application is publicly accessible. If evaluated, bind to loopback, require authentication, keep it behind an authenticated private access layer for remote use, and disable chat/session-control features until permissions and data handling are verified.

Source: https://github.com/d-kimuson/claude-code-viewer

### cyberchitta/scrapling-fetch-mcp and D4Vinci/Scrapling — network isolation is a hard gate

The fetch MCP README says it retrieves bot-protected sites through browser/network components. Scrapling documentation describes HTTP transport authentication options and warns against unauthenticated HTTP listening on a network-accessible interface. Public issue reports also discuss SSRF/internal-network access risks. This is sufficient to require isolation, not sufficient to conclude the latest release is vulnerable.

Required controls: use stdio/local mode unless HTTP is necessary; require a token for HTTP; do not bind unauthenticated services to 0.0.0.0; block loopback, private, link-local and cloud metadata addresses; revalidate redirect targets and DNS resolutions; cap response size, duration and concurrency; enforce an outbound firewall and domain allowlist; treat page contents as untrusted.

Sources:
- https://github.com/cyberchitta/scrapling-fetch-mcp
- https://github.com/D4Vinci/Scrapling/blob/main/docs/ai/mcp-server.md
- https://github.com/D4Vinci/Scrapling/issues/413
- https://github.com/D4Vinci/Scrapling/issues/293

### pasky/chrome-cdp-skill — use only with a disposable browser profile

The project explicitly connects to the user's live Chrome session and can inspect logged-in pages and evaluate JavaScript in page context. No repository security policy is listed on its GitHub security page. This does not prove a vulnerability, but the capability is too privileged for a browser profile containing broker sessions, personal email, password managers, or production credentials. Use a dedicated clean profile and explicit approval before enabling CDP.

Sources:
- https://github.com/pasky/chrome-cdp-skill
- https://github.com/pasky/chrome-cdp-skill/security

## Updated dispositions

- **BLOCK:** claudecodeui until version-specific advisory remediation and regression evidence are verified.
- **HOLD:** claude-code-viewer until authentication and remote exposure are explicitly configured and tested.
- **HOLD:** Scrapling and scrapling-fetch-mcp until SSRF/network egress boundaries and transport authentication are tested.
- **HOLD:** chrome-cdp-skill until isolated browser-profile controls are demonstrated.
- **REVIEW SELECTIVELY:** anthropics/claude-quickstarts and claude-code-showcase; demos/hooks remain untrusted until inspected.
- **CONDITIONAL:** claude-code-java only if Java is actually used.
- **RESEARCH ONLY:** Intel AutoRound; require reproducible benchmarks before any model routing change.
- **OUTSIDE TRADING RUNTIME:** Platinum SEO Engine; separate marketing workspace and license review.

## Remaining evidence gap

No upstream repository was executed or installed. No local scanner, dependency audit, penetration test, regression test or agent-environment check has been performed. The pull request remains a draft documentation PR. These findings do not authorize production deployment, agent installation, broker access, or live trading.
