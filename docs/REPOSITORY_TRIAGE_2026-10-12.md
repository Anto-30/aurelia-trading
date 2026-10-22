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


## Additional P0 metadata screening — 2026-10-12

The following public GitHub metadata was checked on 2026-10-12. This is metadata-only screening: README, dependency manifests, code, install scripts and security behavior were not comprehensively audited, and none of these projects was cloned or executed.

| Repository | GitHub metadata observed | Preliminary disposition |
|---|---|---|
| https://github.com/thrasher-corp/gocryptotrader | MIT; active; Go multi-exchange crypto framework; pushed 2026-10-12 | Reference-only for connector patterns and operations; venue scope does not establish Deriv Options compatibility. |
| https://github.com/c9s/bbgo | AGPL-3.0; active; Go crypto trading framework; pushed 2026-10-12 | Reference-only; legal review required before any incorporation into a proprietary hosted product. |
| https://github.com/enarjord/passivbot | Unlicense; active; targets named crypto venues; pushed 2026-10-12 | Research-only for portfolio/risk ideas; venue-specific execution is not reusable as a Deriv adapter without redesign and tests. |
| https://github.com/coding-kitties/investing-algorithm-framework | Apache-2.0; active; research/backtest/deployment framework; pushed 2026-09-30 | Research-only; inspect implementation and test methodology before borrowing any patterns. |
| https://github.com/gazbert/bxbot | MIT; last push observed 2024-11-30; Bitcoin bot | Low priority/reference-only due to older activity and narrow venue scope. |
| https://github.com/asavinov/intelligent-trading-bot | MIT; last push observed 2026-08-30; ML/feature-engineering trading signals | Research-only; require reproducible prospective OOS, calibration and cost-aware evaluation. |
| https://github.com/huseinzol05/Stock-Prediction-Models | Apache-2.0; archived; last push observed 2023-04-16 | Reject as an active dependency; educational reference only. |
| https://github.com/CryptoSignal/Crypto-Signal | MIT; last push observed 2024-07-07; technical-analysis notifications | Low priority/reference-only; old activity and alerting scope do not qualify a trading strategy. |
| https://github.com/fabston/TradingView-Webhook-Bot | MIT; active; routes TradingView alerts to messaging/social services; pushed 2026-10-01 | Reference-only for notifications; not a broker execution or qualification component. |
| https://github.com/pravo123/derivatives-risk-framework | Apache-2.0; last push observed 2026-05-27; describes paper broker, Tastytrade adapter, risk gates and audit ledger | Highest relevance for comparative risk-control ideas, but reference-only until code/tests are audited; no direct compatibility claim. |
| https://github.com/gamedub56-create/deriv-trading-bot | No SPDX license declared by GitHub API; last push observed 2026-08-26 | Reject as an adoption candidate until license, provenance and source behavior are verified. |
| https://github.com/archiebatshameki-source/deriv-ai-predictor | Apache-2.0; last push observed 2026-10-02; README describes client-side Deriv WebSocket trading | Reference-only; small public footprint and README claims are not proof of safety, API correctness or profitability. |

No item above is approved for installation, merged into AURELIA, or granted capital authority. Next step for any candidate is immutable-commit selection, license-file verification, dependency and workflow inspection, credential-free sandbox tests, and a documented security review.
