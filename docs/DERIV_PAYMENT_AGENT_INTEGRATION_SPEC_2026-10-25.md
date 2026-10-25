# AURELIA — Deriv Payment Agent API Integration Specification

**Status:** Draft for independent review; specification-only change  
**Reference snapshot:** `main` at `d04564aca0648201feff0326fe9af0fbcee92e94` (read 2026-10-25)  
**Safety mode:** `TEST_ONLY` / `VERIFY_ONLY`; real-money payment writes prohibited  
**Canonical live lock:** `config/LIVE_LOCK.yaml` (must remain unchanged)

## 1. Purpose and scope

Specify an isolated adapter contract for Deriv's Payment Agent REST APIs and the evidence, controls, and tests required before implementation. The initial deliverable is an API specification, not a running payment integration. No Deriv API calls, authenticated requests, payment transactions, trading orders, or transfers are performed by this change.

The adapter is a payment-domain service only. It must not be used to authorize trades, change stake sizing, replenish capital automatically, bypass Risk Warden/LivePolicy/Capital Plane Gate/Execution Firewall, unlock `LIVE_EXECUTION`, or mutate the live lock.

### In scope

- Payment-agent directory and statistics.
- Payment-agent/client profile and privacy-setting read/write.
- Deposit transfer preflight and transaction-status reconciliation.
- Client withdrawal verification request, withdrawal submission contract, and status reconciliation.
- Shared auth contract: Bearer token carrying `payment`; PAT additionally requires `Deriv-App-ID`.
- Deterministic schemas, redaction, idempotency, audit evidence, and test plan.

### Documented adjacent domains (not enabled by this adapter)

- Partner analytics `/partners/analytics/v1/overview`, client tag checks `/partners/client-tags/check`, and application markup `/applications/v1/markup-statistics` require `application_read`; use a separately scoped read-only reporting adapter.
- Account nickname `/account/v1/nickname` requires `account_manage` and relies on gateway-provided `X-Brand` / `X-Client-ID`; do not attempt to fabricate these headers.
- Account WebSocket messages (`balance`, `portfolio`, `profit_table`, `statement`, `transaction`), market-data messages (`active_symbols`, `contracts_for`, `contracts_list`, `ticks`, `ticks_history`) and trading messages (`proposal`, `buy`, etc.) are WebSocket protocol surfaces, not paths in this REST OpenAPI contract. They require a separately versioned AsyncAPI/protocol contract. Market data may be research-only; quote/proposal data is non-committing, but `buy`, `sell`, `cancel`, contract updates, and other capital-moving operations are not enabled by this payment integration.
- The modern Options API endpoint and account-specific OTP session rules remain governed by `docs/AURELIA_MODERN_DERIV_PATH_2026-10-03.md` and the existing adapter. Do not mix modern Options APIs with legacy Binary WebSocket v3.

## 2. Canonical safety invariants

The repository's currently observed `config/LIVE_LOCK.yaml` values are:

```yaml
live_trading_enabled: false
FINAL_EXECUTION_AUTHORIZATION: false
LIVE_EXECUTION: BLOCKED
capital_plane_mode: VERIFY_ONLY
research_capital_authority: false
external_repositories_capital_forbidden: true
blind_resubmission: false
kill_switch_independent: true
```

These are reference-state observations, not values to rewrite. The lock must be left untouched by this work.

1. This deliverable does not call any endpoint. Tests use synthetic fixtures and a fake HTTP transport by default.
2. No test may send a real transfer or withdrawal. A live API hostname is not itself a test environment.
3. For any future explicitly configured sandbox/mock transfer preflight, `dry_run` must be pinned to `true` by the adapter; callers must not be allowed to override it in test mode.
4. Real `POST /transfer`, `POST /withdraw`, verification-code dispatch, or client preference mutation must be denied by the default test policy. Verification-code dispatch is not a harmless read: it sends a code to a real contact.
5. If the runtime cannot prove `TEST_ONLY`, the adapter must reject all writes. `UNKNOWN` means `ABORT`; no fallback to real mode.
6. Payment code cannot import or invoke the trading capital-authority interface. A payment event is never an instruction to trade.
7. No auto-top-up, loss-recovery transfer, strategy-triggered withdrawal, agent-initiated client-payment workflow, or LLM-authorized funds movement.
8. Secrets and personally identifying transaction details must not enter application logs, exception strings, prompts, analytics labels, or notifications.

