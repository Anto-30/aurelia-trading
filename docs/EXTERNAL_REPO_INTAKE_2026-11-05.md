# External Repository Intake — Deriv/AURELIA Review

**Date:** 2026-11-05  
**Canonical project:** `Anto-30/aurelia-trading`  
**Intake branch:** `research/deriv-repository-intake-2026-11-05`  
**Registry:** `config/external_repo_federation.json`

## Executive decision

Only two of the six supplied repositories are admitted into AURELIA's pinned external-source registry, and neither is executable in the capital or production path:

- `deriv-com/deriv-api` — `REFERENCE_ONLY`: official legacy SDK reference for protocol comparison.
- `deriv-bots/digitlens-pro` — `RESEARCH_ONLY`: tick-digit statistical research reference.

Four repositories are not admitted: the HD wallet tool is unrelated to Deriv authentication and handles private-key material; the OAuth reflector uses an unsafe legacy token-reflection pattern; the two Rust derive libraries have no identified use in this Python runtime.

No external code was copied into AURELIA, installed, executed, or added to the production dependency set.

## Repository decisions

| Repository | Pinned head | Decision | Rationale |
|---|---|---|---|
| [deriv-com/deriv-api](https://github.com/deriv-com/deriv-api) | `fbf51f6ed7698e6c6164fb0eda4183bb27253546` | `REFERENCE_ONLY` | Official SDK, but README examples connect to `ws.derivws.com/websockets/v3`, the legacy WebSocket API. AURELIA's canonical integration uses the modern Options REST + OTP + `api.derivws.com` WebSocket contract. |
| [deriv-bots/digitlens-pro](https://github.com/deriv-bots/digitlens-pro) | `68866a42bd7bd1a3e4ce4d170c7438d34a1c6402` | `RESEARCH_ONLY` | Public-tick analysis UI with rolling digit-frequency statistics and heuristic score display. No validated probability calibration, expectancy, cost model, risk sizing or broker execution lifecycle was evidenced. |
| [dan-da/hd-wallet-derive](https://github.com/dan-da/hd-wallet-derive) | `43e6c23bdbfa23a4df207bb13a1cd3fdb961f5a5` | Rejected — out of scope | BIP32/BIP39 cryptocurrency-wallet derivation. It produces private keys, extended private/public keys and addresses. It is not a Deriv API token or OAuth utility. Do not provide AURELIA broker secrets, mnemonics or keys to it. |
| [digiemployeeautomation/deriv-oauth-reflector](https://github.com/digiemployeeautomation/deriv-oauth-reflector) | `060b59b8a07f7963df1f29b7bee2bebfb961f5a5` | Rejected — unsafe auth pattern | Its initial commit reflects `token1` and all query parameters into HTML using `innerHTML`, without state validation, escaping, or PKCE authorization-code exchange. This risks token disclosure and reflected DOM injection. Do not deploy or use for AURELIA authentication. |
| [colin-kiegel/rust-derive-builder](https://github.com/colin-kiegel/rust-derive-builder) | `079fd81949c31ad1de88772dae75a80be1e50b2e` | Rejected — out of scope | Rust procedural macro for generating builder-pattern boilerplate. No Rust component or direct AURELIA need identified. |
| [JelteF/derive_more](https://github.com/JelteF/derive_more) | `e13226493dbdb510dae2b3548c975f01624f11d5` | Rejected — out of scope | Rust procedural macros for common trait implementations. No Rust component or direct AURELIA need identified. |

## Findings relevant to AURELIA

### 1. Deriv API SDK is not the current execution adapter

The SDK README and API reference use the legacy `ws.derivws.com/websockets/v3` interface and demonstrate the older `app_id` connection pattern. Its `authorize` method accepts the older WebSocket token-auth shape.

AURELIA's canonical flow is instead:

`https://api.derivws.com` REST account inventory  
→ exact account binding  
→ fresh one-time OTP  
→ authenticated `wss://api.derivws.com/trading/v1/options/ws/{real|demo}`  
→ account/currency/environment checks  
→ fresh balance and capital snapshot.

The SDK must not become a production fallback or create a second broker adapter.

Current official documentation:
- [Options REST API overview](https://developers.deriv.com/docs/options/)
- [OAuth 2.0 Authorization Code + PKCE](https://developers.deriv.com/docs/intro/oauth/)
- [API overview: REST and WebSocket](https://developers.deriv.me/docs/intro/api-overview/)

### 2. DigitLens is a hypothesis generator, not a strategy-performance proof

The inspected `index.html` uses public market-data streams and calculates:
- digit counts and rolling distributions;
- even/odd and over/under shares;
- rise/fall and match/differ frequencies;
- simple rankings and threshold-based scanner signals.

Its displayed score is a heuristic deviation from selected fair-value baselines. A score labelled "confidence" is not a calibrated posterior probability or verified win probability. A rolling frequency imbalance alone does not establish a predictive edge in the next contract.

Permitted follow-up use is limited to an independently implemented research adapter or offline feature comparison. Any candidate must be tested with timestamped, no-lookahead data, walk-forward/OOS partitions, spread/payout/fees, realistic latency, and expectancy/PF/drawdown. No signal from DigitLens is an order instruction.

### 3. OAuth reflector must not enter authentication

The initial reflector commit reads query parameters and writes them directly into HTML templates. It displays the raw `token1` value and every received parameter. The implementation does not verify OAuth `state` and does not perform Authorization Code + PKCE exchange.

The current Deriv OAuth documentation specifies:
1. Generate a cryptographically random PKCE verifier/challenge and per-request `state`.
2. Redirect to Deriv's authorization endpoint.
3. Verify the returned `state`.
4. Exchange the authorization code and original verifier at the token endpoint.
5. Store and use the returned bearer token securely; read `expires_in`, and do not assume a refresh token exists.

AURELIA must keep tokens, OTPs, authenticated WebSocket URLs and other secrets out of logs, browser-readable query strings, third-party agent gateways, source control and untrusted pages. No OAuth implementation was changed in this intake.

## Registry controls

The two admitted entries are pinned to the exact commit IDs above and have:

- `capital_authority=false`
- `production_deployment_authority=false`
- `live_order_authority=false`
- `secret_reading=false`
- `secret_logging=false`
- `broker_transaction_write=false`
- `physical_runtime_install=NOT_CLAIMED`

Modes remain `REFERENCE_ONLY` and `RESEARCH_ONLY`. External code execution remains `DENY_BY_DEFAULT`. The other four sources are recorded as rejected/deferred in the registry intake decision metadata; they were not added as executable sources.

## Verification status

This was a source-level intake review using repository metadata, default-branch commit IDs, README/package/source inspection, AURELIA's current adapter/policy files, and current official Deriv documentation. It was not a runtime clone, dependency scan, independent security audit, or market backtest. Those checks remain `NOT_RUN`.

The AURELIA capital state is unchanged:
`LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`.

