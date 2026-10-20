# External Repository Review — 2026-10-20

## Scope and disposition

This is a public-source triage of four repositories requested on 2026-10-20. It is **not** a source-code security audit, SBOM, reproducible build, or integration test. No source was installed or executed, no credentials were accessed, and no broker or production action was performed. Before any adoption, pin an exact upstream commit and review the complete dependency tree, license notices, release provenance, and test results.

| Repository | License observed | Potential value | Decision for AURELIA |
|---|---|---|---|
| [remorses/playwriter](https://github.com/remorses/playwriter) | MIT | Browser automation for developer-operated UI testing and routine engineering tasks | **Optional developer tooling only. Do not use for production account control, secrets, broker actions, or unattended privileged browser sessions.** |
| [google-research/harness2](https://github.com/google-research/harness2) | Apache-2.0; third-party directories retain their own licenses | Experiments comparing/refining agent harnesses and evaluating task-level behavior | **Isolated research sandbox only. No self-modifying production agent, no automatic acceptance of proposed changes, and no access to secrets or capital plane.** |
| [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute) | MIT at inspected release path; third-party provider/model terms remain separate | Developer-time routing across model providers, subject to provider terms and data handling | **Optional development integration only after privacy, provider terms, credential storage, fallback behavior, and dependency review. Do not route broker credentials, private account data, or production secrets through it.** |
| [Adamant-im/adamant-tradebot](https://github.com/Adamant-im/adamant-tradebot) | No root LICENSE file was found at the default path during this review; verify licensing before reuse | Self-hosted centralized-exchange market-making for a defined set of CEX connectors | **Do not integrate into AURELIA's execution path. It is a separate CEX market-making bot, not a Deriv synthetic-index adapter, and its documented features include order placement. Research source only unless separately reviewed and licensed.** |

## Findings that affect security and architecture

### Playwriter

The upstream security policy states that remote control gives the recipient access to the shared browser tabs and sites those tabs can reach; it explicitly says remote control is not a sandbox. A browser session can carry authenticated cookies, administrative privileges, and access to private dashboards. If used for developer testing, use a dedicated browser profile with no production sessions, avoid remote sharing, and terminate the session immediately after the task.

Source: [Playwriter security policy](https://github.com/remorses/playwriter/blob/main/SECURITY.md).

### Harness²

The project is an agent-harness optimization framework, not a trading engine. Its README documents unrestricted executor network access and a Codex executor running with sandboxing disabled; it also requires Python 3.12 and has benchmark-specific dependencies. These defaults are unacceptable for production or for tasks that can reach secrets, private repositories, or trading systems. If evaluated, run it in a disposable environment with network egress restricted, no production credentials, synthetic tasks, fixed budgets, immutable input/output artifacts, and human review of all proposed edits.

Source: [Harness² README](https://github.com/google-research/harness2).

### OmniRoute

OmniRoute is an AI-provider gateway and routing layer, not an independent model or a guarantee of free, stable, or private inference. Its README says provider accounts/credentials are separately required and provider limits and terms control availability. Provider fallback can change the model, policy, context handling, latency, or data-processing path. If tested, use non-sensitive prompts and scoped development credentials; log provider/model/routing metadata without logging prompt secrets; disable any provider or route not explicitly approved; pin a release and review transitive dependencies before use.

Source: [OmniRoute README](https://github.com/diegosouzapw/OmniRoute).

### ADAMANT Market-Making Software

The project describes self-hosted market-making for selected centralized exchanges and documents buy/sell limit and market orders. Its exchange connectors and order-book logic do not establish compatibility with Deriv's synthetic indices, Rise/Fall contracts, or AURELIA's execution protocol. Importing it would introduce a competing execution path and violate AURELIA's single capital-plane invariant. Do not copy its order-placement logic into the canonical runtime.

Source: [ADAMANT tradebot README](https://github.com/Adamant-im/adamant-tradebot).

## Mandatory AURELIA controls

All four repositories remain non-authoritative external sources. This review does not add them to the runtime, dependency lockfiles, deployment image, or external-repository execution allowlist.

- config/LIVE_LOCK.yaml must remain unchanged.
- LIVE_EXECUTION=BLOCKED, FINAL_EXECUTION_AUTHORIZATION=false, and VERIFY_ONLY remain in force.
- No external agent, browser, model gateway, or CEX bot receives capital authority or production secrets.
- No external source may change risk thresholds, authorize orders, bypass broker verification, or promote a strategy.
- Any future adoption requires a pinned commit, license and dependency review, isolated tests, a documented rollback, and independent human review.

## Validation status

- README and selected license/security files were inspected through the public GitHub repository interface.
- No local clone, package installation, build, test suite, dependency scan, SBOM, or integration test was performed for these four repositories.
- No external repository was added to AURELIA's executable runtime or production dependency set.
- This review is a decision record, not an approval to deploy.