## 3. REST contract

Base URL: `https://api.derivws.com`  
Content type for JSON bodies: `application/json`  
Authentication: `Authorization: Bearer <token>` with OAuth2 `payment` scope. For PAT mode, also send `Deriv-App-ID: <app-id>`. OAuth bearer mode does not require the app-ID header. Never place credentials in URLs.

The accompanying `contracts/deriv-payment-agent.openapi.yaml` models the documented Payment Agent REST paths. Examples are fixtures only; use no real credentials, client nicknames, verification codes, agent IDs, or transaction IDs from examples.

| Method and path | Purpose | Scope | Initial policy |
|---|---|---|---|
| `GET /payment-agents/v1/agent-statistics` | Supported listed-agent countries/currencies | `payment` | Allowed via mock/fixture; live read requires explicit environment configuration |
| `GET /payment-agents/v1/agents` | Paginated agent directory by currency; optional country | `payment` | Same read-only rule |
| `GET /payment-agents/v1/agents/{id}` | Agent profile; `id` may be numeric or `me` | `payment` | Same read-only rule |
| `GET /payment-agents/v1/clients/me` | Client payment settings | `payment` | Same read-only rule |
| `PATCH /payment-agents/v1/clients/me` | Set `show_real_name` | `payment` | **Blocked** in default/test policy; privacy change requires explicit human action |
| `POST /payment-agents/v1/transfer` | Agent-to-client wallet transfer | `payment` | **Mock only**; in any test preflight force `dry_run=true`; real transfer forbidden |
| `GET /payment-agents/v1/transfer/{request_id}` | Transfer status reconciliation | `payment` | Read-only, mock by default |
| `POST /payment-agents/v1/withdraw/verification_code` | Dispatch one-time verification code | `payment` | **Blocked** in test; dispatch has an external side effect |
| `POST /payment-agents/v1/withdraw` | Client wallet-to-agent wallet withdrawal | `payment` | **Blocked**; no real withdrawal in any test |
| `GET /payment-agents/v1/withdraw/{request_id}` | Withdrawal status reconciliation | `payment` | Read-only, mock by default |

### Payment-agent semantics

- Agent discovery starts with statistics, then list by a supported currency, optionally filtered by country, and fetches profile details when needed. Directory pagination must be exhausted before stating a search is complete.
- Agent `currencies[]` entries contain currency-specific commission percentages and possible withdrawal minimum/maximum amounts. Treat absent/null commission or limits as unknown—not zero or unlimited.
- `transfer` is a payment-agent action: authenticated actor must be eligible as an agent. It is not a generic client deposit API. `to_nickname`, amount, and currency must be confirmed before any future human-approved transaction.
- The transfer `request_id` uses `^[\w-]{1,128}$`. Persist an idempotency key before submission. A reused ID must never be regenerated automatically after an ambiguous timeout. A server `RequestIDUsed` response should trigger reconciliation, not a blind retry.
- Transfer response `dry_run_ok` with null `transaction_id` means validation only. It is not proof that funds moved. `pending` must be reconciled using the same `request_id`; only `complete` with an authoritative transaction ID is the API's completion signal.
- A withdrawal requires a six-digit verification code tied to the intended agent, amount, and currency. The code request has `expires_at` and `next_request_at` (Unix epoch seconds). Do not store the code in durable logs or ordinary audit payloads. Withdrawal starts pending and must be reconciled to a terminal status.
- Agent withdrawal settlement to the client occurs outside Deriv. An API status alone does not prove a bank/mobile-money leg has settled.
- Preserve amount and currency as decimal strings in the REST boundary. Do not use binary floats for money; use `Decimal` internally and validate precision/range before serialization.
- The API accepts uppercase currency strings by schema. Do not assume KES or Kenya-based agent support. Query current coverage during a separately approved, read-only live verification; this specification does not claim Kenyan availability.

## 4. Authentication and privilege separation

