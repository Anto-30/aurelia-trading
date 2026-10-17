# External Repository Source Review — 2026-10-17

## Scope and evidence standard

This is a source/API inspection report for the 12 distinct repositories supplied for possible AURELIA-adjacent research. Default-branch commit SHAs below were resolved through GitHub's commit API on 2026-10-17. Selected README, manifest, security-policy, installer, and tool-implementation files were read directly through GitHub's contents API. GitHub's repository license metadata is reported as metadata, not as a substitute for legal review of every file and bundled dependency.

**This is not a completed isolated build/security certification.** No repository was cloned or executed in an isolated runner in this session. No SBOM, full dependency scan, secret scan, malware scan, reproducible build, benchmark, or full test-suite result is claimed. No third-party code was copied into AURELIA.

## Repository inventory and pinned inspection points

| Repository | Default branch HEAD inspected | GitHub license metadata | Current disposition |
|---|---|---|---|
| `RoversX/ThinkTerm` | `12028bfa9e9d685ade3f8297b7a74806752f179f` | GPL-3.0 | **Do not integrate by default.** Separate terminal/session product, not a trading runtime dependency. GPL-3.0 may impose distribution obligations; obtain license review before incorporation. |
| `raroque/boop-agent` | `31979130b1371acd9defbea115279a06c63c1fb4` | MIT | **Research-only agent prototype.** Root package has a broad SDK/integration surface (Claude Agent SDK, Composio, MCP, Convex, optional browser automation). Review server auth, webhook validation, tool permissions, build packaging, and each transitive dependency before deployment. |
| `xerj-org/xerj` | `e04ce9006bcd369ca82eba60aaf6106dd2bdea68` | Apache-2.0 | **Potential retrieval service, not approved for deployment.** README warns `--insecure` disables TLS and API-key authentication and may expose indexed content/memory to any reachable caller. Keep loopback-only unless TLS/auth are explicitly configured and tested. Security policy says the project is release-candidate stage; its stated CI includes Rust advisory scanning and bounded parser fuzzing, but that is not evidence we ran it. |
| `CopilotKit/OpenBot` | `12c3a69406b2ca32bcb117c0329c9c6d9359565d` | MIT | **Alpha template only; not approved for AURELIA runtime.** README explicitly says it is a template under active development. `.env.example` documents `OPENBOT_SINGLE_USER=true` as allowing every visitor administrator access and says sign-in is required before another party can reach a deployment. Never expose with this mode enabled. |
| `superlinked/sie` | `04f808008897c0bc6ab22ca69074e718c1eff598` | Apache-2.0 | **Optional future inference service.** Root Python workspace requires Python `>=3.12,<3.13`; workspace includes model, GPU, Docker, and cloud integration tests. No operational need, hardware fit, model-level license audit, or cost case is established for AURELIA. |
| `earendil-works/pi` | `8efd314fa3d3232ce197d8d7a6a5660530b9d83e` | MIT | **Best candidate for a replaceable research-agent harness, still unapproved.** Root is a private npm monorepo with many workspaces and examples/extensions. Its scripts include dependency pinning/runtime-dependency/import-graph/browser-smoke checks. Exact extension permissions, tool policy, network behavior, package-level licenses, and sandbox boundaries require separate review. Keep agents advisory and outside the capital plane. |
| `anandanand84/technicalindicators` | `7740f17cf681a2b1ace3009f5f396c14cbadf1f1` | MIT | **Test-only numerical reference candidate.** Latest default-branch commit inspected is from 2020-03-16. Root package is v3.1.0 and uses legacy Babel 6, Mocha 2, Gulp 3, TypeScript 2.9-era tooling and old type definitions. This is a maintenance/compatibility warning, not proof of a vulnerability. Do not add as a production dependency before parity tests and isolated dependency review. |
| `manu354/cryptocurrency-arbitrage` | `853d1d0d026997ace7c380aba350978c064a6519` | GPL-3.0 | **Historical educational reference only; do not run as a bot.** Repository commit is from 2018. `package.json` declares Node `8.0.0`, old dependencies, and license string `GNU` which is inconsistent/underspecified relative to GitHub's GPL-3.0 metadata. Its price-spread logic is not sufficient execution economics: no demonstrated current venue support, executable depth, fees, transfer/settlement delay, slippage, or live profitability. |
| `nightly-labs/openbot` | `9e50da3c80f9323fc6ac966b29a326e8043e5bf8` | GitHub reports NOASSERTION; package declares PolyForm-Noncommercial-1.0.0 | **Reject for commercial/production AURELIA use absent legal clearance and security redesign.** README calls it a development preview and warns agents run with `danger-full-access` and `approvalPolicy: never`, with filesystem, command, network, and browser access after first-launch consent. Package license explicitly says PolyForm Noncommercial 1.0.0. |
| `JerBouma/AlgorithmicTrading` | `87886cc8bf32f9ec9871c289cb5076371d5c1fb0` | MIT | **Educational research reference only.** GitHub marks the repository archived. No strategy should be treated as an edge or Deriv-compatible without a fresh specification, clean-room implementation, and independent out-of-sample evaluation. |
| `regnull/openbot` | `27f9e9e75564924f0512a2094808affbd7c9470b` | MIT | **Potential isolated workflow prototype, not approved for privileged operation.** README explicitly states `run_shell` is not sandboxed. Source inspection shows path containment and an optional `SHELL_USER` mode that drops privileges and removes server environment variables, but those controls are not equivalent to a container/VM security boundary. Require a dedicated unprivileged worker, network egress controls, tight workspace scope, webhook/API authentication, and tests before any use. |
| `anthropics/claude-plugins-official` | `ea10b213686c90bb1984b2016937310e05336cf3` | Apache-2.0 (catalog repository metadata) | **Catalog/reference only, not blanket approval.** Its README explicitly warns that plugins may include MCP servers, files, and other software Anthropic cannot verify. Review and pin each individual plugin source SHA, license, scripts, and permissions before installation. |

