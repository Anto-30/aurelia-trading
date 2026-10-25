# FreeLLMAPI Deployment-Path Review — 2026-10-24

## Scope and evidence

Read-only retrieval of selected files from `tashfeenahmed/freellmapi` default branch on 2026-10-24. Current observed upstream main commit: `5646971602a89436ce4921b0f04b99ac7bcc3728`. No code was executed, built, or installed. This is a focused configuration/source inspection, not a complete security audit.

| File | Retrieved blob SHA | Review purpose |
|---|---|---|
| `package.json` | `958e1dbce29a84e891265df15b9fe9c9883af635` | workspace scripts/test/build entry points |
| `server/package.json` | `306e550adb2454f91d2d4ff4f691d2014c63879f` | server dependencies and scripts |
| `Dockerfile` | `228c81dd314b436513be04fe9d6f06757e57f0ca` | image build/runtime stages |
| `docker-compose.yml` | `cf28e53e045cc421ec41a1901f8af16251919954` | network binding and update configuration |
| `.dockerignore` | `58610da53da142013553d685cab8f75a003d4360` | build-context secret/data exclusions |
| `.github/workflows/ci.yml` | `6686fff2044854a308843e31832b238832a53528` | test/build workflow |

## Observations

1. **Default container tag is mutable.** The compose file references `ghcr.io/tashfeenahmed/freellmapi:latest`. For any future sandbox evaluation, resolve and pin the image by immutable digest; do not use `:latest` as an evidence-grade artifact or for an automatically updating production deployment.
2. **Automatic update path exists.** Compose config includes a Watchtower integration behind an optional `autoupdate` profile and a token. Its exact runtime behavior and authentication boundaries have not been tested. Keep automatic updates disabled during audit; review the full compose file, Watchtower image/version, token handling, update scope, and rollback behavior before enabling it.
3. **Localhost is the declared default bind.** Compose uses `${HOST_BIND:-127.0.0.1}`, with an explicit comment warning that the service is single-user and should not be exposed to the internet. Preserve loopback-only binding in any test; do not set `HOST_BIND=0.0.0.0`.
4. **Host gateway is made reachable from the container.** Compose adds `host.docker.internal:host-gateway` to support proxy configuration. This can be useful for local proxying but also means the container has a host-reachable network path; network egress and proxy targets must be restricted during sandbox tests.
5. **Build context exclusions are present.** `.dockerignore` excludes `.env`, `.env.*`, SQLite DB files, backups, the encryption-key file, and data directories. This is a positive safeguard in the inspected file, not proof that all secret paths or Docker build stages are safe.
6. **Multi-stage image build and lockfile install.** Dockerfile uses `npm ci`, builds in a separate stage, prunes dev dependencies, and copies into a runtime stage. The Node image is tag-pinned but not recorded here by digest; the Docker base image and resulting image should be pinned/attested for reproducibility.
7. **CI action references appear immutable in the inspected excerpt.** The workflow uses full commit SHAs for checkout and setup-node. This is a positive signal for those specific action references only; the complete workflow, permissions, artifact handling, and test results still need review.
8. **Server dependency surface is substantial.** The server package includes Express, CORS, Helmet, upload handling, proxy-agent and HTTP client dependencies, schema validators, and SQLite-related native dependency support via the workspace. This is not itself a vulnerability finding; it defines areas for dependency/SAST and request-boundary review.
9. **Catalog configuration examples need per-client compatibility checks.** The Awesome Free LLM APIs repository's Claude Code example sets `ANTHROPIC_BASE_URL` to endpoints labelled OpenAI-compatible. Compatibility varies by provider and client API dialect; treat examples as templates, not verified working configurations. Test each client/provider pair with dummy prompts and no sensitive source before considering use.

## Decision

No deployment or runtime integration is approved. Keep FreeLLMAPI quarantined for research; keep the API directory read-only. Before isolated execution, use a disposable environment, no real API keys, no broker or production network routes, loopback-only exposure, automatic updates disabled, pinned image/dependencies, and egress allowlisting. A successful build/test would not authorize AURELIA production use.

## Remaining checks

- Review full compose file, Watchtower image/version, token setup, all Dockerfile stages and startup scripts.
- Inspect auth, encryption-key lifecycle, catalog signature/rollback validation, MCP permissions, logging/redaction, upload paths, outbound request controls, and backup/restore behavior.
- Review full lockfile and produce SBOM; run approved dependency/CVE, secret, and static analysis.
- Execute upstream tests and reproducible build only in a disposable sandbox; record exact commit, environment, commands, exit codes, and artifacts.
- Verify each candidate provider's official API terms, retention/training, region, rate limits, and free-tier eligibility.
- Resolve the mismatch between SECURITY.md's `0.13.x` supported-version claim and the observed `0.16.7` release page.

## Direct sources

- https://github.com/tashfeenahmed/freellmapi/blob/5646971602a89436ce4921b0f04b99ac7bcc3728/package.json
- https://github.com/tashfeenahmed/freellmapi/blob/5646971602a89436ce4921b0f04b99ac7bcc3728/server/package.json
- https://github.com/tashfeenahmed/freellmapi/blob/5646971602a89436ce4921b0f04b99ac7bcc3728/Dockerfile
- https://github.com/tashfeenahmed/freellmapi/blob/5646971602a89436ce4921b0f04b99ac7bcc3728/docker-compose.yml
- https://github.com/tashfeenahmed/freellmapi/blob/5646971602a89436ce4921b0f04b99ac7bcc3728/.dockerignore
- https://github.com/tashfeenahmed/freellmapi/blob/5646971602a89436ce4921b0f04b99ac7bcc3728/.github/workflows/ci.yml
- https://github.com/open-free-llm-api/awesome-freellm-apis/blob/d04877f798520a680a0a954ced5a6ee5514406c0/code-examples/claude-code.md