- Prefer a least-privilege OAuth token with only the scopes needed for the adapter. Payment calls require `payment`; partner reporting requires `application_read`; account nickname requires `account_manage`. Do not combine scopes merely for convenience.
- PAT authentication requires `Deriv-App-ID`. OAuth tokens do not require it. Token mode is explicit configuration, never inferred by retrying alternate auth styles.
- Reject missing token, missing PAT app ID, mismatched configured auth mode, insufficient-scope errors (403), TLS/host mismatch, malformed JSON, schema violation, unexpected HTTP statuses, and timeout as structured errors without echoing secrets.
- Keep token acquisition and storage outside this adapter. Never commit credentials, use repository secrets in untrusted PR jobs, or expose credentials to LLM/agent prompts.
- Because no separate test Payment Agent base URL is documented in the supplied reference, test mode must use mocked HTTP responses. Do not assume the production base URL has a test account/payment sandbox.

## 5. Client architecture

Suggested future module boundaries (do not create production runtime behavior as part of the spec-only change):

- `runtime/adapters/deriv_payment_agent.py`: typed request/response models and transport; no authority over capital.
- `runtime/payment/payment_policy.py`: mode enforcement, allowlist of operations, redaction requirements, human-approval contract.
- `runtime/payment/payment_ledger.py`: durable request-ID ledger and state machine; separate from trading order ledger unless a reviewed shared audit primitive is explicitly justified.
- `contracts/deriv-payment-agent.openapi.yaml`: checked-in upstream REST contract snapshot.
- `tests/payment/`: fixture-based schema, mode, security, and state-machine tests.

Do not duplicate the canonical capital manager, risk engine, execution firewall, or trading request ledger. The payment ledger is for financial reconciliation and must be domain-separated so payment states cannot be mistaken for open contracts or trades.

### Minimum typed internal state

`request_id`, operation, actor/account reference (masked or hashed), recipient/agent reference (masked), amount string, currency, mode, request timestamp UTC, last status, transaction ID if returned, last reconciliation timestamp UTC, error code, source schema version/hash, and explicit human approval record if a future real operation is ever considered. Never persist bearer token or OTP.

### State model

- Read: `REQUESTED -> SUCCEEDED | REJECTED | UNKNOWN`.
- Transfer/withdraw: `PREPARED -> PREFLIGHT_OK -> SUBMITTED -> PENDING -> COMPLETE | REJECTED | FAILED`.
- `DRY_RUN_OK` is a terminal preflight result and must not transition to `COMPLETE`.
- Timeout after write submission: `UNKNOWN`; reconcile using the same request ID before taking any further action.
- Unknown response schema, contradictory state, no matching request ID, or status that does not settle within policy: `UNKNOWN` and manual review. Never blind-resubmit.

## 6. Error contract and retry policy

Deriv errors commonly use an envelope with `data`, `errors[]`, and `metadata`. Each error should be normalized to `DerivPaymentError(status, code, retryable, request_id)` with a sanitized message.

- `400`: input/business-rule failures; do not retry without a changed, validated request. Examples include currency/agent mismatch, limit failure, insufficient funds, OTP validation failure, or request ID reuse.
- `401`: authentication missing/invalid; stop. Never print or re-try arbitrary tokens.
- `403`: missing `payment` scope; stop and request correctly scoped authorization.
- `404`: agent not found for agent-profile lookup, or status request ID not found; do not infer transaction failure from a not-found status lookup immediately after a network ambiguity.
- `500`, `502`, `504`, network timeout: read requests may retry with bounded exponential backoff and jitter. Writes must be reconciled first with the original ID; no blind resubmission.
- Rate-limit errors including `OtpRateLimitExceeded` / `OtpValidationRateLimitExceeded`: honor `next_request_at` when provided; do not repeatedly dispatch codes.
- Never include full server response bodies in logs without allowlisted field extraction and redaction.

## 7. Adjacent Deriv API boundaries from supplied references

These are intentionally not part of the Payment Agent OpenAPI file, to avoid implying one scope or transport covers all Deriv APIs:

| Domain | Documented endpoints/messages | Scope / transport | Contract boundary |
|---|---|---|---|
| Partner analytics | `/partners/analytics/v1/overview`, `/partners/client-tags/check`, `/applications/v1/markup-statistics` | REST, `application_read`; beta caveat for overview and tag check | Separate read-only reporting adapter; date validation, max 730-day analytics interval, max 100 client IDs per tag check |
| Account identity | `GET /account/v1/nickname` | REST, `account_manage` | Gateway resolves `X-Brand` / `X-Client-ID`; do not spoof them or assume this endpoint can establish Deriv trading account identity |
| Account status | `balance`, `portfolio`, `profit_table`, `statement`, `transaction` | Authenticated WebSocket | Read/monitoring; reconcile transactions and history; separate protocol contract |
| Market data | `active_symbols`, `contracts_for`, `contracts_list`, `ticks`, `ticks_history` | WebSocket | Research data only; record source, symbol, epoch and freshness; no assumed order book/depth/real-volume data for synthetic indices |
| Quotes and trading | `proposal`, `buy`, `sell`, `cancel`, `proposal_open_contract`, updates | WebSocket | Proposal may be a quote; buy/sell/cancel/update are trading side effects and remain governed by existing execution firewall and locked live mode |

