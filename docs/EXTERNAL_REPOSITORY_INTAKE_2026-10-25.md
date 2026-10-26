# External Repository Intake — 2026-10-25 / 2026-10-26

## Status

This is a controlled intake proposal for 81 repositories supplied for AURELIA engineering evaluation. The two 2026-10-26 batches contain 48 distinct repository references (the repeated Crypto-Signal URL in the earlier batch was deduplicated); 46 registry records were added across those batches and two existing records were refreshed as intake candidates. Registration is not a security approval, installation, dependency pin, or production integration.

- Intake candidates: 81 (56 BLOCKED; 25 UNREVIEWED)
- Newly added registry records across the PR: 79 (33 initial records, 21 from the first 2026-10-26 batch, and 25 from the new batch); 2 existing registry records refreshed as candidates
- Candidate head revisions: 81/81 pinned to exact commit SHAs. The initial 33 were captured on 2026-10-25; 48 additional distinct references were checked on 2026-10-26. Exact commit links and UTC author dates are recorded below. This is source provenance only, not a security approval.
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
| `ryfineZ/codex-session-patcher` | `main` | [`cf7deab2d5b2`](https://github.com/ryfineZ/codex-session-patcher/commit/cf7deab2d5b28c1f70f5b5498461848b69024a15) | 2026-10-05 | MIT declared in pyproject; LICENSE file missing | No | BLOCKED — refusal patching / prompt injection / reasoning erasure and license-file gap |
| `openai/codex-security` | `main` | [`796fa130e927`](https://github.com/openai/codex-security/commit/796fa130e92787085ab36aa4313d8c4bd9414560) | 2026-10-25 | Apache-2.0 | No | UNREVIEWED |
| `qxcnm/Codex-Manager` | `main` | [`430eddb0af9a`](https://github.com/qxcnm/Codex-Manager/commit/430eddb0af9ae6277f8133fbac7f8634b7699dc6) | 2026-10-18 | MIT | No | BLOCKED — sample Compose runs root/latest and exposes gateway service |
| `composio-community/awesome-codex-skills` | `master` | [`0930e1373789`](https://github.com/composio-community/awesome-codex-skills/commit/0930e1373789d2eda449039f7ac154b33031de89) | 2026-07-26 | NO LICENSE FILE | No | BLOCKED — no top-level license file |
| `router-for-me/CLIProxyAPI` | `main` | [`bc0643405a1d`](https://github.com/router-for-me/CLIProxyAPI/commit/bc0643405a1d0adf77dd0f109972ac3313d66397) | 2026-10-24 | MIT | No | BLOCKED — sample Compose exposes multiple ports and mounts auth/plugin directories |
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
| `Roibal/Cryptocurrency-Trading-Bots-Python-Beginner-Advance` | `master` | [`6cd9f639ac7f`](https://github.com/Roibal/Cryptocurrency-Trading-Bots-Python-Beginner-Advance/commit/6cd9f639ac7f9d914d556738ca3aeeef53618146) | 2019-01-18 | MIT | No | BLOCKED — legacy exchange code / stale snapshot |
| `x1xhlol/system-prompts-and-models-of-ai-tools` | `main` | [`162db92f54d7`](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools/commit/162db92f54d717d8ebd12292e155aeef32bb4b3c) | 2026-10-12 | GPL-3.0 | No | BLOCKED — third-party prompt provenance |
| `elder-plinius/CL4R1T4S` | `main` | [`a4d3da04e633`](https://github.com/elder-plinius/CL4R1T4S/commit/a4d3da04e63324e794a65500c3e41994fc4ab02e) | 2026-09-22 | AGPL-3.0 | No | BLOCKED — third-party prompt provenance |
| `dyad-sh/dyad` | `main` | [`1be2b4b6d2c7`](https://github.com/dyad-sh/dyad/commit/1be2b4b6d2c70a4550db7b96e26fc75c50bf5bc0) | 2026-10-22 | Apache-2.0 / FSL-1.1-ALv2 in `src/pro` | No | UNREVIEWED — mixed license |

**Pinned set:** 33/33. **Blocked pending prerequisites:** twelve. **Security/functional source audits and isolated tests:** not yet completed. `coder/agentapi` is archived and its pinned commit subject explicitly says deprecated and unmaintained; OpenHands ACI and `b-nnett/goose` are archived; the no-license skill/session/prompt sources are blocked from installation or redistribution; OpenHands Cloud is blocked for adoption pending legal review of its restrictive license; legacy Roibal trading code and third-party prompt collections are blocked pending security, provenance and license review.

Pinning establishes provenance only. It does not establish license compatibility, benign behavior, maintainability, successful installation, test coverage, or fitness for AURELIA.

---
## Candidate inventory

| Repository | Preliminary mode | Main review focus |
|---|---|---|
| `iOfficeAI/OfficeCLI` | TOOLCHAIN_ONLY | office-document-agent-tool |
| `Jia-Ethan/codex-keysmith` | SANDBOX_ONLY | agent-instruction-management |
| `Loongphy/codex-auth` | SANDBOX_ONLY | credential-account-manager |
| `ryfineZ/codex-session-patcher` | REFERENCE_ONLY (BLOCKED) | session-modification-tool / refusal-patching / prompt-injection |
| `openai/codex-security` | TOOLCHAIN_ONLY | code-security-assurance |
| `qxcnm/Codex-Manager` | REFERENCE_ONLY (BLOCKED) | coding-agent-account-management |
| `composio-community/awesome-codex-skills` | REFERENCE_ONLY (BLOCKED) | agent-skills-catalog / no license file |
| `router-for-me/CLIProxyAPI` | REFERENCE_ONLY (BLOCKED) | llm-api-proxy |
| `OpenHands/OpenHands` | SANDBOX_ONLY | coding-agent-application |
| `OpenHands/software-agent-sdk` | SANDBOX_ONLY | coding-agent-sdk |
| `OpenHands/extensions` | REFERENCE_ONLY | agent-extension-registry |
| `OpenHands/OpenHands-CLI` | SANDBOX_ONLY | coding-agent-cli |
| `OpenHands/automation` | SANDBOX_ONLY | agent-automation-orchestration |
| `OpenHands/openhands-aci` | REFERENCE_ONLY (BLOCKED) | agent-computer-interaction |
| `OpenHands/OpenHands-Cloud` | REFERENCE_ONLY (BLOCKED) | hosted-agent-platform / restrictive license |
| `cline/cline` | SANDBOX_ONLY | coding-agent-extension |
| `cline/prompts` | REFERENCE_ONLY (BLOCKED) | agent-prompt-library / no license file |
| `decolua/9router` | SANDBOX_ONLY | llm-api-router |
| `aaif-goose/goose` | SANDBOX_ONLY | coding-agent-framework |
| `pressly/goose` | TOOLCHAIN_ONLY | database-migration-tool |
| `b-nnett/goose` | REFERENCE_ONLY (BLOCKED) | goose-project-identity-unverified / archived / no license file |
| `gooseworks-ai/goose-skills` | REFERENCE_ONLY | agent-skills-library |
| `mz-automation/libiec61850` | REFERENCE_ONLY | industrial-protocol-library |
| `tag1consulting/goose` | TOOLCHAIN_ONLY | rust-load-testing-tool |
| `Aider-AI/aider` | SANDBOX_ONLY | coding-agent |
| `hotovo/aider-desk` | SANDBOX_ONLY | coding-agent-ui |
| `coder/agentapi` | REFERENCE_ONLY (BLOCKED) | agent-runtime-api (deprecated/unmaintained signal) |
| `aide/aide` | REFERENCE_ONLY | developer-agent-tooling-identity-unverified |
| `iamfakeguru/agent-md` | REFERENCE_ONLY | agent-instruction-conventions |
| `Roibal/Cryptocurrency-Trading-Bots-Python-Beginner-Advance` | REFERENCE_ONLY (BLOCKED) | legacy trading code / credential and exchange API review |
| `x1xhlol/system-prompts-and-models-of-ai-tools` | REFERENCE_ONLY (BLOCKED) | third-party AI prompt collection / provenance and license |
| `elder-plinius/CL4R1T4S` | REFERENCE_ONLY (BLOCKED) | third-party AI prompt collection / AGPL and provenance |
| `dyad-sh/dyad` | REFERENCE_ONLY | local AI app builder / mixed license and sandbox review |

## Completion criteria

Intake is complete only when every candidate has an exact commit SHA, verified source URL, license disposition, security/test evidence, owner/reviewer, and a recorded acceptance/rejection decision. The sync workflow's head snapshot alone is not a security approval. Production use requires a separate reviewed change and existing AURELIA release gates.


## Additional intake batch — 2026-10-26

The following 23 distinct references were added to the review set. SHA values and dates are GitHub's observed default-branch latest commit metadata; this is source provenance, not security clearance. Two records already existed in the registry and were refreshed instead of duplicated.

| Repository | Branch | Pinned commit | Author date (UTC) | License metadata | Status |
|---|---|---|---|---|---|
| Adamant-im/adamant-tradebot | dev | [9f81feaab1404961a764ddbecc6cc225c94e0b10](https://github.com/Adamant-im/adamant-tradebot/commit/9f81feaab1404961a764ddbecc6cc225c94e0b10) | 2026-08-02 | NOASSERTION | BLOCKED |
| Mintplex-Labs/anythingllm-docs | main | [bc510c6d4692c8b09945c331ccb470e6efa74b1a](https://github.com/Mintplex-Labs/anythingllm-docs/commit/bc510c6d4692c8b09945c331ccb470e6efa74b1a) | 2026-10-26 | MIT | UNREVIEWED |
| hackobi/AI-Scalpel-Trading-Bot | master | [30eed4130d4808a25a5be6a0ee6cf42e3f19bc22](https://github.com/hackobi/AI-Scalpel-Trading-Bot/commit/30eed4130d4808a25a5be6a0ee6cf42e3f19bc22) | 2023-08-24 | GPL-3.0 | BLOCKED |
| dsmsmj/vercel-labs-agent-skills | main | [ac6a79af08f6d32c34ee03c829824990f3de0a6d](https://github.com/dsmsmj/vercel-labs-agent-skills/commit/ac6a79af08f6d32c34ee03c829824990f3de0a6d) | 2026-01-18 | NOASSERTION | BLOCKED |
| minhlucvan/agent-browser-mcp | main | [638b7093f47df42ac4688ae9ebcbca7470bb6c98](https://github.com/minhlucvan/agent-browser-mcp/commit/638b7093f47df42ac4688ae9ebcbca7470bb6c98) | 2026-05-23 | NOASSERTION | BLOCKED |
| Qian-Anton/GitStudy | main | [fbf2e88f5d7b46b7631336443c9b5aac808df2d5](https://github.com/Qian-Anton/GitStudy/commit/fbf2e88f5d7b46b7631336443c9b5aac808df2d5) | 2026-05-09 | NOASSERTION | BLOCKED |
| kevincm89/https-github.com-vercel-labs-skills | claude/vibrant-pasteur-hvbJE | [075c5d438165f6bd877f936a4b6c3286f79eec95](https://github.com/kevincm89/https-github.com-vercel-labs-skills/commit/075c5d438165f6bd877f936a4b6c3286f79eec95) | 2026-05-23 | NOASSERTION | BLOCKED |
| koreainvestment/open-trading-api | main | [cd63caee6aeb90553d506b15ab6866cfad23beda](https://github.com/koreainvestment/open-trading-api/commit/cd63caee6aeb90553d506b15ab6866cfad23beda) | 2026-10-23 | NOASSERTION | BLOCKED |
| onchain-trading-bot/.github | main | [d777aaf6e032dddcbc3ce68846b65bc23f12a3e5](https://github.com/onchain-trading-bot/.github/commit/d777aaf6e032dddcbc3ce68846b65bc23f12a3e5) | 2026-10-23 | NOASSERTION | BLOCKED |
| starwiz-7/StalkStock | main | [7f3034a52c63ec9117f45d03e9ad64d98bee4d1d](https://github.com/starwiz-7/StalkStock/commit/7f3034a52c63ec9117f45d03e9ad64d98bee4d1d) | 2021-09-01 | GPL-3.0 | BLOCKED |
| Options-Visualizer/Options-Visualizer.github.io | source | [d275ba222638f92747f3434599f8d51bac76405b](https://github.com/Options-Visualizer/Options-Visualizer.github.io/commit/d275ba222638f92747f3434599f8d51bac76405b) | 2020-09-02 | NOASSERTION | BLOCKED |
| traderwillhu/market_dashboard | main | [5740a1523f2d8caac25072bc7b675ed6ff258716](https://github.com/traderwillhu/market_dashboard/commit/5740a1523f2d8caac25072bc7b675ed6ff258716) | 2026-03-10 | NOASSERTION | BLOCKED |
| df-tools-bn/.github | main | [3c35faf4e84e681d24d0cd3a5915bc7822d8ff60](https://github.com/df-tools-bn/.github/commit/3c35faf4e84e681d24d0cd3a5915bc7822d8ff60) | 2026-10-23 | NOASSERTION | BLOCKED |
| learn-crypto-trading/learn-crypto-trading.github.io | master | [1ed31e8751c2e3789ce1f2b098fab0599ccd4532](https://github.com/learn-crypto-trading/learn-crypto-trading.github.io/commit/1ed31e8751c2e3789ce1f2b098fab0599ccd4532) | 2023-02-24 | CC0-1.0 | UNREVIEWED |
| TradingGoose/TradingGoose.github.io | main | [c9ee488499fd0c7f98f5ece6a4680ac2fc11011a](https://github.com/TradingGoose/TradingGoose.github.io/commit/c9ee488499fd0c7f98f5ece6a4680ac2fc11011a) | 2026-04-22 | AGPL-3.0 | BLOCKED |
| TradingAgents-AI/TradingAgents-AI.github.io | main | [d007e8858fbc64844dab2a6c1786fe2cc2355729](https://github.com/TradingAgents-AI/TradingAgents-AI.github.io/commit/d007e8858fbc64844dab2a6c1786fe2cc2355729) | 2025-07-05 | NOASSERTION | BLOCKED |
| CryptoSignal/Crypto-Signal | master | [7cb9c5c6cd226c6fe2d345e4bda3bec8156cefec](https://github.com/CryptoSignal/Crypto-Signal/commit/7cb9c5c6cd226c6fe2d345e4bda3bec8156cefec) | 2022-08-09 | MIT | BLOCKED |
| twentyhq/twenty | main | [3ffa71331e1d4f120c42abcdbc933ccf51b93fcb](https://github.com/twentyhq/twenty/commit/3ffa71331e1d4f120c42abcdbc933ccf51b93fcb) | 2026-10-26 | NOASSERTION | BLOCKED |
| zurb/twentytwenty | master | [a7b4057817bb098f554c5626a19c3d5ae14b280b](https://github.com/zurb/twentytwenty/commit/a7b4057817bb098f554c5626a19c3d5ae14b280b) | 2018-11-27 | ISC | UNREVIEWED |
| aiwebarchitects/hyperliquid_free_trading_bot | main | [149f53bbd992602c68295e0cb41bd4834d13e9c6](https://github.com/aiwebarchitects/hyperliquid_free_trading_bot/commit/149f53bbd992602c68295e0cb41bd4834d13e9c6) | 2025-10-15 | Apache-2.0 | BLOCKED |
| Cryptotrademate/cryptotrademate-trading-bot | main | [33ca3ad65221ec699d07aa5c071dc2114430ed97](https://github.com/Cryptotrademate/cryptotrademate-trading-bot/commit/33ca3ad65221ec699d07aa5c071dc2114430ed97) | 2025-01-22 | MIT | BLOCKED |
| asba-IA/Github-Mev-Bot | main | [5b7a9f2c8552f6dfc9f259aea214bd6e2efc5e95](https://github.com/asba-IA/Github-Mev-Bot/commit/5b7a9f2c8552f6dfc9f259aea214bd6e2efc5e95) | 2025-04-26 | NOASSERTION | BLOCKED |
| CMZ33/Github-Mev-Bot | master | [38a67f0aa34b01a10e22ceab752aac6900de58dd](https://github.com/CMZ33/Github-Mev-Bot/commit/38a67f0aa34b01a10e22ceab752aac6900de58dd) | 2025-03-24 | MIT | BLOCKED |

Licensing note: NOASSERTION means GitHub metadata returned no recognized SPDX identifier; it does not prove a license file is absent. Candidates so marked remain blocked where shown until actual license terms are reviewed. Repeated CryptoSignal/Crypto-Signal input was recorded once. No candidate code, scripts, skills, dependencies, or broker integrations were installed or executed.


## Additional intake batch — 2026-10-26 (agent/mobile and trading projects)

This batch contains 25 distinct repositories. Default branches, latest commit SHAs and commit-author dates were retrieved through GitHub's public API. The license column records GitHub repository metadata, not a legal determination. All candidates are reference-only. Twenty-four are BLOCKED pending the repository-specific reviews captured in the registry; `didi/Hummer` remains UNREVIEWED because it is a general mobile framework and still requires source/dependency review. No code was installed or executed, no agent/device/call gateway was connected, and no credentials were supplied.

| Repository | Branch | Pinned commit | Author date (UTC) | GitHub license metadata | Intake status |
|---|---|---|---|---|---|
| Haehnchen/crypto-trading-bot | master | [cb9563344a20ea7ac89ff214d350f141d1521219](https://github.com/Haehnchen/crypto-trading-bot/commit/cb9563344a20ea7ac89ff214d350f141d1521219) | 2026-08-02 | MIT | BLOCKED |
| HenWorks/Hermes-agent-android-PC-companion-app | main | [bcae80000db4f3a372664357b08eb2150651ca1c](https://github.com/HenWorks/Hermes-agent-android-PC-companion-app/commit/bcae80000db4f3a372664357b08eb2150651ca1c) | 2026-09-04 | AGPL-3.0 | BLOCKED |
| didi/Hummer | master | [ba0d5be2054f00a1014877c81f34f093ca7486b0](https://github.com/didi/Hummer/commit/ba0d5be2054f00a1014877c81f34f093ca7486b0) | 2025-10-29 | Apache-2.0 | UNREVIEWED |
| sidinsearch/AgentCall | main | [9c80cfe99707861869016227cb5e8f19683adc75](https://github.com/sidinsearch/AgentCall/commit/9c80cfe99707861869016227cb5e8f19683adc75) | 2026-08-02 | AGPL-3.0 | BLOCKED |
| sesori-ai/sesori_apps_monorepo | main | [9cc801c2903f33a8772d16c358624518cc2ef483](https://github.com/sesori-ai/sesori_apps_monorepo/commit/9cc801c2903f33a8772d16c358624518cc2ef483) | 2026-10-26 | NOASSERTION | BLOCKED |
| l3ad3r1/Hermes-Agent-Android | main | [a08497b979d6241387bc15cde7c57279d0b2cc10](https://github.com/l3ad3r1/Hermes-Agent-Android/commit/a08497b979d6241387bc15cde7c57279d0b2cc10) | 2026-10-07 | MIT | BLOCKED |
| Binair-Dev/HermesAgentMobile | main | [b68f921d9ba2f75344356b607157260564c8fad6](https://github.com/Binair-Dev/HermesAgentMobile/commit/b68f921d9ba2f75344356b607157260564c8fad6) | 2026-04-10 | MIT | BLOCKED |
| amirghm/hermes-agent-mobile | main | [4a9cf07702bab44a191d7bd6ee3bd387edef467a](https://github.com/amirghm/hermes-agent-mobile/commit/4a9cf07702bab44a191d7bd6ee3bd387edef467a) | 2026-06-30 | NOASSERTION | BLOCKED |
| xP3ta/hermes-console | main | [f80fae7239e88234e3d62ac1eebbf96d68f00803](https://github.com/xP3ta/hermes-console/commit/f80fae7239e88234e3d62ac1eebbf96d68f00803) | 2026-10-25 | GPL-3.0 | BLOCKED |
| sesaloy/hermes-mobile | main | [5181095a0878b37adc2ccb63710b42f2fba2719a](https://github.com/sesaloy/hermes-mobile/commit/5181095a0878b37adc2ccb63710b42f2fba2719a) | 2026-07-14 | MIT | BLOCKED |
| marshallrichards/ClawPhone | main | [b224a589b06ee8de27bc57dde3f3695359d1f60c](https://github.com/marshallrichards/ClawPhone/commit/b224a589b06ee8de27bc57dde3f3695359d1f60c) | 2026-05-25 | NOASSERTION | BLOCKED |
| jeromeleeqy-hash/Hermes-Android | main | [65aedfa629403f70f907c3b6387b27ef498ae57b](https://github.com/jeromeleeqy-hash/Hermes-Android/commit/65aedfa629403f70f907c3b6387b27ef498ae57b) | 2026-10-05 | NOASSERTION | BLOCKED |
| unsupportedpastels/mercury | main | [cc634c922b8a171e4c500a5851a3ca6e740d7fe6](https://github.com/unsupportedpastels/mercury/commit/cc634c922b8a171e4c500a5851a3ca6e740d7fe6) | 2026-09-20 | MIT | BLOCKED |
| omarqaterge/hermes-mobile-app | main | [c8688096f74c8b01b1a49b7dbf9123eb98f7c717](https://github.com/omarqaterge/hermes-mobile-app/commit/c8688096f74c8b01b1a49b7dbf9123eb98f7c717) | 2026-10-26 | MIT | BLOCKED |
| adebnar/hermes-android | main | [9f08f39ed2b9fc7cb29a551b1d9b695a409fdb7a](https://github.com/adebnar/hermes-android/commit/9f08f39ed2b9fc7cb29a551b1d9b695a409fdb7a) | 2026-07-20 | GPL-3.0 | BLOCKED |
| getpaseo/paseo | main | [65ce4b590a09106372c555cb7322f6da73b9d419](https://github.com/getpaseo/paseo/commit/65ce4b590a09106372c555cb7322f6da73b9d419) | 2026-10-26 | NOASSERTION | BLOCKED |
| reactnativecn/react-native-update | master | [4620119b37d40e16f51a119bd2d613e12a316cd4](https://github.com/reactnativecn/react-native-update/commit/4620119b37d40e16f51a119bd2d613e12a316cd4) | 2026-10-21 | NOASSERTION | BLOCKED |
| hermes-webui/hermes-android | main | [9c35a2fd0cf0fbf8f688dc283e86a3cae1258c2f](https://github.com/hermes-webui/hermes-android/commit/9c35a2fd0cf0fbf8f688dc283e86a3cae1258c2f) | 2026-10-25 | NOASSERTION | BLOCKED |
| Hy4ri/hermes-mobile | main | [f03426df599d36b003b10ce29516434e591aef82](https://github.com/Hy4ri/hermes-mobile/commit/f03426df599d36b003b10ce29516434e591aef82) | 2026-10-26 | Apache-2.0 | BLOCKED |
| Giton22/herald | master | [687d80e3e6b6bbf2199086ff1d780b07e57bc88c](https://github.com/Giton22/herald/commit/687d80e3e6b6bbf2199086ff1d780b07e57bc88c) | 2026-10-24 | MIT | BLOCKED |
| AbuZar-Ansarii/Hermes-Agent-On-Android | main | [4d2427c2d6dc6a7683ec9c9d4efab9114abe17cc](https://github.com/AbuZar-Ansarii/Hermes-Agent-On-Android/commit/4d2427c2d6dc6a7683ec9c9d4efab9114abe17cc) | 2026-08-13 | NOASSERTION | BLOCKED |
| Xiaofei-it/Hermes | master | [262039098b407f40f8298e6bbb3ca173a9fe2322](https://github.com/Xiaofei-it/Hermes/commit/262039098b407f40f8298e6bbb3ca173a9fe2322) | 2017-05-05 | NOASSERTION | BLOCKED |
| rusty4444/hermes-android | main | [3f26dd528224e21bc6ae3efcc5dc18912efb7f52](https://github.com/rusty4444/hermes-android/commit/3f26dd528224e21bc6ae3efcc5dc18912efb7f52) | 2026-10-26 | MIT | BLOCKED |
| Codename-11/hermes-relay | main | [da782a8d74eb6631ea2f097b3cc69c6452ec33de](https://github.com/Codename-11/hermes-relay/commit/da782a8d74eb6631ea2f097b3cc69c6452ec33de) | 2026-10-20 | MIT | BLOCKED |
| cogwheel0/conduit | main | [0f5c598aebaab02779b4bdbdb050e8e040ba2e9b](https://github.com/cogwheel0/conduit/commit/0f5c598aebaab02779b4bdbdb050e8e040ba2e9b) | 2026-10-26 | GPL-3.0 | BLOCKED |

**Security focus:** the mobile/agent clients, remote-control bridges, and orchestrators are not interchangeable with trusted integrations. They remain blocked pending source/provenance, credential storage, agent tool/side-effect scope, network/TLS, permission, subprocess, data privacy, and license review. The crypto trading bot remains blocked pending exchange API permission, secret handling, order-write and cost-adjusted test review. `NOASSERTION` is a metadata signal and does not prove that a license file is absent. No candidate has been approved for installation, runtime use, broker access or capital authority.
