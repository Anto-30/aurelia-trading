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
