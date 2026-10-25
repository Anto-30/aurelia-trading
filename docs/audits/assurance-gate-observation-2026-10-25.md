# Assurance Gate Observation — 2026-10-25

This is a follow-up to `external-repository-integration-review-2026-10-25.md` and records the final status observed after the review branch's latest push.

## Result

- `federation-audit`: **success** on review head `aab6517ce6bf13a0413daf1fe9dff37d48b32c36`.
- `continuity`: **success** on review head `aab6517ce6bf13a0413daf1fe9dff37d48b32c36`.
- `assurance`: **failure by environment protection**, not a reported code-test failure. GitHub's check annotations state that `refs/pull/208/merge` and `audit/external-repositories-2026-10-25` are not allowed to deploy to the `production` environment, and the deployment was rejected or did not satisfy the protection rules.

## Decision

Do not bypass or approve the production environment gate to make this documentation-only PR green. The rejection is consistent with fail-closed governance for an unapproved branch. Keep production credentials and authenticated Deriv lifecycle steps gated. If the assurance workflow must run on pull requests, refactor it so unprivileged PR checks are separate from production-environment verification; never make secrets available to untrusted PR code merely to obtain a green check.

This observation does not certify the workflow's complete secret handling, and it does not mean the candidate repositories were tested. The PR remains open and requires an independent approval; no merge, deployment, or live execution occurred.
