# Pinned Source Spot Audit — Agent UI and Fetch MCP (2026-10-13)

This is a read-only source review at the exact upstream revisions recorded in the intake registry. It is not a full code audit, dependency scan, install, execution test, or security certification.

## CloudCLI / claudecodeui

**Pinned upstream commit:** `7c3049fe8e157f12b7add3e496d8d2fe6fa5c014`  
**Package manifest:** `package.json` blob `7853ed0dd4dce2a4869d0d26ffd2ea38814b7d60`; package `@cloudcli-ai/cloudcli` version `1.37.4`; license `AGPL-3.0-or-later`.

### Positive evidence in inspected source
- `server/modules/auth/auth.middleware.ts` blob `da451961b526eeec9f9514316817287b4a9b376a`: JWT secret uses `process.env.JWT_SECRET || appConfigDb.getOrCreateJwtSecret()`, not the public hard-coded fallback described in GHSA-gv8f-wpm2-m5wr. The inspected WebSocket auth function verifies the token and checks that the user still exists in the database.
- `server/modules/git/git.routes.ts` blob `810ddf764f6a89548c129b816b37a141999ef138`: inspected helper invokes the injected process spawner with `shell: false`; commit, branch, file-path and remote-name validation helpers are present.
- `server/modules/user/user.routes.ts` delegates Git identity changes to a service dependency instead of constructing shell commands directly in the route.

### Security decision
These checks are consistent with important mitigations for the published command-injection/authentication advisories, but do **not** prove that every vulnerable path is fixed or that the package is safe. The exact pinned commit's broader shell/terminal, plugin, filesystem, session, authentication, and build paths have not all been audited; no regression suite was executed here. Keep `SANDBOX_ONLY` and `BLOCKED_PENDING_REGRESSION_TESTS_AND_FULL_SOURCE_REVIEW`. Do not install into AURELIA's production or credential-bearing environment. AGPL-3.0-or-later obligations require separate legal/compliance review before reuse or distribution.

Relevant advisories:
- GHSA-gv8f-wpm2-m5wr: https://github.com/advisories/GHSA-gv8f-wpm2-m5wr
- GHSA-7fv4-fmmc-86g2: https://github.com/advisories/GHSA-7fv4-fmmc-86g2
- GHSA-f2fc-vc88-6w7q: https://github.com/advisories/GHSA-f2fc-vc88-6w7q

## Scrapling Fetch MCP

**Pinned upstream commit:** `8ed4c0df0979ca758e6e13ae84e6cdbe129e1a7a`  
**Manifest:** `pyproject.toml` blob `c8fe879c95a910f7fde0f767fcce7a75810451f4`; version `0.2.5`; Python `>=3.10`; declared dependencies include MCP, Scrapling fetchers, cryptography, PyJWT, Starlette and other transitive packages.

### Observed controls and gaps
- `src/scrapling_fetch_mcp/mcp.py` blob `d3cde9c0a8f7c44ca0db6997cedc4bee3cb11b67` starts the MCP server using stdio transport. The inspected MCP entry point does not itself expose a network listener.
- `src/scrapling_fetch_mcp/_fetcher.py` blob `5a14a816f3b5b95f50018f2432f9d424522b1f5a` restricts URL schemes to HTTP/HTTPS and truncates returned content to a caller-selected character count.
- The inspected URL validation does **not** reject loopback, private, link-local, or cloud-metadata addresses, and does not itself show DNS pinning/revalidation or redirect-target checks. The fetcher passes the URL to Scrapling.
- The README explicitly describes retrieval from bot-protected websites. This creates policy and terms-of-service considerations; do not use it to bypass access controls or authentication.

### Security decision
Keep `SANDBOX_ONLY` and `BLOCKED_PENDING_SSRF_AUTH_AND_EGRESS_TESTS`. Before even a research-only runtime trial, add/verify URL and redirect checks that reject private/loopback/link-local/metadata IPs after DNS resolution and at every redirect, restrict egress to an explicit allowlist, enforce time/response-size/rate limits, and treat fetched page content as untrusted prompt-injection material. Produce an SBOM and full dependency/license/vulnerability report. Do not run it with broker credentials or access to internal control-plane endpoints.

## Remaining intake-wide work
- Fetch each file used for licensing and manifest decisions by its exact pinned commit; root-file spot checks do not replace transitive license review.
- Run secret scanning, SAST, dependency vulnerability scanning and SBOM generation for each candidate in an isolated environment.
- Run project-specific regression/security tests only after dependency review, with no broker secrets and no write access to the canonical AURELIA repository.
- Keep the PR draft and external-code execution deny-by-default until evidence and human review are complete.

