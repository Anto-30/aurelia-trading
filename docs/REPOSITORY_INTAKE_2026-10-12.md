# External Repository Intake — 2026-10-12

## Purpose
Evaluate the repositories supplied for possible reuse in the canonical AURELIA trading platform and its development tooling. This is a research intake queue, not an approval to install or execute external code.

## Canonical-system invariants
- Canonical repository: `Anto-30/aurelia-trading`; canonical branch: `main`.
- Intake work is isolated on `research/repository-intake-2026-10-12`.
- Do not create a second trading engine or duplicate the capital plane.
- External code remains untrusted until source, license, dependency, secrets, supply-chain and behavior reviews pass.
- No external agent or strategy may obtain capital authority.
- Do not change `config/LIVE_LOCK.yaml`, production secrets, live execution settings, or deployment controls as part of intake.
- Research adoption requires a documented owner, intended interface, test plan, rollback plan and evidence.

## Intake workflow
1. Confirm repository availability, default branch, recent activity, license, release history and archived status.
2. Read README, build instructions, dependency manifests, CI workflows, install scripts and security policy.
3. Classify as adopt / adapt / reference-only / reject. Record rationale and provenance.
4. Run static and dependency checks in an isolated environment; never use production credentials.
5. Build a small proof-of-concept only for a concrete AURELIA requirement.
6. Add tests and architecture notes; submit changes through review. Never merge directly to `main` from intake.
7. Promote only after deterministic assurance and an explicit release review.

## Priority tiers

### P0 — Trading research, broker integrations and quantitative infrastructure
First inspect:
- `jesse-ai/jesse`
- `hummingbot/hummingbot`
- `Drakkar-Software/OctoBot`
- `thrasher-corp/gocryptotrader`
- `ccxt/ccxt`
- `c9s/bbgo`
- `enarjord/passivbot`
- `coding-kitties/investing-algorithm-framework`
- `gazbert/bxbot`
- `asavinov/intelligent-trading-bot`
- `huseinzol05/Stock-Prediction-Models`
- `CryptoSignal/Crypto-Signal`
- `fabston/TradingView-Webhook-Bot`
- `pravo123/derivatives-risk-framework`
- `OnyxPrym/KARANKA-DERIV-V8-BOT`
- `archiebatshameki-source/deriv-ai-predictor`
- `hillarynjuguna26-hue/tradepilot-deriv`
- `gamedub56-create/deriv-trading-bot`
- `pranay123-stack/NSE-derivatives-xts-api-HFT-system`

Policy: treat broker-specific projects as reference material until current API compatibility and authorization are verified. Binary-options, copy-trading, MEV and high-frequency projects receive heightened review; no profitability claims are accepted without reproducible out-of-sample evidence.

### P1 — Agent tooling, development workflow, debugging and observability
Inspect for a specific engineering use case:
- `github/github-mcp-server`
- `benjaminr/chrome-devtools-mcp`
- `openai/openai-realtime-console`
- `cyrus-and/chrome-remote-interface`
- `PySnooper` (`cool-RR/PySnooper`)
- `debug-js/debug`
- `facebook/flipper`
- `facebook/chisel`
- `xdebug/xdebug`
- `probe-rs/probe-rs`
- `HyperDbg/HyperDbg`
- `HuolalaTech/page-spy-web`
- `avwo/whistle`
- `homarr-labs/homarr`
- `AthenZ/athenz`
- `auth0-developer-hub/auth0-b2b-saas-starter`
- `Intina47/context-sync`
- `reugn/dev-tools`
- `DevToys-app/DevToys`
- `me-shaon/devtools`
- `fosslife/devtools-x`
- `elastic/devfiler`

Policy: grant least privilege, keep desktop/remote-control tooling separate from capital execution, and require explicit approval for actions that modify a machine, repository or deployment.

### P2 — Desktop applications and platform tooling
Candidate repositories include GitHub Desktop (`desktop/desktop`), Zen Browser (`zen-browser/desktop`), Nextcloud Desktop (`nextcloud/desktop`), Mattermost Desktop (`mattermost/desktop`), Streamlabs Desktop (`streamlabs/desktop`), Open WebUI Desktop (`open-webui/desktop`), ComfyUI Desktop (`Comfy-Org/desktop`), E2B Desktop (`e2b-dev/desktop`), HTTPie Desktop (`httpie/desktop`), draw.io Desktop (`jgraph/drawio-desktop`), ONLYOFFICE Desktop Editors (`ONLYOFFICE/DesktopEditors`), OpenCloud Desktop (`opencloud-eu/desktop`), Telegram Desktop (`telegramdesktop/tdesktop`), Podman Desktop (`podman-desktop/podman-desktop`), Electron Fiddle (`electron/fiddle`), NW.js (`nwjs/nw.js`), Jellyfin Desktop (`jellyfin/jellyfin-desktop`), React Desktop (`gabrielbull/react-desktop`), Replit Desktop (`replit/desktop`), Flutter Desktop Embedding (`google/flutter-desktop-embedding`), AltSnap (`RamonUnch/AltSnap`) and Dev Manager Desktop (`webosbrew/dev-manager-desktop`).

Policy: do not install all desktop projects. First establish the precise desktop blocker, operating system, architecture and required capability; select one compatible path and validate it in a non-production environment.

### P3 — General libraries, domain-specific systems and low-priority projects
Examples in the supplied list include IbPy, metasfresh documentation, metal3-dev-env, DHIS2 metadata package development, Redis desktop management, WebTorrent Desktop, Appium Desktop, IPFS Desktop, Power BI samples, Android Debug Database, FLEX, VS Code Debug Visualizer, device-detector libraries, Ubuntu development playbooks, Odoo dev containers, JSBin and educational forking labs.

Policy: reference-only unless a direct dependency on a defined AURELIA requirement is demonstrated.

## Exclusion and caution rules
- Do not adopt archived, abandoned, unlicensed, opaque or materially vulnerable code without an explicit risk decision.
- Never import live credentials, tokens, OTPs, account identifiers or production configuration from examples.
- Never treat demo trading, backtests, screenshots, win rates or README claims as evidence of live profitability.
- Do not use a desktop/remote-control project to bypass security controls or access restrictions.
- Do not let an agent rewrite its own permissions, risk rules, or release authorization.
- Preserve idempotency, transaction verification, ledger reconciliation, account isolation, kill-switch behavior and fail-closed UNKNOWN handling.

## Current status
- [x] Canonical AURELIA repository access verified.
- [x] Isolated research branch created.
- [x] Intake policy and priority queue recorded.
- [ ] Enumerate every supplied URL and verify repository metadata.
- [ ] Complete per-repository license, maintenance, dependency and security review.
- [ ] Clone selected candidates into isolated workspaces.
- [ ] Run tests and proof-of-concept evaluations.
- [ ] Submit any justified changes for review; no production or live-trading authorization is implied.

## Acceptance criteria
A repository is not marked integrated until the exact commit/tag, license, files adopted, changes made, tests run, security findings, integration boundary, rollback path and review outcome are recorded. No candidate is accepted solely because it is popular or appears in this intake list.