## Direct source observations

### ThinkTerm installer

Read `install.sh` at the pinned default-branch head. It accepts a release asset only after comparing it with the SHA-256 digest returned by GitHub when the digest is present. The mirror-download branch uses plain `curl` for third-party mirrors rather than the token-bearing helper and rejects digest mismatches. If GitHub provides no digest, the script falls back to GitHub rather than trusting a mirror. This is a useful integrity control, but does not change the GPL-3.0 licensing or make the product relevant to the AURELIA trading runtime.

### Boop Agent

Read root `package.json`. It is a private application package rather than a small isolated library; its dependency and integration surface includes browser automation, provider SDKs, MCP, Convex, Electron, and webhook scripts. A package manifest alone cannot establish safe authentication, webhook authorization, tool containment, or dependency health. No production credentials should be present in a test environment.

### XERJ

Read `SECURITY.md` and README security notes. The project documents release-candidate status and security/fuzz checks in its CI. The `--insecure` option must be treated as unsafe on any network interface reachable by other users. Do not put secrets or sensitive indexed documents into an exposed test instance.

### CopilotKit OpenBot

Read README, `.env.example`, and `server/src/config.ts`. The example explicitly warns that `OPENBOT_SINGLE_USER=true` makes every visitor an administrator. The repository is an alpha template and the example uses local-development values. Production would require deliberate identity-provider setup, non-example encryption keys, isolated computer/browser workers, scoped permissions, and a security review.

### SIE

Read root `pyproject.toml`. The workspace is a substantial inference platform, not a lightweight dependency; it includes Docker/GPU/cloud/model-marked test categories and an explicit Python-version range. Any future trial must be isolated, costed, model-license reviewed, and justified by measured inference latency/quality versus simpler alternatives.

### Pi agent toolkit