## Non-claims
No repository was installed or executed by this review. No agent runtime was configured. No trading logic, LIVE_LOCK, broker configuration, production secrets, release authority, or capital plane was changed. These findings do not establish live-trading readiness.


## Claude Code Viewer

**Pinned upstream commit:** `9367cf006be9965c954e6cd36526f2195dce67ea`  
**Manifest:** `package.json` blob `9123f9001a1c36ab4242151915423280960751b2`; version `0.8.2`; license `MIT`. README blob `69ccaf6b50ecc6ec946ad46a45650964d3c93b7f`.

The README documents a default bind hostname of `localhost`, a password option (`--password`), and an explicit hostname option. It also documents an integrated terminal and live session/history visibility. The default localhost bind is a useful safe default, but it does not establish safety when operators configure a remote hostname. For any remote exposure, require explicit authentication, TLS/private network access, firewall/allowlisting, session and filesystem isolation, and tests that prove unauthenticated clients cannot read sessions or operate the terminal. Keep `SANDBOX_ONLY`; do not expose on a public interface or place in a broker-credential-bearing environment before those checks. No tests were run by this review.


## Chrome CDP Skill

**Pinned upstream commit:** `ffea76a24b0471663ddd9d9f24335bbc442b6266`  
**Manifest:** `package.json` blob `3c87071888c082482104ddc5557d2f42a8aec75c`; version `1.1.0`; license `MIT`. README blob `877d4d412b12d97304a524bde386027d7f99815a`.

The README explicitly says this tool connects to the user's live Chrome session and can read and interact with tabs that are already logged in. The command surface includes page JavaScript evaluation, navigation, clicks, typing, raw CDP passthrough and network-resource inspection. Chrome remote debugging must be enabled. This grants access to whatever authenticated pages the connected browser can reach, including internal tools.

Decision: keep `SANDBOX_ONLY`. Do not point it at a daily-use browser, any logged-in broker portal, production GitHub credentials, password manager, email, or AURELIA admin surfaces. If ever tested, use a disposable browser profile with no sessions, no saved secrets, restricted target allowlist, and remote-debugging access bound to loopback only. No runtime test was performed.


## CloudCLI follow-up: authentication mode and credential transport

A second pass over the same pinned `server/modules/auth/auth.middleware.ts` (blob `da451961b526eeec9f9514316817287b4a9b376a`) identified additional configuration-sensitive risks that need explicit regression tests:

- `validateApiKey` skips API-key validation entirely when `API_KEY` is unset. This may be intended for local OSS mode, but deployments must not assume the optional middleware provides a security boundary unless configuration is enforced and tested.
- In `IS_PLATFORM` mode, both HTTP and WebSocket authentication return the first database user without validating a bearer token. This may be a product-specific platform trust boundary, but it is a critical mode switch and must never be enabled accidentally in a self-hosted/remote deployment.
- The middleware accepts an authentication token from the query string for SSE endpoints. URL-carried bearer tokens can leak through access logs, browser history, telemetry, reverse proxies, or referrer propagation unless carefully constrained.
- The inspected code logs authentication failures. Verify logs never include bearer tokens, secrets, request URLs containing credentials, or other sensitive request context.
- The pinned `server/modules/agent/agent.routes.ts` (blob `07bfc81b2d76d0c30c55d188a75a354fe763ced2`) accepts the agent API key from either `x-api-key` or the URL query parameter `apiKey`. Query-string credentials can leak into access logs, browser history, proxy telemetry and referrer data. The agent router does have its own API-key database validation in self-hosted mode, so the separate optional global `API_KEY` middleware being unset does not by itself prove the agent endpoint is unauthenticated. Remove query-parameter key support where possible, redact credentials, and test the reverse-proxy boundary. The pinned `server/index.ts` (blob `98cd213a1489f7a5a127eb1788fd9e3844b1e498`) documents that `IS_PLATFORM` mode relies on an external proxy; verify the service is unreachable except through that authenticated proxy.

Required gates before reconsideration: fail startup for unsafe auth-mode/configuration combinations; tests for unset API_KEY, invalid/missing tokens, platform-mode behavior, WebSocket and SSE paths; verify query-token redaction and restrictive cache/referrer/logging headers; and test auth on every terminal, file, Git, plugin, session, and WebSocket route. The source spot check is not sufficient to establish route coverage.

**Decision unchanged:** `BLOCKED_PENDING_REGRESSION_TESTS_AND_FULL_SOURCE_REVIEW`; sandbox-only, no runtime installation. These are risks requiring verification, not a claim that the upstream project is exploitable in every deployment.


