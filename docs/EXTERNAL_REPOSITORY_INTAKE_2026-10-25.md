# External Repository Intake — 2026-10-25

## Status

This is a controlled intake proposal for 29 repositories supplied for AURELIA engineering evaluation. Registration is not a security approval, installation, dependency pin, or production integration.

- Intake candidates: 29
- Newly added registry records: 29
- Candidate head revisions: 29/29 pinned to the observed default-branch commit snapshot queried on 2026-10-25. The exact commit links and author dates are recorded in the pin manifest below. This is source provenance only, not a security approval.
- Runtime installation: none performed by this change.
- Capital/execution authority: none.
- `config/LIVE_LOCK.yaml` is unchanged and remains fail-closed.

## Required gate for every candidate

1. Resolve exact repository head SHA and release/tag; preserve the sync artifact.
2. Inspect license, maintenance/release history, source tree, install/build hooks, dependency manifests and lockfiles.
3. Run secret scanning, dependency vulnerability review, static analysis where applicable, and isolated tests.
4. Review subprocess/shell, filesystem, network egress, browser/session, token storage, logging, prompt-injection, and sandbox behavior.
5. Record a verdict with evidence: ACCEPT_FOR_SANDBOX, REFERENCE_ONLY, REJECT, or BLOCKED.
6. Require independent review before any production dependency proposal. No agent, skill, proxy, extension, or repository may access broker secrets or modify the capital plane.

## Special handling

- Account/session tooling (`Loongphy/codex-auth`, `ryfineZ/codex-session-patcher`, `qxcnm/Codex-Manager`) requires a dedicated credential/session threat model. Do not use with real credentials during initial testing.
- Model routers/proxies (`router-for-me/CLIProxyAPI`, `decolua/9router`) require explicit egress allowlists, secret redaction, authentication review, and request/response logging tests.
- OpenHands repositories have distinct responsibilities. Prefer evaluating `OpenHands/software-agent-sdk` as the core SDK candidate; assess the CLI, app, automation, extensions, ACI and Cloud repositories against that boundary instead of installing all components.
- Goose repositories are distinct projects: `aaif-goose/goose` is an agent framework, `pressly/goose` is a database migration tool, and `tag1consulting/goose` is a Rust load-testing project. `b-nnett/goose` requires identity verification before classification.
- `mz-automation/libiec61850` is an industrial communications library and stays outside AURELIA's trading runtime absent a separate justified use case.
- `aide/aide` requires repository-purpose confirmation before anything beyond reference-only handling.
- Skills, prompts and instruction files are untrusted inputs; review each item individually. Do not bulk-install.

## Pin and metadata manifest — 2026-10-25

Commit SHAs were retrieved from GitHub's public REST `GET /repos/{owner}/{repo}/commits?per_page=1` endpoint. Each returned the latest commit on the declared default branch at query time. Dates are commit author dates (UTC), not verification or release dates. Branches may advance; the SHA pins remain immutable until changed through review.

License dispositions use GitHub repository license metadata unless the table notes direct inspection. `NO LICENSE FILE` means no top-level `LICENSE`/`LICENSE.md` was found in the inspected repository contents; it does not prove that every nested file lacks separate terms. The OpenHands Cloud `LICENSE` was inspected and identifies PolyForm Free Trial 1.0.0, which has material restrictions on distributing copies. The `pressly/goose` top-level `LICENSE` was inspected and identifies MIT despite GitHub API `NOASSERTION`.