Read root `package.json`. It is a multi-workspace repository with multiple agent/tooling surfaces and examples. Its repository scripts are useful review targets but do not certify all optional extensions. A candidate deployment would need to disable unused extensions, enforce an allowlist of tools, run in a separate unprivileged process/container, restrict network egress, and prevent all agent identities from reaching broker credentials or order APIs.

### Technical indicators

Read `package.json`. The declared MIT license is permissive, but the development toolchain is old. Any use should be as a comparison oracle, not the canonical calculator. Required parity suite: fixed OHLCV fixtures; warm-up and missing-value behavior; input ordering; candle boundaries; precision/tolerance; RSI/MACD/EMA/SMA/ATR/VWAP outputs; no lookahead; deterministic results. The implementation must remain behind an adapter until parity is demonstrated.

### Cryptocurrency arbitrage sample

Read `package.json` and `main.js`. The app is a 2017-era Node service that serves a web page and calculates price differences from API responses. It is not evidence of executable arbitrage. No API keys, orders, exchange actions, or execution tests were performed. It must not be connected to a broker or reused as a trading engine.

### Nightly Labs OpenBot

Read README and root `package.json`. Its own documentation states that agents receive broad machine access and no per-action approval after initial consent. It also declares a non-commercial license. Those are independent blockers for production/commercial AURELIA use.

### Regnull OpenBot

Read README, `backend/openbot/tools/builtin/shell.py`, `backend/openbot/tools/builtin/workspace.py`, and `backend/openbot/config.py`. The shell tool launches Bash and relies on workspace path checks; optional `SHELL_USER` uses `setpriv` and a reduced environment when configured. Since the README says the tool is not sandboxed, workspace path checks and optional UID dropping must not be represented as a complete sandbox. Never grant this process production secrets or broker permissions.

### Claude plugins catalog

Read README. It separates internal and third-party plugins and explicitly tells users to trust-check plugins before installing/updating. The catalog's Apache-2.0 metadata does not automatically license every linked plugin or dependency.

## AURELIA integration decision

No candidate is approved for direct integration at this stage. Recommended order of further investigation:

1. **Technical-indicator parity experiment** in a disposable, no-secret test environment, using pinned source and golden vectors; copy no implementation until the license and parity review is complete.
2. **Pi toolkit proof of concept** only for read-only research, with an explicit tool allowlist and no broker credentials/order endpoint access.
3. **XERJ retrieval proof of concept** only bound to loopback or an authenticated private network, with test data rather than secrets.
4. **SIE** only if a measured inference requirement justifies its runtime and infrastructure burden.
5. Keep both OpenBot projects, ThinkTerm, Boop Agent, the arbitrage sample, and plugin catalog outside the canonical trading runtime unless a separate threat model and legal review approve a narrowly scoped use.

AURELIA remains the only canonical capital plane. Agents may produce research and evidence but cannot approve releases, override deterministic risk controls, or submit live orders.

## What still must be run in a real isolated environment

- Clone the pinned SHAs with no AURELIA secrets, no production filesystem access, and restricted network egress.
- Record source tree hashes and generate per-repository SBOMs.
- Run secret scanning and dependency/advisory scans against lockfiles and all subpackages; distinguish confirmed findings from scanner noise.
- Review shell/install scripts, CI workflows, extension/plugin loading, subprocess execution, authentication, workspace boundaries, outbound network access, and license notices at the exact pinned SHAs.
- Run tests/builds only after sandbox policy is verified; record exact commands, tool versions, logs, exit codes, and artifact hashes.
- Run indicator golden-vector tests and strategy out-of-sample/cost validation before any trading-related use.
- Obtain independent human security/license review before integrating anything.

## Safety status

No third-party source or package was added to AURELIA. No repository code was executed. No broker credentials were read or disclosed, no broker operation or live order was sent, no production deployment was performed, and no paid resource was created. The absence of a local isolated clone/test environment remains a hard evidence boundary, not a task completed by documentation.