## Platinum SEO Engine: MCP command and hook risks

**Pinned upstream commit:** `ffdf24da84cd5d52f755f156707d9bd14f7c0135`  
**Inspected files:** `.mcp.json` blob `3d61ab1934052da771b9da042b0bdbb9bba094b3`; `.claude/settings.json` blob `976575dbb2eaa1f03c9d4f954a563e51b38fd81c`. The repository is AGPL-3.0.

The MCP configuration runs `bash -c`, sources a local `.env` into the child environment, then invokes package names through `npx -y`. It also includes a machine-specific absolute path under `/Users/apple/Downloads/` and local HTTP endpoints. These are not appropriate to copy into AURELIA's shared agent configuration: shell-based launch, environment inheritance and on-demand package resolution create an execution/supply-chain boundary that must be isolated and pinned.

The inspected Claude settings include command hooks that invoke a project-local script, run `npx prettier`, and automatically run `npm install` when a `package.json` file changes. These hooks can execute code in response to agent file edits and should not be imported wholesale into a trading repository. Before any adaptation, review every hook script and matcher, replace implicit package downloads with lockfile-verified installation in a disposable workspace, and test that secrets are not inherited or logged.

**Decision:** marketing reference only, separate workspace; do not copy its MCP configuration or hooks into AURELIA. Require legal review for AGPL reuse and a dedicated security review for any selected component. No commands were executed as part of this review.

## Claude Code Showcase: executable hook behavior

At pinned commit `a95518f0cb67e86230119da40429169bc4c35a6f`, the inspected `.claude/settings.json` blob `976575dbb2eaa1f03c9d4f954a563e51b38fd81c` contains command hooks for prompt submission and tool use. A post-edit hook invokes `npx prettier --write`; another hook invokes `npm install` automatically when a `package.json` file changes. This is an example configuration, not a passive collection of markdown prompts: importing it can cause shell commands and dependency installation during agent operations.

The root `LICENSE` path returned 404 at the pinned revision. That alone does not prove the repository has no license elsewhere, but reuse rights remain unconfirmed. **Decision:** keep reference-only, do not copy or redistribute code until license terms are established, and do not import the hook settings into AURELIA. Review hook scripts and package-install behavior independently even if a license is later found.


## Scrapling Fetch MCP: URL destination and resource-exhaustion follow-up

**Pinned upstream commit:** `8ed4c0df0979ca758e6e13ae84e6cdbe129e1a7a`  
**Inspected files:** `src/scrapling_fetch_mcp/_fetcher.py` blob `5a14a816f3b5b95f50018f2432f9d424522b1f5a`; `src/scrapling_fetch_mcp/_scrapling.py` blob `a39c9428deb89d9955194254096e2bfd5baa0531`; `src/scrapling_fetch_mcp/mcp.py` blob `d3cde9c0a8f7c44ca0db6997cedc4bee3cb11b67`.

A deeper read of the pinned fetch path confirms that `_require_web_url` checks only the URL scheme (`http` or `https`). In the inspected files, there is no destination-IP policy for loopback, private, link-local or cloud metadata ranges, nor an explicit redirect-target/DNS-rebinding check before the fetcher follows a destination. The actual guarantees of the transitive Scrapling fetchers have not been exhaustively established, so this is a missing application-level control requiring verification, not proof that every redirect is exploitable.

The pattern-search tool applies Python's regular-expression engine to the full fetched document using `list(compile(pattern).finditer(content))`. Output truncation happens after the search. The exposed tool arguments do not show explicit upper bounds for `search_pattern`, `context_chars`, `max_length`, or `start_index`. This creates a potential resource-exhaustion/regex-denial-of-service surface when a caller can supply adversarial patterns or extreme parameters; it needs bounded inputs, safer matching or execution time/resource limits, plus tests.

The server uses MCP stdio transport in the inspected entrypoint, which reduces network-listener exposure in that path but does not remove risks from a connected model/client requesting unsafe destinations or expensive patterns. Do not use it with broker credentials or trusted internal network access. Before reconsideration, test loopback/private/link-local/metadata URLs, redirects to forbidden targets, DNS changes between validation and connection, oversized arguments, pathological regex patterns, response-size limits, fetch timeouts, concurrency/resource ceilings, and outbound egress restrictions in an isolated environment.

**Decision unchanged:** `BLOCKED_PENDING_SSRF_AUTH_AND_EGRESS_TESTS`; no install or runtime test was performed during this source review.