Partner analytics amounts are documented as USD and its analytics dates are inclusive, with a maximum period of 730 days. Markup statistics dates are UTC. These should be validated in the future reporting adapter rather than mixed into payment transactions.

## 8. Acceptance and test plan

All tests in this phase must be offline/fixture-based. There is no claim that a demo authenticated API test has run.

### Contract tests

1. Parse OpenAPI as OpenAPI 3.1 and validate every `$ref`, path, operation ID, request, response, enum, and pattern.
2. Round-trip valid/invalid fixture requests for decimal amounts, currencies, numeric-or-`me` agent IDs, request-ID pattern, six-digit verification code, dates, pagination, and optional/null profile fields.
3. Validate success and error envelopes; reject missing or malformed `data`, `errors`, required `metadata`, and unexpected terminal statuses.
4. Ensure secrets in fixture authorization headers, OTPs, nicknames and personal data never appear in logs or normalized exception text.

### Mode and no-money tests

5. `TEST_ONLY` denies all write endpoints by default, including client settings PATCH, verification-code POST, withdrawal POST, and live transfer POST.
6. A transfer dry-run fixture forces `dry_run=true` even if a caller passes false; no HTTP request may reach a production transport.
7. Use a fake transport and assert zero network requests in default unit tests; detect accidental use of the production hostname from test configuration.
8. Test missing/expired/under-scoped auth; PAT missing app ID; OAuth mode without app ID; 401/403; host mismatch; malformed JSON; TLS failure; timeout.
9. Test idempotency: persisted ID before dispatch, duplicate ID handling, timeout->`UNKNOWN`, reconcile-before-any-repeat, no ID regeneration, `DRY_RUN_OK` never recorded as completed transfer.
10. Test withdrawal OTP expiry/rate limit and ensure verification-code submission is disabled in test mode.
11. Test status progression: pending->complete, pending->rejected/failed, unknown/malformed status->UNKNOWN/manual review; no unbounded polling.
12. Test that payment code cannot alter live lock, trading authorization flags, stake/risk configuration, or invoke broker buy/sell/cancel functions.

### Evidence required before any later integration rollout

- Commit SHA and UTC timestamp; hashes of this contract and upstream schema snapshot.
- OpenAPI validation report and full test command/output.
- Source-bound statement of which transport was used and proof all tests used fake responses.
- Independent security review of auth scope, secrets, idempotency, write allowlist, privacy and audit data.
- A separate approved plan for any authenticated demo read-only smoke test. No real money is permitted by this phase.

## 9. Implementation exit gates

The specification may be accepted only after independent review of the contract and test plan. Runtime implementation remains a separate change. Before live payment functionality could even be considered, require an explicit user-approved scope, legal/operational eligibility confirmation, strong authorization, review of the exact transfer/withdrawal intent, verified agent and currency/fees/limits, source-bound idempotency and reconciliation, and an independent security review. Trading live-readiness gates are separate; passing payment tests cannot unlock trading.

## 10. Reference sources

- Deriv Payment Agent REST docs as supplied in the task, including each endpoint page and `https://api.derivws.com/data/production-openapi.json`.
- Deriv Partners REST docs as supplied in the task.
- Deriv Account Management, Market Data WebSocket, and Trading Operations docs as supplied in the task.
- Current AURELIA repository: `https://github.com/Anto-30/aurelia-trading`, reference commit `d04564aca0648201feff0326fe9af0fbcee92e94`.
- Canonical existing lock: `https://github.com/Anto-30/aurelia-trading/blob/main/config/LIVE_LOCK.yaml`.

**Status statement:** specification only. No API credential was used. No external Deriv request, verification-code dispatch, payment write, trading order, repository test run, or authenticated soak was performed by this work.