| Repository | Default branch | Pinned commit | Author date (UTC) | License finding | Archived | Intake disposition |
|---|---|---|---|---|---|---|
| `iOfficeAI/OfficeCLI` | `main` | [`5e3e26278753`](https://github.com/iOfficeAI/OfficeCLI/commit/5e3e26278753be846b4b0b2fb0387f42d911553a) | 2026-10-23 | Apache-2.0 | No | UNREVIEWED |
| `Jia-Ethan/codex-keysmith` | `main` | [`cfcd96eb727c`](https://github.com/Jia-Ethan/codex-keysmith/commit/cfcd96eb727c324ee8649170c43aaa632ff53cb3) | 2026-09-27 | MIT | No | UNREVIEWED |
| `Loongphy/codex-auth` | `main` | [`a83059701ee5`](https://github.com/Loongphy/codex-auth/commit/a83059701ee54c4c8f91aa030810b97bd35e254b) | 2026-10-25 | MIT | No | UNREVIEWED |
| `ryfineZ/codex-session-patcher` | `main` | [`cf7deab2d5b2`](https://github.com/ryfineZ/codex-session-patcher/commit/cf7deab2d5b28c1f70f5b5498461848b69024a15) | 2026-10-05 | NO LICENSE FILE | No | BLOCKED — no top-level license file |
| `openai/codex-security` | `main` | [`796fa130e927`](https://github.com/openai/codex-security/commit/796fa130e92787085ab36aa4313d8c4bd9414560) | 2026-10-25 | Apache-2.0 | No | UNREVIEWED |
| `qxcnm/Codex-Manager` | `main` | [`430eddb0af9a`](https://github.com/qxcnm/Codex-Manager/commit/430eddb0af9ae6277f8133fbac7f8634b7699dc6) | 2026-10-18 | MIT | No | UNREVIEWED |
| `composio-community/awesome-codex-skills` | `master` | [`0930e1373789`](https://github.com/composio-community/awesome-codex-skills/commit/0930e1373789d2eda449039f7ac154b33031de89) | 2026-07-26 | NO LICENSE FILE | No | BLOCKED — no top-level license file |
| `router-for-me/CLIProxyAPI` | `main` | [`bc0643405a1d`](https://github.com/router-for-me/CLIProxyAPI/commit/bc0643405a1d0adf77dd0f109972ac3313d66397) | 2026-10-24 | MIT | No | UNREVIEWED |
| `OpenHands/OpenHands` | `main` | [`b7fdc6c31203`](https://github.com/OpenHands/OpenHands/commit/b7fdc6c312039a0b840fdcd34a5c23ca7e65c218) | 2026-10-25 | MIT | No | UNREVIEWED |
| `OpenHands/software-agent-sdk` | `main` | [`d2ee0cdea608`](https://github.com/OpenHands/software-agent-sdk/commit/d2ee0cdea60825608c2f8906eb54e1d4d264fb42) | 2026-10-25 | MIT | No | UNREVIEWED |
| `OpenHands/extensions` | `main` | [`1ea389f96e44`](https://github.com/OpenHands/extensions/commit/1ea389f96e44a7f1db8969b25ec460d02e8fcf09) | 2026-10-24 | MIT | No | UNREVIEWED |
| `OpenHands/OpenHands-CLI` | `main` | [`283c6ac3610f`](https://github.com/OpenHands/OpenHands-CLI/commit/283c6ac3610f4299f405f7389f65766dcb83e12a) | 2026-10-22 | MIT | No | UNREVIEWED |
| `OpenHands/automation` | `main` | [`2c110703bbe9`](https://github.com/OpenHands/automation/commit/2c110703bbe91e4113a57adc1fa64a912ac7f4f8) | 2026-10-23 | MIT | No | UNREVIEWED |
| `OpenHands/openhands-aci` | `main` | [`a8d8d23ec635`](https://github.com/OpenHands/openhands-aci/commit/a8d8d23ec635f9aaa94af17aec3c851656f10c8a) | 2026-03-24 | MIT | Yes | BLOCKED — archived |
| `OpenHands/OpenHands-Cloud` | `main` | [`d1c3b0d8cae4`](https://github.com/OpenHands/OpenHands-Cloud/commit/d1c3b0d8cae493e15c7d8931f1d9d06180799928) | 2026-10-23 | PolyForm Free Trial 1.0.0 | No | BLOCKED — restrictive license |
| `cline/cline` | `main` | [`40c5d99031fe`](https://github.com/cline/cline/commit/40c5d99031fe1128189c5b52e40638d2b7787754) | 2026-10-24 | Apache-2.0 | No | UNREVIEWED |
| `cline/prompts` | `main` | [`2fc3b77a8fe3`](https://github.com/cline/prompts/commit/2fc3b77a8fe39553ac424bfc7cdc9883e4a21e1f) | 2026-02-27 | NO LICENSE FILE | No | BLOCKED — no top-level license file |
| `decolua/9router` | `master` | [`f39d8f07481a`](https://github.com/decolua/9router/commit/f39d8f07481ae8518e93175f0ecaaafa61573c6c) | 2026-10-23 | MIT | No | UNREVIEWED |
| `aaif-goose/goose` | `main` | [`2b17adc33a71`](https://github.com/aaif-goose/goose/commit/2b17adc33a7176e701c2fef9578a5fc5834ea89a) | 2026-10-24 | Apache-2.0 | No | UNREVIEWED |
| `pressly/goose` | `main` | [`0aa9878439d2`](https://github.com/pressly/goose/commit/0aa9878439d23c25b62634b9cb9306a007d326d4) | 2026-10-25 | MIT (LICENSE file inspected) | No | UNREVIEWED |
| `b-nnett/goose` | `main` | [`ba9ae0280c9b`](https://github.com/b-nnett/goose/commit/ba9ae0280c9b5b9a1545baab8e944cb3b7563c62) | 2026-06-02 | NO LICENSE FILE | Yes | BLOCKED — archived |
| `gooseworks-ai/goose-skills` | `main` | [`6d5d5f160c62`](https://github.com/gooseworks-ai/goose-skills/commit/6d5d5f160c623613d7eb682b6a467beb165cc2a4) | 2026-10-20 | MIT | No | UNREVIEWED |
| `mz-automation/libiec61850` | `v1.6_develop` | [`6e265c54af66`](https://github.com/mz-automation/libiec61850/commit/6e265c54af66ea686453b6d31c4dcce1cf7ad2bd) | 2026-10-21 | GPL-3.0 | No | UNREVIEWED |
| `tag1consulting/goose` | `main` | [`7bf83ae35a6c`](https://github.com/tag1consulting/goose/commit/7bf83ae35a6c3acc666c5a5ea38332ddeb0735d9) | 2026-10-25 | Apache-2.0 | No | UNREVIEWED |
| `Aider-AI/aider` | `main` | [`5dc9490bb35f`](https://github.com/Aider-AI/aider/commit/5dc9490bb35f9729ef2c95d00a19ccd30c26339c) | 2026-05-22 | Apache-2.0 | No | UNREVIEWED |
| `hotovo/aider-desk` | `main` | [`438e8710fa5f`](https://github.com/hotovo/aider-desk/commit/438e8710fa5f89a9509ce8d4b1c6f314a801b779) | 2026-10-25 | Apache-2.0 | No | UNREVIEWED |
| `coder/agentapi` | `main` | [`7c468d5b25ec`](https://github.com/coder/agentapi/commit/7c468d5b25ec9d3d76c41313cf4e08904ff5968d) | 2026-09-13 | MIT | Yes | BLOCKED — archived |
| `aide/aide` | `master` | [`db923656149e`](https://github.com/aide/aide/commit/db923656149ea64bee63f7e45275322a20c7dbe3) | 2026-10-18 | GPL-2.0 | No | UNREVIEWED |
| `iamfakeguru/agent-md` | `main` | [`65c6a8e8ca1b`](https://github.com/iamfakeguru/agent-md/commit/65c6a8e8ca1b2aa3a84fde5b1ea20f1abbbf063f) | 2026-09-21 | MIT | No | UNREVIEWED |

**Pinned set:** 29/29. **Blocked pending prerequisites:** seven. **Security/functional source audits and isolated tests:** not yet completed. `coder/agentapi` is archived and its pinned commit subject explicitly says deprecated and unmaintained; OpenHands ACI and `b-nnett/goose` are archived; the three no-license skill/session/prompt sources are blocked from installation or redistribution; OpenHands Cloud is blocked for adoption pending legal review of its restrictive license.

Pinning establishes provenance only. It does not establish license compatibility, benign behavior, maintainability, successful installation, test coverage, or fitness for AURELIA.

---
## Candidate inventory

| Repository | Preliminary mode | Main review focus |
|---|---|---|
| `iOfficeAI/OfficeCLI` | TOOLCHAIN_ONLY | office-document-agent-tool |
| `Jia-Ethan/codex-keysmith` | SANDBOX_ONLY | agent-instruction-management |
| `Loongphy/codex-auth` | SANDBOX_ONLY | credential-account-manager |
| `ryfineZ/codex-session-patcher` | SANDBOX_ONLY | session-modification-tool |
| `openai/codex-security` | TOOLCHAIN_ONLY | code-security-assurance |
| `qxcnm/Codex-Manager` | SANDBOX_ONLY | coding-agent-account-management |
| `composio-community/awesome-codex-skills` | REFERENCE_ONLY | agent-skills-catalog |
| `router-for-me/CLIProxyAPI` | SANDBOX_ONLY | llm-api-proxy |
| `OpenHands/OpenHands` | SANDBOX_ONLY | coding-agent-application |
| `OpenHands/software-agent-sdk` | SANDBOX_ONLY | coding-agent-sdk |
| `OpenHands/extensions` | REFERENCE_ONLY | agent-extension-registry |
| `OpenHands/OpenHands-CLI` | SANDBOX_ONLY | coding-agent-cli |
| `OpenHands/automation` | SANDBOX_ONLY | agent-automation-orchestration |
| `OpenHands/openhands-aci` | REFERENCE_ONLY (BLOCKED) | agent-computer-interaction |
| `OpenHands/OpenHands-Cloud` | REFERENCE_ONLY | hosted-agent-platform |
| `cline/cline` | SANDBOX_ONLY | coding-agent-extension |
| `cline/prompts` | REFERENCE_ONLY | agent-prompt-library |
| `decolua/9router` | SANDBOX_ONLY | llm-api-router |
| `aaif-goose/goose` | SANDBOX_ONLY | coding-agent-framework |
| `pressly/goose` | TOOLCHAIN_ONLY | database-migration-tool |
| `b-nnett/goose` | REFERENCE_ONLY | goose-project-identity-unverified |
| `gooseworks-ai/goose-skills` | REFERENCE_ONLY | agent-skills-library |
| `mz-automation/libiec61850` | REFERENCE_ONLY | industrial-protocol-library |
| `tag1consulting/goose` | TOOLCHAIN_ONLY | rust-load-testing-tool |
| `Aider-AI/aider` | SANDBOX_ONLY | coding-agent |
| `hotovo/aider-desk` | SANDBOX_ONLY | coding-agent-ui |
| `coder/agentapi` | REFERENCE_ONLY (BLOCKED) | agent-runtime-api (deprecated/unmaintained signal) |
| `aide/aide` | REFERENCE_ONLY | developer-agent-tooling-identity-unverified |
| `iamfakeguru/agent-md` | REFERENCE_ONLY | agent-instruction-conventions |

## Completion criteria

Intake is complete only when every candidate has an exact commit SHA, verified source URL, license disposition, security/test evidence, owner/reviewer, and a recorded acceptance/rejection decision. The sync workflow's head snapshot alone is not a security approval. Production use requires a separate reviewed change and existing AURELIA release gates.
