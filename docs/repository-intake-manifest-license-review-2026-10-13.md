# Repository Intake — Manifest and License Review (2026-10-13)

This is a source-file spot check using GitHub raw files from the repositories' current default branches. Before importing anything, repeat the review against the immutable upstream commit SHA recorded in `repository-intake-upstream-pins-2026-10-13.md`; a `main` URL can move independently.

## License-file spot checks

| Repository | License file observed | Preliminary disposition |
|---|---|---|
| pasky/chrome-cdp-skill | MIT | License appears permissive; operational risk remains high because the skill controls an existing browser session. |
| anthropics/claude-quickstarts | MIT | Example code only; review each sample and its dependency/API-key handling. |
| siteboon/claudecodeui | AGPL-3.0 | Copyleft review required before modifying, distributing, or operating a modified network-accessible service. Also reconcile critical security advisories against exact package version and code. |
| ChrisWiles/claude-code-showcase | No root `LICENSE` found at the checked path (HTTP 404). | Treat licensing as unconfirmed. Do not copy or redistribute source components until rights are clarified. |
| decebals/claude-code-java | MIT | License appears permissive; use only if Java-specific workflow support is needed. |
| d-kimuson/claude-code-viewer | MIT | License appears permissive; web UI/terminal/session-control attack surface still requires security testing. |
| intel/auto-round | Apache-2.0 | License appears permissive; benchmark-only until reproducible evaluation is complete. |
| D4Vinci/Scrapling | BSD 3-Clause | License appears permissive; isolate network access and review dependency/security posture. |
| cyberchitta/scrapling-fetch-mcp | Apache-2.0 | License appears permissive; MCP network access and SSRF controls remain blocking gates. |
| popiliadam/platinum-seo-engine | AGPL-3.0 | Copyleft review required; keep outside the trading runtime and separate from proprietary code pending counsel/license review. |

These are observations of root license files, not legal advice, not a complete attribution audit, and not verification of all transitive dependency licenses.

## Manifest and configuration observations

### siteboon/claudecodeui (package name `@cloudcli-ai/cloudcli`, version `1.37.4` in the inspected package.json)
- The package scripts expose server and desktop entry points and build/test/typecheck commands.
- Root license file is AGPL-3.0, contrary to any assumption that this project is automatically permissive.
- Security gate: inspect exact vulnerable endpoints and advisory patches at the pinned commit, then run targeted unauthenticated/RCE regression tests in a disposable isolated environment. Do not expose the service to the public internet or use a host with broker credentials.

### d-kimuson/claude-code-viewer (package version `0.8.2` in package.json)
- Package includes a start command, build scripts, test/lint/typecheck commands and a large dependency surface.
- README's warning that no password disables authentication must be treated as a hard deployment blocker for any non-local use.
- Do not run with real agent histories, credentials, broker access, or an internet-reachable bind until auth, session isolation, terminal permissions and host binding are verified.

### cyberchitta/scrapling-fetch-mcp (pyproject version `0.2.5`)
- Declares a fetch/extraction MCP server and dependencies including Scrapling fetchers, MCP, cryptography, PyJWT and Starlette.
- Version constraints alone do not prove dependency safety. Resolve a lockfile/SBOM and scan the full dependency graph at the pinned revision.
- Network egress must deny loopback, link-local, RFC1918/private, metadata endpoints and redirects into those ranges; enforce DNS revalidation, content/time/size ceilings, authentication, and explicit allowlists. Do not use it to bypass access controls.

### popiliadam/platinum-seo-engine (.mcp.json)
- The inspected config launches MCP tools through `bash -c`, sources a local `.env`, and runs packages with `npx -y`.
- It also includes a machine-specific absolute path under `/Users/apple/Downloads/...` and local HTTP endpoints.
- Do not copy this config into AURELIA. Replace it with an audited, portable, least-privilege configuration only in a separate marketing workspace; pin package versions and integrity, remove machine-specific paths, avoid broad environment inheritance, and validate every server and endpoint before startup.

### intel/auto-round
- `pyproject.toml` configures Python 3.11 lint/test tooling and a setuptools build backend.
- No quantization or model-routing change is approved by this review. Any benchmark must record exact model/checkpoint, dataset, calibration set, hardware, seed, quantization settings, latency/memory and quality metrics.

## Required next actions

1. Re-fetch each inspected file by immutable commit SHA and record file blob hashes before adoption.
2. Confirm exact advisory applicability and patch status for CloudCLI; run security regressions, dependency audit, secret scan and SAST in an isolated environment.
3. Generate an SBOM and full transitive dependency/license report for each candidate; check the full license/notice tree, not only root LICENSE.
4. Review MCP and hook configs as executable code. No imported agent config may access production secrets, write to main, change release gates or route broker orders.
5. Keep PR #122 draft until selected code has reproducible test evidence and a human review. No code was installed, executed or merged as part of this spot check.


## Immutable-revision license recheck (2026-10-13)

The root `LICENSE` path was re-fetched using each exact upstream commit SHA in the registry, rather than the moving default branch. Git blob IDs returned by GitHub:

| Repository | Pinned commit | Root LICENSE blob | Result |
|---|---|---|---|
| `pasky/chrome-cdp-skill` | `ffea76a24b0471663ddd9d9f24335bbc442b6266` | `e0cb6b81ad2c4dfe17b2fd93b9387b6fff573aa6` | Found; MIT |
| `anthropics/claude-quickstarts` | `9ec32b91df50b0d4906cae64b13c6298055ff40d` | `e0d914d8c81feba1a081620902f8c4877ad6313d` | Found; MIT |
| `siteboon/claudecodeui` | `7c3049fe8e157f12b7add3e496d8d2fe6fa5c014` | `b9620f502de0874d9c8b145aa505c8b1447eebe0` | Found; AGPL-3.0-or-later |
| `ChrisWiles/claude-code-showcase` | `a95518f0cb67e86230119da40429169bc4c35a6f` | — | Root path returns 404; license remains unconfirmed |
| `decebals/claude-code-java` | `0d98fe9bd62923e819568ee1e041a1bf320f74d4` | `85c2f8765b2abb92096668fa9e0e808edafadc19` | Found; MIT |
| `d-kimuson/claude-code-viewer` | `9367cf006be9965c954e6cd36526f2195dce67ea` | `fc5beba21eefa1dfa6753ba19c2cbfb175b5b268` | Found; MIT |
| `intel/auto-round` | `4663212ac4fd18be2b4ec4fa7c79c6e2e6fa9ce1` | `2bb9ad240fa04c8cf706a4901c4807878e90c2dc` | Found; Apache-2.0 |
| `D4Vinci/Scrapling` | `7a684934907a8c7feaafe9ff1ccfd9d45cc26faf` | `41615aad07eb42df7f09997f207950098e853a68` | Found; BSD 3-Clause |
| `cyberchitta/scrapling-fetch-mcp` | `8ed4c0df0979ca758e6e13ae84e6cdbe129e1a7a` | `f49a4e16e68b128803cc2dcea614603632b04eac` | Found; Apache-2.0 |
| `popiliadam/platinum-seo-engine` | `ffdf24da84cd5d52f755f156707d9bd14f7c0135` | `be3f7b28e564e7dd05eaf59d64adba1a4065ac0e` | Found; AGPL-3.0 |

This closes the narrow question of whether the root license file exists at each pinned revision for nine of the ten candidates. It does **not** establish complete license compliance: nested notices, vendored components, transitive dependencies, generated assets, and attribution obligations have not been exhaustively scanned. For Claude Code Showcase, inspect repository metadata and nested license/notice files and obtain maintainer clarification before copying or redistributing any source.
