# AURELIA Identity & Broker Lifecycle Assurance — Verification Report

**Report date:** 2026-11-04  
**Integration branch:** `feat/aurelia-identity-assurance-policy-20261103`  
**Repository base:** PR #256 branch (`security/split-deriv-research-account-planes-20261102`)  
**Release state:** `LIVE_EXECUTION=BLOCKED`

## Executive result

**Status: PARTIAL — identity assurance integration and encrypted file-store implementation are present; authenticated Deriv account evidence and production persistence deployment remain blocked.**

The integration extends the existing identity, broker lifecycle, persistence adapter, stake-policy, and canonical Deriv transport modules. The assurance orchestrator continues to require injected existing components and does not create a second broker transport or capital authority.

A concrete encrypted account-binding implementation now exists at `runtime/core/account_binding_store.py`. It implements the existing `ExistingAccountBindingStore` contract using Fernet authenticated encryption, strict identity revalidation, cross-process POSIX file locking, atomic file replacement, fsync, and restrictive local file/directory permissions. The key is supplied by the caller; this module does not generate, store, log, or retrieve it. Regression tests cover restart reconstruction, ciphertext secrecy, wrong-key rejection, tamper rejection, uniqueness of Deriv login IDs, invalid keys, and missing-store behavior.

**Important deployment boundary:** this file store is a single-host backend for a durable private POSIX volume. It is not a distributed database, is not wired into the production runtime configuration, and no production key-management or mounted-volume configuration has been applied. The readiness report therefore must continue to report the persistent worker/store as not deployed until those separate configuration and operational requirements are satisfied.

The PR #256 account-plane restriction remains in force. No documented genuinely read-only Deriv account permission is currently available to this workflow. No real account login, balance, portfolio, statement, or broker lifecycle evidence was acquired. Unit tests, public market-data checks, and test doubles are not broker account evidence.

## Component status

| Component | Status | Evidence/limitation |
|---|---|---|
| Composite identity dataclasses | Implemented; unit tests added | Independent validation, checksum tamper detection, distinct identity namespaces; no email/email-hash fields |
| Canonical transport integration | Implemented; tests added | Assurance uses injected existing adapter/transport; no second transport created |
| Binding-store adapter | Implemented integration seam | Adapter requires injected `ExistingAccountBindingStore`; no in-memory fallback |
| Encrypted account-binding file store | Implemented; tests added | Fernet authenticated encryption, caller-injected key, private permissions, local process lock, atomic replace, strict tamper/wrong-key failure; not production-wired |
| Evidence acquisition | Interface orchestration only | Requires injected evidence provider; no authenticated account evidence obtained |
| Lifecycle assurance | Partial | Eight explicit PASS phases are required; test doubles exercise the contract; genuine authenticated broker lifecycle not run |
| Transport lifecycle | Code fix and mocked-socket tests added | Connection creation/close regression tests use mocked sockets, not Deriv |
| Stake provenance registry | Implemented; unit tests added | Incomplete provenance rejected; candidates remain pending |
| PR #191 / #256 resolution | Documented | Preserve PR #256 credential isolation; import execution-neutral Layer 6 contracts only |

## Persistence design and limitations

- Store implementation: `runtime/core/account_binding_store.py`
- Adapter contract: `ExistingAccountBindingStore` in `runtime/core/persistent.py`
- Cryptographic dependency: `cryptography>=42.0` in project and requirements manifests
- Ciphertext authentication/encryption: Fernet; no default key or fallback
- Key handling: injected at construction; must be sourced from a separate secrets manager/KMS at deployment time
- Local durability: same-directory temporary file, fsync, atomic replace, private 0600 file and 0700 parent directory, POSIX flock
- Identity invariants: serialized identity is reconstructed and checksum/component validated on every read; a Deriv login ID cannot bind to multiple AURELIA UUIDs
- Failure behavior: wrong key, modified ciphertext, malformed schema, weak permissions, or identity mismatch fails closed

This implementation does not prove a production volume survives host loss, a key rotation/recovery process, backup restoration, or multi-replica operation. Those require a deployment-specific KMS/secret-manager and durable storage design plus operational recovery testing.

## Lifecycle test semantics

A successful WebSocket connect test is not a complete broker lifecycle test. This branch tests the current transport's connect/request correlation/reconnect/close behaviour with mocked sockets and verifies heartbeat parameters are configured. It does not claim a Deriv heartbeat, authenticated account lifecycle, fresh real OTP, portfolio/statement read, state recovery against a real broker, or production reconciliation.

The integrated assurance orchestrator requires explicit PASS results for authentication, connection, heartbeat, controlled disconnect, fresh-OTP reconnect, state recovery, reconciliation and clean shutdown. Any `not_run`, missing, or non-PASS phase prevents a COMPLETED report.

## Exact-head CI

Latest code commit verified before this report-only update: `dff978c31ab909dc60b17c902f8c1fdac1faccfa`.

- Workflow: AURELIA Assurance, run [#41810648663](https://github.com/Anto-30/aurelia-trading/actions/runs/41810648663)
- Result: **success**, all 26 workflow steps succeeded
- Test batches: research 80; authentication gates 12; auth prerequisites 6; assurance 61; runtime 402; hardening 12 (573 unittest tests total), plus the secret-presence pytest check
- Container build: passed
- Public Deriv market-data transport evidence: passed
- Account-plane prerequisite check: passed with account evidence explicitly BLOCKED
- Readiness check: expected blocked
- Release gate: `LIVE_RELEASE_GATE=BLOCKED` because `config/LIVE_LOCK.yaml` disables live trading
- Artifacts: Layer 6 matrix, public transport evidence, and Deriv authentication prerequisites; see PR checks and evidence manifest for SHA-256 artifact digests

A documentation-only follow-up changes the branch head after this verified run; the new exact-head workflow result must also pass before the reviewer signs off.

## Outstanding blockers

1. The encrypted file store is not wired into the deployed runtime and has no production KMS/secret-manager or durable-volume configuration.
2. No documented, genuinely read-only Deriv account permission has been established; account evidence remains BLOCKED.
3. The identity verifier and full evidence provider require actual production implementations with source provenance, not mocks.
4. The eight-phase genuine broker lifecycle, including fresh OTP reconnect and actual reconciliation, has not been run.
5. The 3,600-second non-production soak and independent review remain separate release requirements.
6. Prospective out-of-sample, calibration, execution economics, security audit, deployment and strategy-eligibility artifacts are missing.
7. PR #259 remains Draft and stacked on PR #256; PR #256 must be merged and PR #259 retargeted before mainline integration review.

## Release recommendation

Keep PR #259 Draft and unmerged. Do not enable authenticated account verification or live execution through this branch. The GitHub commit-signature issue must be resolved with a valid key registered to the account; do not disable Vercel's verified-commit enforcement.

`LIVE_EXECUTION=BLOCKED`  
`FINAL_EXECUTION_AUTHORIZATION=false`  
`capital_plane_mode=VERIFY_ONLY`
