# Initial Repository Triage — 2026-10-12

This is a first-pass metadata/README review of selected candidates. It is not a security audit, compatibility certification, or approval to install or execute any project.

| Repository | Initial observation | AURELIA disposition |
|---|---|---|
| https://github.com/jesse-ai/jesse | README describes a crypto strategy research/backtesting/live-trading framework. | Research-only comparison for strategy interfaces and reproducible backtesting; do not transplant its execution authority. |
| https://github.com/hummingbot/hummingbot | README describes an automated trading framework for centralized/decentralized exchanges and references Apache 2.0. | Research-only; review connectors, dependencies, license obligations and execution model before considering any isolated adapter reuse. |
| https://github.com/Drakkar-Software/OctoBot | README describes an open-source crypto trading bot and links CI workflow. | Research-only; compare modularity, tests and risk controls; no direct production integration. |
| https://github.com/ccxt/ccxt | README describes a multi-language cryptocurrency exchange integration library. | Reference-only for exchange API abstraction; not a replacement for the canonical Deriv Options API path or broker verification. |
| https://github.com/hillarynjuguna26-hue/tradepilot-deriv | README describes a mobile-first Deriv bot, a 15-minute pivot strategy and explicitly labels its architecture demo-first / execution demo-only. | Reference-only; do not promote to live execution without independent audit, API verification, tests and full AURELIA capital-plane integration. |
| https://github.com/OnyxPrym/KARANKA-DERIV-V8-BOT | Repository metadata lookup succeeded, but fetching README.md returned HTTP 404 / NOT_FOUND. | Unverified; do not clone or execute until availability, default branch and source contents are confirmed. |

## Checks still required for every candidate
- Exact repository metadata and default branch; archive and maintenance status.
- LICENSE file and whether intended reuse is compatible with AURELIA's distribution.
- Dependency and lock files, CI workflows, release provenance, security policy and known vulnerabilities.
- Secrets handling, network behavior, installation scripts, subprocess execution and permissions.
- Test results in an isolated, credential-free environment.
- A documented integration boundary, rollback plan and reviewer decision.

## Interpretation
A reachable repository is not necessarily safe or maintained. README descriptions are claims by project authors, not independent evidence of reliability or profitability. No strategy in this list is qualified for live trading by this triage.
