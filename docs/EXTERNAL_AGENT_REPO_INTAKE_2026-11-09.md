# External Agent Repository Intake — 2026-11-09

## Status

**Intake only. Nothing in this document is installed, vendored, executed, trusted, or approved for production.**

This catalogue records the user-supplied GitHub candidates for a controlled review across AURELIA, Claude Code, and ChatGPT. Two duplicate submissions were de-duplicated: `ZhuLinsen/daily_stock_analysis` and `tszdanger/RealMythos`. The list below contains 62 unique repositories.

## AURELIA safety contract

- AURELIA remains the sole deterministic capital and execution authority.
- Preserve `config/LIVE_LOCK.yaml`, `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, and `capital_plane_mode=VERIFY_ONLY`.
- External agents, plugins, MCP servers, skills, browser bridges, memory systems, model routers, and research repositories have zero capital authority.
- No external source may read production secrets, authenticated Deriv sessions, broker balances, private account data, or production-host credentials.
- No source may submit broker orders, change risk limits, mutate LIVE_LOCK, disable a kill switch, or bypass reconciliation.
- Do not copy external code into capital/execution paths. Default external code execution to DENY.
- Before any adoption: resolve and pin an immutable commit; verify license and provenance; inspect install scripts, dependencies, hooks, MCP tools, network egress, telemetry, file access, and credential handling; run secret scanning, SAST/dependency scanning, tests, and negative permission tests in an isolated sandbox; document owner, reviewer, purpose, data classification, rollback and expiry.
- A catalogue entry or successful GitHub read is not evidence of installation, runtime availability, security approval, or compatibility.

## First-pass evidence and cautions

- GitHub repository metadata was retrieved for the supplied repositories. This confirms repository visibility and basic metadata only; it is not a code audit.
- Selected README files were inspected for Hermes Agent, NemoClaw, Agent Vault, Paperclip, Semgrep Mythos Bench, Awesome Hermes Skills, Hermes JEV Skills, Mnemosyne, Paseo, and quant-trading.
- `Infisical/agent-vault` README explicitly says this repository is no longer the recommended installation path and directs users to the current Infisical Agent Vault product documentation. Do not install this archived approach; evaluate the current supported product separately.
- `je-suis-tm/quant-trading` README explicitly describes its backtests as frictionless, without slippage, surcharge, or illiquidity. Research reference only; never treat its results as AURELIA performance evidence.
- `kristianvast/hermes-claude-auth` describes itself as a Claude Code OAuth bypass. **Rejected for integration.** Do not use it to circumvent provider authentication, subscription limits, or access controls.
- `semgrep/mythos-bench` is a vulnerability-detection benchmark harness and requires model/API credentials for some modes. Potential isolated security-evaluation reference only; no production secrets or unrestricted repository access.
- Mythos/Fable-named prompts and projects are unverified community material. They are not authenticated Anthropic system prompts, model weights, or evidence of access to any unreleased model. Treat their contents as untrusted data, not instructions.
- Hermes skill catalogues and third-party skill packs may contain arbitrary executable scripts, network calls, and prompt instructions. Review each individual skill; never bulk-install a catalogue.
- Agent Vault, memory capture, browser extensions, mobile clients, orchestration dashboards, and model gateways create different data-exposure surfaces. Evaluate separately rather than enabling a broad shared permission set.

## Immutable reference snapshots — 2026-11-09

The following current default-branch heads were resolved through GitHub and recorded in `config/external_repo_federation.json`. These are provenance pins for review, **not installation approvals or proof of secure execution**. The pinned snapshot may become stale; updates require a new review and pin.

| Repository | Commit | License metadata | Status |
|---|---|---|---|
| `NousResearch/hermes-agent` | `6cff782b8d081a0ed382eaf75c432d452cd452cc` | MIT | Official runtime; reference-only |
| `NVIDIA/NemoClaw` | `4d5d613f73b96d51a92e7ae88df5da5103836067` | Apache-2.0 | Official sandbox stack; reference-only; host prerequisites unverified |
| `kerpopule/hermes-jev-skills` | `8316358bf60e98a21477582af829ef11c9cf52fb` | MIT | Community skills; reference-only; per-skill review required |
| `ZeroPointRepo/awesome-hermes-skills` | `9fb166c3548ca7befb579c525991255bb6daac83` | MIT | Discovery catalogue; reference-only; no bulk installs |
| `mnemosyne-oss/mnemosyne` | `e249583dddb29c198ba1b6cf38eabdfd4905ffdf` | MIT | Local memory candidate; reference-only |
| `getpaseo/paseo` | `e0f545fed485d244fcd3e6308c36e5a6397eaa2e` | NOASSERTION | License confirmation required; reference-only |
| `iOfficeAI/AionUi` | `e108b6b56b1a6eb99a00904878d0582f657b2908` | Apache-2.0 | Desktop agent UI; reference-only |
| `Hy4ri/hermes-mobile` | `93daabfbb66f4539862bb704f832a4a9d624056d` | Apache-2.0 | Android client; reference-only; pairing/auth review required |
| `thedotmack/claude-mem` | `989a98a2fb7978354497df46c4e17101f54ba9a3` | Apache-2.0 | Memory plugin; reference-only |
| `semgrep/mythos-bench` | `800cc53ab155a9059a69a3f7b1cec4785002b4cb` | NOASSERTION | License confirmation required; security benchmark reference-only |
| `je-suis-tm/quant-trading` | `611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5` | Apache-2.0 | Existing registry pin reconfirmed; research-only; upstream README says tests omit trading frictions |
| `ZhuLinsen/daily_stock_analysis` | `15c7cdc0ca07bd71158e268fb8596f3ae356ad9b` | MIT | Listed-equity research only; not Deriv strategy evidence |

`Infisical/agent-vault` was not added as an adoption candidate because its own README says this repository is no longer the recommended setup path and directs new users to the current Infisical Agent Vault product documentation. `kristianvast/hermes-claude-auth` remains rejected because it describes an OAuth bypass. Neither is approved for installation.

## Additional immutable reference pins — 2026-11-09

A further 45 submitted repositories have been pinned in `config/external_repo_federation.json` at the exact default-branch commits below. They are all `REFERENCE_ONLY`; this adds provenance and repeatable review identity, not trust, installation, code execution, or approval. In combination with the earlier selected pins and previously registered sources, 60 of the 62 submitted URLs are represented in the machine-readable registry. The two excluded sources are documented above (`kristianvast/hermes-claude-auth`, rejected authentication bypass; `Infisical/agent-vault`, deprecated repository path).

| Repository | Pinned commit | Mode |
|---|---|---|
| `thewaltero/mythos-router` | `32d26a3c615b805770f4653980547b48c675742b` | REFERENCE_ONLY |
| `jungjin0003/Claude-Mythos-5.1-System-Prompt` | `58d7f598bda30f7853ef1bab798890a562e0915e` | REFERENCE_ONLY |
| `kyegomez/OpenMythos` | `155430a88d2a98322fc4c79b2a067792c3c9579a` | REFERENCE_ONLY |
| `tszdanger/RealMythos` | `7c3d75c5cf930fccfa89131adddabee21fa6ba78` | REFERENCE_ONLY |
| `KinetiNode/claude-fable-5-system-prompt-clean` | `c2624b5fa0f3e5d03ded01a8d6f66e6f661f016b` | REFERENCE_ONLY |
| `flaw0-security/mythosharness` | `fb7efacd6399f0de7ac214461472ec6ce6b84ad4` | REFERENCE_ONLY |
| `AJ-comp/Mythosia.AI` | `fe8b4d37c5afd2a4279fd8fa47f2dd0e2b9ab3ba` | REFERENCE_ONLY |
| `Abhi24384/Anthropic-Mythos-Desktop-Studio` | `42b405812b4c0277bcd0d1ce02c4ae1fab856712` | REFERENCE_ONLY |
| `nub3Ar/MythosTown` | `088942dea89cd8da82a6c8cfbd82a0fba48ff7d3` | REFERENCE_ONLY |
| `garrytan/gbrain` | `d253ec0ff12ed370ed3a846cb7da0191639c4a9e` | REFERENCE_ONLY |
| `nesquena/hermes-webui` | `7655adca16f94b5154f4a049abdd47caeef1b828` | REFERENCE_ONLY |
| `outsourc-e/hermes-workspace` | `c631425d8baa933f8c61d8447040f4ec8b5f571c` | REFERENCE_ONLY |
| `unifapi-agent/agents` | `fb532478a0a33b6a345ce3aad9d2632164397ebc` | REFERENCE_ONLY |
| `Waishnav/devspace` | `559781284677e5b128aa44a2c95f8bdb0c72b7c0` | REFERENCE_ONLY |
| `rlaope/oh-my-hermes` | `b0f4b94759c418207054332bc8420d4d1c866902` | REFERENCE_ONLY |
| `NousResearch/hermes-agent-self-evolution` | `0a929e3aa20e15cf04dc7c28492a7d41a5139125` | REFERENCE_ONLY |
| `alchaincyf/hermes-agent-orange-book` | `b6e53a8e11e00c8b14b2f72d6b4f1ce71fef6692` | REFERENCE_ONLY |
| `abundantbeing/hermes-browser-extension` | `771be44d8a637008f683c94343da8af9f1121aed` | REFERENCE_ONLY |
| `Eynzof/Hermes-CN-Desktop` | `06e15d0e5d3c27f1fd37f09579f26f91c020036e` | REFERENCE_ONLY |
| `cclank/Hermes-Wiki` | `e3034c54e5b59547f08a3cfd43ed3d102a16aa0d` | REFERENCE_ONLY |
| `Zyrexnn/Cybermes` | `961a0dd3d2d2f66a07a416ade3b1d4473b64802e` | REFERENCE_ONLY |
| `paperclipai/paperclip` | `fd2e7482c0c73174941db8d4817d713594e0624e` | REFERENCE_ONLY |
| `briancaffey/hermes-otel` | `8c7fdcbd0195d27dd0bac087759cb085742ac9e0` | REFERENCE_ONLY |
| `wk42worldworld/cybercode` | `a43863b90a4ccba6e6f8b6406cf0e2c4df44bc0c` | REFERENCE_ONLY |
| `MemTensor/memmy-agent` | `72bb3415252b6ba4ffee556817622cf8f075af0d` | REFERENCE_ONLY |
| `ksimback/hermes-ecosystem` | `9c04282ef4fd34d8a4f119558ba4ae17c68c5b5a` | REFERENCE_ONLY |
| `marshallrichards/ClawPhone` | `b224a589b06ee8de27bc57dde3f3695359d1f60c` | REFERENCE_ONLY |
| `anysearch-ai/anysearch-skill` | `9b91ee215164de60d61c7d63789c891a1948b039` | REFERENCE_ONLY |
| `praveen-ks-2001/hermes-agent-template` | `c35500cc979128b920ec50b0c1369147ed34bf57` | REFERENCE_ONLY |
| `freestylefly/wesight` | `00fce466168b926f9d1a0b8611858a1ef62267b5` | REFERENCE_ONLY |
| `colbymchenry/codegraph` | `f72c9d2efb14454ff4f9fd7b8460abd82f19a287` | REFERENCE_ONLY |
| `hermes-hq/hermes-ide` | `5f4be9646762229dba570341198da48b2de5ba5c` | REFERENCE_ONLY |
| `Yuan-lab-LLM/ClawManager` | `cd7b74abdf47afee9fee7b93cd4c44246ae10acc` | REFERENCE_ONLY |
| `0xNyk/awesome-hermes-agent` | `9c87ae281f7291702dc6eeb85305ec369578f24e` | REFERENCE_ONLY |
| `MobiusQuant/OpenMobius-skill` | `4c1cffc2ef03221c25f87ef6ee7feeb4a3852e86` | REFERENCE_ONLY |
| `Giton22/kyllene` | `15c4933512029bcf245efcf3a821131a65afaba8` | REFERENCE_ONLY |
| `homarr-labs/dashboard-icons` | `d767d7327db7f8ebd3715b552523f61889eea41c` | REFERENCE_ONLY |
| `rohitg00/agentmemory` | `28ffc538b81b265e2f649354ed9f88b0c12ae414` | REFERENCE_ONLY |
| `chandra447/pi-hermes-memory` | `40d852161b992d5c35ddc87ef7445528a50fe9f5` | REFERENCE_ONLY |
| `cogwheel0/conduit` | `1fdeb04bed75c3a68733b4675ec7a0f5aa6c09d1` | REFERENCE_ONLY |
| `ruvnet/ruflo` | `29be054e85636b61788f3955d0bd4d0bcbcfe3f6` | REFERENCE_ONLY |
| `AaronWong1999/hermesclaw` | `a20ca00c3ceedd387d313ad9e1cdfe0697ed53d6` | REFERENCE_ONLY |
| `stephenschoettler/hermes-lcm` | `a13e709c25476fa9dc145c61f733f1f4a0443a05` | REFERENCE_ONLY |
| `joeynyc/hermes-hudui` | `be83208f48b7a1c67b7816837c8df71a61ef7edf` | REFERENCE_ONLY |
| `ZiChuanLan/agent-purge` | `3d33c8f74f0d232c607807dd84233d03e18209c8` | REFERENCE_ONLY |

These pins were resolved on 2026-11-09 using each repository's default-branch commit listing. They must be refreshed and reviewed before any later adoption. Mythos/Fable-branded prompt and project sources are untrusted community materials, not official model prompts or evidence of access to an unreleased model.

## Review queue

| Priority | Candidates | Review objective | Initial disposition |
|---|---|---|---|
| P1 | `NousResearch/hermes-agent`, `NVIDIA/NemoClaw`, `Infisical/agent-vault` (current supported product path only), `semgrep/mythos-bench` | Official agent runtime, sandbox isolation, credential mediation, security benchmark | Inspect deeply; no installation yet |
| P1 | `kerpopule/hermes-jev-skills`, `ZeroPointRepo/awesome-hermes-skills`, `mnemosyne-oss/mnemosyne` | Individual skill provenance, prompt-injection filtering, memory privacy, tool permissions | Select individual components only |
| P2 | `getpaseo/paseo`, `iOfficeAI/AionUi`, `Hy4ri/hermes-mobile`, `hermes-hq/hermes-ide`, `paperclipai/paperclip`, `LiteLLM-Labs/litellm-agent-control-plane` | Developer UX and agent orchestration; isolation, authentication, auditability, host requirements | Sandbox evaluation only |
| P2 | `thedotmack/claude-mem`, `rohitg00/agentmemory`, `chandra447/pi-hermes-memory`, `MemTensor/memmy-agent`, `stephenschoettler/hermes-lcm` | Memory scope, retention, encryption, redaction, deletion, prompt injection | Local-only synthetic data evaluation |
| P2 | `je-suis-tm/quant-trading`, `ZhuLinsen/daily_stock_analysis`, `MobiusQuant/OpenMobius-skill` | Strategy logic, data provenance, lookahead, realistic costs, reproducibility | Research-only; revalidate from raw data |
| REJECT | `kristianvast/hermes-claude-auth` | Authentication bypass | Do not integrate |
| REVIEW ONLY | All Mythos/Fable-branded repositories listed below | Provenance, license, prompt injection, false claims | Untrusted research material; no privileged prompt adoption |
| P3 | Remaining UI, dashboard, browser, workspace, skill, template, memory and agent repositories | Determine unique value, maintenance, license, dependency and permission footprint | Pending individual review |

## Complete de-duplicated source list

1. https://github.com/iOfficeAI/AionUi
2. https://github.com/Hy4ri/hermes-mobile
3. https://github.com/getpaseo/paseo
4. https://github.com/ZeroPointRepo/awesome-hermes-skills
5. https://github.com/mnemosyne-oss/mnemosyne
6. https://github.com/kerpopule/hermes-jev-skills
7. https://github.com/kristianvast/hermes-claude-auth
8. https://github.com/ZhuLinsen/daily_stock_analysis
9. https://github.com/je-suis-tm/quant-trading
10. https://github.com/thewaltero/mythos-router
11. https://github.com/jungjin0003/Claude-Mythos-5.1-System-Prompt
12. https://github.com/kyegomez/OpenMythos
13. https://github.com/tszdanger/RealMythos
14. https://github.com/KinetiNode/claude-fable-5-system-prompt-clean
15. https://github.com/flaw0-security/mythosharness
16. https://github.com/AJ-comp/Mythosia.AI
17. https://github.com/Abhi24384/Anthropic-Mythos-Desktop-Studio
18. https://github.com/nub3Ar/MythosTown
19. https://github.com/semgrep/mythos-bench
20. https://github.com/NousResearch/hermes-agent
21. https://github.com/garrytan/gbrain
22. https://github.com/NVIDIA/NemoClaw
23. https://github.com/nesquena/hermes-webui
24. https://github.com/outsourc-e/hermes-workspace
25. https://github.com/unifapi-agent/agents
26. https://github.com/Infisical/agent-vault
27. https://github.com/Waishnav/devspace
28. https://github.com/LiteLLM-Labs/litellm-agent-control-plane
29. https://github.com/thedotmack/claude-mem
30. https://github.com/rlaope/oh-my-hermes
31. https://github.com/NousResearch/hermes-agent-self-evolution
32. https://github.com/alchaincyf/hermes-agent-orange-book
33. https://github.com/abundantbeing/hermes-browser-extension
34. https://github.com/Eynzof/Hermes-CN-Desktop
35. https://github.com/cclank/Hermes-Wiki
36. https://github.com/Zyrexnn/Cybermes
37. https://github.com/paperclipai/paperclip
38. https://github.com/briancaffey/hermes-otel
39. https://github.com/wk42worldworld/cybercode
40. https://github.com/MemTensor/memmy-agent
41. https://github.com/ksimback/hermes-ecosystem
42. https://github.com/marshallrichards/ClawPhone
43. https://github.com/anysearch-ai/anysearch-skill
44. https://github.com/praveen-ks-2001/hermes-agent-template
45. https://github.com/iamlukethedev/Herald-OS
46. https://github.com/freestylefly/wesight
47. https://github.com/colbymchenry/codegraph
48. https://github.com/hermes-hq/hermes-ide
49. https://github.com/Yuan-lab-LLM/ClawManager
50. https://github.com/kepano/obsidian-skills
51. https://github.com/0xNyk/awesome-hermes-agent
52. https://github.com/MobiusQuant/OpenMobius-skill
53. https://github.com/Giton22/kyllene
54. https://github.com/homarr-labs/dashboard-icons
55. https://github.com/rohitg00/agentmemory
56. https://github.com/chandra447/pi-hermes-memory
57. https://github.com/cogwheel0/conduit
58. https://github.com/ruvnet/ruflo
59. https://github.com/AaronWong1999/hermesclaw
60. https://github.com/stephenschoettler/hermes-lcm
61. https://github.com/joeynyc/hermes-hudui
62. https://github.com/ZiChuanLan/agent-purge

## Required adoption record

No candidate may move from intake to adoption until its record contains:
1. Exact upstream commit SHA and retrieval timestamp.
2. License and provenance assessment.
3. Maintainer activity and release/issue review.
4. Dependency lockfile and vulnerability scan results.
5. Install/build/test evidence from an isolated environment.
6. Threat model covering prompt injection, SSRF, arbitrary file access, command execution, data exfiltration, token handling, and persistence.
7. Explicit capability allowlist and network egress policy.
8. AURELIA integration boundary and proof of zero capital authority.
9. Named human reviewer and rollback procedure.
10. A separate status proving whether the component is merely catalogued, sandbox-tested, approved, installed on a named host, or running with a verified heartbeat.

## Platform-specific boundary

- **AURELIA:** This file is a source-intake record only. It does not change the external federation registry, agent assignments, dependencies, runtime, deployment, or release controls.
- **Claude Code:** Claude can read this file when operating in the AURELIA repository. It does not install software on a separate Claude host or alter Claude account settings.
- **ChatGPT:** This conversation can inspect public source material and supervise reviews. It cannot install arbitrary GitHub code into the ChatGPT product or create a persistent background ChatGPT daemon.

