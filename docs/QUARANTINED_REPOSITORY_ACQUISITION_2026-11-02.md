# Quarantined Repository Acquisition — 2026-11-02

## Disposition

This document records a preliminary, source-browsed acquisition assessment. It does not certify local cloning, SBOM completeness, vulnerability status, isolated tests, or AURELIA integration. All candidates remain quarantined under `config/external_repo_federation.json`.

Global boundary remains unchanged: `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`, `research_capital_authority=false`, and external repositories have no capital authority.

## Repository identity and pinned source heads

| Repository | Observed default-branch HEAD | Pin date | Mode | Initial decision |
|---|---|---|---|---|
| NousResearch/hermes-agent | `fbf6c6c91d8a9ce3008e05c4b51ca60ad05bb85f` | 2026-11-02 | SANDBOX_ONLY | NO-GO for direct AURELIA runtime; sandbox reference only |
| tradermonty/hermes-trading-research-agent-work-package | `9598a9cc21e465438b194e43f35b52d4adf7fe3d` | 2026-11-02 | RESEARCH_ONLY | GO for isolated research/reporting evaluation |
| tradermonty/claude-trading-skills | `121dce2da6760a36a160c73493370fbc26a02ccd` | 2026-11-02 | RESEARCH_ONLY | GO for selected calculation/schema evaluation |
| agiprolabs/claude-trading-skills | `981e1d736cdc02bdc1c55c74ec9224e956414706` | 2026-11-02 | REFERENCE_ONLY | NO-GO for DEX/wallet execution; research snippets only after separate audit |
| Jakeschincariol/day-trader-skill | `3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd` | 2026-11-02 | REFERENCE_ONLY | NO-GO for broker integration; approval-state-machine reference only |

The originally suggested `tradermonty/hermes` returned GitHub 404. `Julian-dev28/hermes-trader` was not found by the exact owner/repository search. The TradeMonty Hermes profile repository above is not the Hermes Agent runtime; the actual runtime source browsed separately is `NousResearch/hermes-agent`.

## License

The root license files inspected for all five repositories identify MIT. This supports commercial compatibility subject to preserving notices and auditing third-party and vendored components. It is not a dependency-license completeness result. No GPL root license was found; transitive and embedded license obligations remain pending.

## Dependency and SBOM status

- **NousResearch Hermes Agent:** `pyproject.toml` declares Python `>=3.11,<3.15` and exact-pinned direct dependencies for most core packages, with some conditional ranges and an Android VCS pin. A `uv.lock` file exists, but its content was not retrievable through the current file connector. Complete lock and transitive dependency inspection is pending.
- **TradeMonty Hermes profile:** `pyproject.toml` declares PyYAML, with pytest and jsonschema as development extras. The README additionally documents jsonschema and PyYAML installation. No complete lockfile audit performed.
- **TradeMonty Claude skills:** `pyproject.toml` declares jsonschema, packaging, PyYAML, requests, SciPy and yfinance with version ranges; optional/development extras include pytest, Bandit, detect-secrets and pip-audit. No lockfile audit performed.
- **AgiPro skills:** dependencies are documented per skill rather than through a complete root manifest. Inspected execution examples use httpx and solders plus Jupiter/Solana RPC.
- **Day Trader:** README describes core scripts as standard-library Python; broker interaction is via an external Alpaca MCP connector, not direct broker calls from the local ticket script.

CVE status: UNKNOWN - Requires Local Audit. The independent screening service returned no detailed CVE inventory for these repository identifiers; this is not evidence of zero vulnerabilities.

## Security and execution findings

- Hermes Agent is a general agent runtime with terminal backends, tool execution, subagents, messaging, scheduled automation and skill persistence/self-improvement features. It is too privileged for direct use in the AURELIA capital plane. Evaluate only in an isolated, no-secrets sandbox.
- The Hermes trading profile states that it is a research, journaling and risk-review assistant, not an automated trading system. Its profile example uses environment-variable placeholders and an Alpaca paper default. Its README also documents a `curl | bash` installer; do not use that installer in production acquisition.
- TradeMonty Claude skills provide research calculations and schemas, but no native Deriv adapter or Layer 6 integration was established.
- AgiPro's DEX skill documents wallet private-key loading, transaction signing and Solana RPC submission. Its WebSocket examples use WSS endpoints, but the presence of WSS examples does not prove comprehensive payload validation or safe key custody. Do not execute or vendor these pathways.
- Day Trader's broker workflow uses order fingerprints, a risk PASS for the exact order and two human approval gates before an external broker connector. It is US-equity/Alpaca-specific; it does not satisfy Deriv identity, Risk Warden or execution-firewall contracts. Its market-data tools explicitly warn that Yahoo Finance data is unofficial and can lag.

No repository was executed. No live credentials, broker tokens, wallet keys or production secrets were supplied or accessed.

## AURELIA CI and provider findings linked to this review

- PR #247 improves fail-closed behavior when no worker command is configured. Its configured-worker test uses a sleeping Python process; that proves process liveness, not provider authentication. AURELIA's provider-authentication gate remains incomplete.
- PR #248's inspected head `7b9e0bd9ae6ee66f8e474cd803d4e8e06fac09fd` fails the Assurance compile step. Retrieved files end in incomplete declarations/assertions/expressions and the status document is truncated. The CI log separately reports UTF-8 decoding errors. Do not blanket-replace invalid bytes; repair from an attributable source and rerun exact-head CI. Silver Bullet tuning, P1 and P2 remain blocked.
- The current `main` branch does not contain `config/risk_policy.yaml`. The current documented/runtime probability floor remains 0.50–0.75. The proposed 0.55 floor is not active until the canonical policy is reviewed and implemented consistently across runtime, production standard, README, audits and tests.

## Test execution status

No isolated test suite was run in this session. The local container could not resolve GitHub for `git clone`; no Desktop Commander device is connected; and the available Hugging Face job service rejected a minimal Python job request with HTTP 402 Payment Required. Therefore:

- Clone status: NOT COMPLETE.
- Offline tests: NOT RUN.
- CVE/dependency scan: NOT RUN.
- Full secret scan: NOT RUN.
- Full source-tree and network-flow audit: NOT COMPLETE.

Repository-prescribed commands for a future isolated checkout:

```bash
# Hermes trading research profile
make validate
make test
# validate-all additionally requires CLAUDE_TRADING_SKILLS_REPO
make validate-all

# Day Trader
python3 -m unittest discover -s tests -v

# TradeMonty Claude skills
python -m pytest -q
```

For Hermes core and AgiPro, use their exact pinned source checkout and repo-provided test configuration after reading all test and packaging instructions. Do not assume a default pytest invocation is sufficient.

## Promotion criteria

No source is promoted to execution or capital-plane dependencies. Reconsider only after: authenticated and isolated clone; full dependency/license SBOM; offline secret scanning; SAST and CVE scanning against a current advisory database; network-egress and subprocess review; complete offline tests; reproducible build hashes; independent code review; and adapter-level compatibility tests against AURELIA contracts. Any accepted component remains advisory or research-only unless an independent AURELIA release process authorizes otherwise.

## External environment limitations

This PR updates source pins and records evidence only. It does not claim a physical clone or runtime install. AURELIA's agent capability boundary records Dev as NOT_CONNECTED; the current ChatGPT session has GitHub source browsing/writing but no connected desktop shell, Claude Code runtime, DeepSeek harness, or Hermes process. The user can connect an authorized host later to complete offline execution.

