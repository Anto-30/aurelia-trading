# External Repository Intake — 2026-10-25

## Status

This is a controlled intake proposal for 28 repositories supplied for AURELIA engineering evaluation. Registration is not a security approval, installation, dependency pin, or production integration.

- Intake candidates: 29
- Newly added registry records: 29
- Candidate head revisions: `SYNC_REQUIRED` until the external-repository sync workflow verifies reachability and records exact heads.
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
| `OpenHands/openhands-aci` | SANDBOX_ONLY | agent-computer-interaction |
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
| `coder/agentapi` | SANDBOX_ONLY | agent-runtime-api |
| `aide/aide` | REFERENCE_ONLY | developer-agent-tooling-identity-unverified |
| `iamfakeguru/agent-md` | REFERENCE_ONLY | agent-instruction-conventions |

## Completion criteria

Intake is complete only when every candidate has an exact commit SHA, verified source URL, license disposition, security/test evidence, owner/reviewer, and a recorded acceptance/rejection decision. The sync workflow's head snapshot alone is not a security approval. Production use requires a separate reviewed change and existing AURELIA release gates.
