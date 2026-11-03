# PR #191 / PR #256 Integration Resolution

**Assessment date:** 2026-11-03  
**Repository base:** `Anto-30/aurelia-trading`  
**Integration branch:** `feat/aurelia-identity-assurance-policy-20261103`  
**State:** implementation branch; pending CI and independent review

## Finding

The two pull requests do not define competing stake-sizing policies in their changed-file sets.

- **PR #191** (`feat/layer6-fail-closed-risk-gate`) adds the disabled-by-default Layer 6 risk veto, source-bound risk contracts, execution-boundary regression tests, and cost-adjusted research metrics. Its changed-file list also includes a change to `.github/workflows/aurelia-assurance.yml` and an authenticated read-only state-verification script.
- **PR #256** (`security/split-deriv-research-account-planes-20261102`) separates public research from the account plane, blocks authenticated account verification while a documented read-only broker scope is unavailable, removes account-credential mappings from general assurance, and modifies the same workflow.
- The only identical path in the two PR changed-file lists is `.github/workflows/aurelia-assurance.yml`. Neither PR changes `runtime/core/stake_sizing.py` or the checked-in stake-policy documents.

The proposed $0.35 / $1.00 / $1.50 conflict therefore cannot be attributed to PR #191 versus PR #256 based on their current diffs.

## Workflow conflict and resolution

The PR #191 workflow retains a production-scoped environment and credential-backed account-verification steps. PR #256 deliberately removes that path from general Assurance, sets `DERIV_AUTH_CONFIGURED=false`, and reports account evidence as blocked until a verifiable read-only account permission is available.

**Resolution chosen on this integration branch: preserve PR #256's credential isolation and account-plane block.** The branch does not restore production environment secrets, PAT/generic-token fallback, authenticated account calls, or a broker account verifier job.

The branch imports PR #191's execution-neutral Layer 6 gate, boundary contracts, trade metrics, and their unit tests. It does not import or schedule PR #191's authenticated `verify_deriv_read_only_state.py` workflow step. That would conflict with PR #256's explicit account permission restriction and cannot produce valid account evidence today.

The Layer 6 code remains a risk veto only. It is not wired into the production signal loop and cannot grant capital authority. The existing `CapitalPlaneExecutor` remains the sole capital-moving gateway.

## Integration evidence

- PR #191: [GitHub pull request](https://github.com/Anto-30/aurelia-trading/pull/191)
- PR #256: [GitHub pull request](https://github.com/Anto-30/aurelia-trading/pull/256)
- PR #191 branch head observed during assessment: `5042235f9e24e37b27ad2f93b600cac30e18c83f`
- PR #256 head observed during assessment: `16ef405df4ca0602ae93de99b38a0cfdcd791ea7`
- Common changed path: `.github/workflows/aurelia-assurance.yml`
- Stake-sizing implementation and documents are not changed by either PR.
- `config/LIVE_LOCK.yaml` is preserved unchanged on the integration branch; expected blob SHA: `b2cddd1efb0f25f35a6a08354290f805812bf34c`.

## Items intentionally not resolved by code

1. No independently approved record for $0.35 or $1.50 was found in the checked-in stake policy documents/history inspected for this report.
2. The implemented $1.00 minimum and 1% risk sizing rule is identifiable in source and tests, but no separate approval signature/authority record was found; the new registry therefore reports its provenance as pending until approval metadata is supplied.
3. Deriv authenticated account evidence and a real broker lifecycle remain blocked. Unit tests and public market-data tests cannot substitute for account evidence.
4. This integration branch has not been independently approved. Neither PR is merged by this change.

## Release status

`LIVE_EXECUTION=BLOCKED`  
`FINAL_EXECUTION_AUTHORIZATION=false`  
`capital_plane_mode=VERIFY_ONLY`

No live account authentication, broker transaction, order, credential provisioning, production deployment, or release authorization was performed by this integration.
