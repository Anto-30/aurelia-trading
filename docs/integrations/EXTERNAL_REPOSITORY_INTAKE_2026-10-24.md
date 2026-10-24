# External Repository Intake — 2026-10-24

## Decision boundary

This is a preliminary, source-linked triage of the repositories submitted on 2026-10-24. It is **not** a completed source audit. No repository was cloned or executed by this intake record; exact default-branch HEAD SHAs, signed releases, dependency locks, SBOMs, security scans, reproducible tests, and license compatibility have not been verified here.

AURELIA remains fail-closed: `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, and `capital_plane_mode=VERIFY_ONLY`. Keep every candidate outside the production runtime and capital plane until independently reviewed. No third-party agent or repository may access broker credentials, alter risk limits, authorize capital, submit orders, change the kill switch, or release a deployment.

## Deduplicated candidate register

| Repository | Preliminary category | Potential use | Initial disposition / key gate |
|---|---|---|---|
| [openinterpreter/openinterpreter](https://github.com/openinterpreter/openinterpreter) | Toolchain candidate; high-risk execution surface | Provider-agnostic coding-agent harness; ACP/MCP/skills portability | **Sandbox-only.** It can inspect/edit files and execute commands. Verify sandbox boundaries, approval semantics, filesystem/network permissions, hooks, provider auth, dependency provenance, and exact source head before any isolated trial. Apache-2.0 is indicated upstream; review notices and bundled dependencies. |
| [FareedKhan-dev/kimi-k3-in-c](https://github.com/FareedKhan-dev/kimi-k3-in-c) | Reference / isolated inference-engine candidate | Portable C inference implementation and deterministic parser/kernel tests | **Reference-only pending audit.** Upstream README describes a weightless test suite plus a very large model checkpoint requirement. Build/test only in a disposable, network-restricted environment after source-head and build-script review. Verify all numerical and performance claims independently; do not download multi-terabyte weights as part of intake. Apache-2.0 project license is indicated, with separate model-weight terms. |
| [gavamedia/deltafin](https://github.com/gavamedia/deltafin) | Reference / isolated local-inference server candidate | Local Kimi K3 inference and OpenAI-compatible API research | **Sandbox-only; not a trading runtime.** Upstream documents model setup/downloads and an API server. Review all install/download paths, native dependencies, model provenance, request limits, and server binding/authentication. Keep any test service on loopback in a disposable environment; never expose an unauthenticated endpoint. Upstream says project code is MIT, while model and other third-party assets have separate terms. |
| [MoonshotAI/Kimi-K3](https://github.com/MoonshotAI/Kimi-K3) | Official model-source reference | Authoritative model code, model card/configuration, license and provenance reference | **Reference-only.** Verify the actual license and any model-service restrictions before download, deployment, redistribution, or external access. No weights or code are implicitly approved for production by adding this URL. |
| [sqliteai/warp](https://github.com/sqliteai/warp) | Reference / isolated inference-engine candidate | Weight-aware local model paging and bounded expert-cache research | **Reference-only pending audit.** Review memory-mapped/direct I/O, file access, download paths, native code, cache integrity, model provenance, and reproducibility. Its reported model/runtime requirements are not validated by this intake. Do not connect it to AURELIA's runtime or capital plane. |
| [baidu-baige/LoongForge](https://github.com/baidu-baige/LoongForge) | Research reference; likely out-of-scope for runtime | LLM/VLM/diffusion training framework and accelerator research | **Reference-only.** It appears oriented to training on NVIDIA GPUs and Kunlun XPUs, not a direct AURELIA agent connector. Review Apache-2.0 and per-file third-party notices if a specific component is proposed. No install or runtime inclusion authorized. |
| [Leechael/pi-provider-kimi-code](https://github.com/Leechael/pi-provider-kimi-code) | Optional provider adapter candidate | Kimi Code provider, optional Moonshot tools, Pi harness integration | **Sandbox-only pending credential review.** Upstream describes reading/synchronizing Kimi CLI OAuth credentials and optional server-side tools. Do not use a personal credential file in CI or AURELIA; test with a disposable account/session, minimal scopes, redacted logs, tools disabled by default, and explicit opt-in. Confirm Pi/provider versions, license, dependency and token-refresh behavior. |
| [Ebony-Vinyl/dsh-our-free-model](https://github.com/Ebony-Vinyl/dsh-our-free-model) | DeepSeek Harness plugin candidate; elevated supply-chain risk | Potential model-provider option for DSH, subject to endpoint/provenance verification | **Quarantined; do not install or send sensitive prompts.** The repository advertises no-login/no-key/free access to frontier models. Before any test, identify the actual service operator, endpoints, data retention/training terms, authentication and rate limits, code paths, dependency chain, and whether prompts/code are sent to an untrusted third party. A public MIT license does not establish endpoint safety, privacy, model authorization, or availability. |
| [gavamedia/deltafin](https://github.com/gavamedia/deltafin) (duplicate URL) | Duplicate | — | Deduplicated; one entry only. |

## Required verification gates

1. Resolve each repository's default branch and exact current HEAD SHA; record retrieval timestamp and source URL. Do not use a mutable branch name as a pin.
2. Read the complete license, notices, model/data terms, security policy, install/build scripts, CI workflows, submodules, and lockfiles.
3. Generate an SBOM and run dependency, secret, malware, static-analysis, and license checks in an isolated environment. Treat scanner output as evidence to review, not a guarantee of safety.
4. Run only documented, bounded tests with network disabled by default and no secrets, user data, broker endpoints, or production mounts. Record commands, environment, exit codes, logs, and artifact hashes.
5. For provider plugins, verify endpoints and data handling before sending even non-public source code. Credentials must be provisioned only through an approved secret manager or provider OAuth UI; never place them in repository files, prompts, issues, or logs.
6. Any proposed AURELIA integration must be a separate, reviewed PR with exact source pins, provenance, test evidence, rollback plan, and independent approval. No candidate receives capital authority or execution access.

## Status

- URLs deduplicated: 8 unique repositories.
- Preliminary public-source triage: recorded.
- Exact source-head pinning: **not yet verified**.
- Clone, SBOM, dependency/security/license scans: **not yet run**.
- Isolated build/tests and integration tests: **not yet run**.
- External provider sessions/authentication: **not established by this record**.
- Production/AURELIA runtime installation: **not performed**.
- Live execution: **blocked; VERIFY_ONLY remains mandatory**.
