# AURELIA Identity & Broker Lifecycle Assurance — Verification Report

**Report date:** 2026-11-03  
**Integration branch:** `feat/aurelia-identity-assurance-policy-20261103`  
**Repository base:** PR #256 branch  
**Release state:** `LIVE_EXECUTION=BLOCKED`

## Executive result

**Status: PARTIAL — implementation and unit-test additions are present; CI and real account evidence are not yet established in this report.**

This branch extends the existing `runtime.core.models`, `runtime.adapters.deriv_lifecycle`, `runtime.core.persistent`, `runtime.core.stake_sizing`, and `runtime.adapters.deriv_ws` modules. The assurance orchestrator requires injected existing adapter, verifier, evidence acquirer, lifecycle assessor and policy registry. It has no WebSocket factory, credentials, OTP, connect/reconnect, or order-submission implementation of its own.

A concrete binding-store limitation remains: the repository had no production account identity binding store implementing the needed composite-identity API. `BrokerUUIDToLoginBinding` therefore delegates to a required injected durable store and has no local cache or fallback. Its persistence regression test uses a test-only durable store; it does not prove that a production AURELIA binding store is already wired.

The PR #256 account-plane restriction remains in force. The authenticated verifier and real broker lifecycle cannot be run until a genuinely read-only permission is independently available and the repository has a compatible production provider. No mocked account data is reported as broker evidence.

## Component status

| Component | Status | Evidence/limitation |
|---|---|---|
| Composite identity dataclasses | Implemented; unit tests added | Independent validation, checksum tamper detection, distinct identity namespaces, no email/email-hash fields |
| Canonical transport integration | Implemented; tests added | Orchestrator accepts an injected existing adapter and asserts the same transport object remains attached; no transport is constructed by the orchestrator |
| Binding-store adapter | Partial integration seam | Delegates to injected durable store; no compatible production store was found in the repository |
| Extended evidence acquisition | Interface orchestration only | Requires injected evidence provider; no authenticated account evidence obtained; required fields and PII exclusions are validated |
| Lifecycle assurance | Partial | Orchestrator requires eight explicit PASS phase results; test doubles exercise the contract; genuine authenticated broker lifecycle is not run |
| Transport lifecycle | Code fix and mocked-socket tests added | Serializes connect; closes captured socket on shutdown; reconnect tests use a mocked WebSocket, not Deriv |
| Stake provenance registry | Implemented; unit tests added | Incomplete provenance rejected; multiple validated policies per plane rejected; candidate report includes $0.35, $1.00, $1.50 as pending |
| PR #191 / #256 resolution | Documented | Keep PR #256's workflow and credential isolation; integrate PR #191 Layer 6/risk-metrics code only; defer account verifier |

## Source and change references

- Composite identity model: `runtime/core/models.py`
- Existing broker lifecycle module extended: `runtime/adapters/deriv_lifecycle.py`
- Existing persistence module extended with injected-store adapter: `runtime/core/persistent.py`
- Existing stake sizing module extended: `runtime/core/stake_sizing.py`
- Existing canonical Deriv WebSocket transport repaired: `runtime/adapters/deriv_ws.py`
- Identity tests: `tests/test_composite_account_identity.py`
- Binding tests: `tests/test_composite_account_binding.py`
- Lifecycle orchestration tests: `tests/test_broker_lifecycle_assurance.py`
- Transport lifecycle tests: `tests/test_deriv_transport_lifecycle.py`
- Stake provenance tests: `tests/test_stake_policy_provenance.py`
- Policy report: `docs/assurance/stake-policy-reconciliation-2026-11-03.md`
- PR integration report: `docs/assurance/PR-191-PR-256-integration-resolution-2026-11-03.md`

## Lifecycle test semantics

A successful WebSocket connect test is not a complete broker lifecycle test. This branch tests the current transport's connect/request correlation/reconnect/close behaviour with a mocked socket and verifies heartbeat parameters are configured. It does not claim a Deriv heartbeat, authenticated account lifecycle, fresh real OTP, portfolio/statement read, state recovery against a real broker, or production reconciliation.

The integrated assurance orchestrator requires explicit PASS results for authentication, connection, heartbeat, controlled disconnect, fresh-OTP reconnect, state recovery, reconciliation and clean shutdown. Any `not_run`, missing, or non-PASS phase prevents a COMPLETED report.

## CI and coverage

**CI run ID:** pending  
**CI head commit:** pending  
**Tests passed/failed/skipped:** pending  
**Lifecycle coverage:** pending

These fields will be populated only from the GitHub Actions run for this exact integration head. Unit-test fakes are not production account evidence.

## Outstanding blockers

1. No production binding store implementing the injected `ExistingAccountBindingStore` contract is present in the current repository.
2. No read-only Deriv account permission has been established for required account APIs; PR #256 keeps authenticated account evidence blocked.
3. The identity verifier and full evidence provider require actual production implementations with source provenance, not mocks.
4. The eight-phase genuine broker lifecycle, including fresh OTP reconnect and actual reconciliation, has not been run.
5. The 3,600-second non-production soak and independent review remain separate release requirements.
6. Stake policy provenance for $0.35 and $1.50 is absent; the $1.00 baseline lacks a separately recorded formal approval authority/signature in the inspected docs/history.

## Release recommendation

Do not merge this integration until CI has passed on the exact head and an independent reviewer has inspected the changed modules. Do not enable authenticated account verification or live execution through this branch.

`LIVE_EXECUTION=BLOCKED`  
`FINAL_EXECUTION_AUTHORIZATION=false`  
`capital_plane_mode=VERIFY_ONLY`
