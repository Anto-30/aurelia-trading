# External Repository Intake — Browser and Agent Batch (2026-10-15)

## Scope and disposition

This intake adds six new external sources to `config/external_repo_federation.json` and refreshes the pin for the already-registered Chrome DevTools MCP repository. The registry now contains 304 unique repository entries. These are provenance and research/tooling records, not installed runtime dependencies.

| Repository | Pinned commit | Disposition | Initial assessment |
|---|---|---|---|
| https://github.com/anthropics/claude-plugins-official | `8f814f49002ff824e8a9ba43cf96112dc7f5948d` | `SANDBOX_ONLY` | Review each plugin's commands, hooks, permissions, dependencies, and license notices before enabling. |
| https://github.com/xFFFFF/Gekko-Strategies | `f53854f8555a7c962f4013c53c464cfb377f83f6` | `RESEARCH_ONLY` | Upstream head is dated 2018-05-24. Historical strategy hypotheses only; no strategy is assumed profitable or compatible with Deriv instruments. |
| https://github.com/ChromeDevTools/chrome-devtools-mcp | `c87d190b2e26de0514a31b5af399ecd66337a44e` | `TOOLCHAIN_ONLY` | Existing registry entry; pin refreshed. Browser debugging candidate, not a trading runtime component. |
| https://github.com/browserbase/mcp-server-browserbase | `3e6f53461949037d5e65dd425da3ceb1263f11d6` | `REFERENCE_ONLY` | Upstream is archived and marked unmaintained as of 2026-07-20. Do not use as a new production dependency. |
| https://github.com/QwenLM/Qwen-Agent | `31a4d36d123688581a9e9744427272b33ce940e0` | `SANDBOX_ONLY` | Agent orchestration/tool-calling reference. Review execution isolation, prompt/tool boundaries, dependencies, licensing, and egress before any synthetic-data POC. |
| https://github.com/zhizhuodemao/js-reverse-mcp | `bf7dc506e8743ba1ec5bd3325c91818b9192e40e` | `SANDBOX_ONLY` | Browser/runtime analysis can expose page data and local files. Require dedicated allowed roots, restricted egress, and no sensitive browser profile. |
| https://github.com/vibheksoni/stealth-browser-mcp | `ba95cca933c8e90bfeaa515c1d05dad2927794e6` | `SANDBOX_ONLY` | Powerful CDP, page script, cookie/storage, request interception, header mutation, and file-upload features. Keep disabled pending threat-model and sandbox validation. |

## Security and integration controls

- All records are pinned to immutable commit SHAs observed through the GitHub API on 2026-10-15.
- No upstream source was cloned into the AURELIA execution path, installed, or executed by this intake.
- No repository receives capital authority, live-order submission, live-lock mutation, production-secret reading/logging, broker-transaction write access, or production-deployment authority.
- Do not pass Deriv tokens, account identifiers, cookies, browser profiles, private files, or production configuration to these tools or their agents.
- Browser automation and reverse-engineering tools must run in a disposable isolated environment with restricted filesystem roots and network egress. Do not connect them to an authenticated Deriv session.
- Gekko strategy code is research-only. Any adaptation requires instrument-specific semantics, no-lookahead and prefix-stability tests, spread/slippage/payout/fee modeling, walk-forward and out-of-sample evaluation, calibration, and prospective evidence. CI success alone is not strategy qualification.
- License and transitive dependency/CVE review remains pending for this intake. Repository presence, README review, and a pinned SHA are not a full source audit, SBOM, or legal clearance.

## Validation and promotion gates

1. Validate registry JSON, uniqueness, and immutable commit pins.
2. Run the existing AURELIA assurance, external-repository federation, and continuity checks on the exact pull-request head.
3. Review dependency manifests, install hooks, tool permissions, local-file access, network egress, telemetry, and licenses before any sandbox POC.
4. Require independent human review before merge.
5. Keep `config/LIVE_LOCK.yaml` unchanged and `LIVE_EXECUTION=BLOCKED`; no live-trading gate is satisfied by this intake.

## Separate production-control blocker

The repository's `Execution` ruleset was observed via GitHub API on 2026-10-15 with `enforcement=disabled`. This intake does not change repository rulesets, environment protection, secrets, or production workflows. Environment correction should be independently verified in GitHub Settings, and the ruleset must be enabled with required checks and appropriately restricted bypasses by an authorized administrator before production credentials or deployments are approved.
