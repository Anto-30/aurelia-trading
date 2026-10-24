# Free LLM API Source Snapshot and Focused Review — 2026-10-24

## Scope

Read-only inspection of current upstream `main` refs and selected README, SECURITY.md, and LICENSE files using GitHub's repository API on 2026-10-24. This is a focused metadata/documentation review, not a source-code audit. No code was cloned or executed, no dependencies installed, no provider API called, and no credentials supplied.

## Exact source snapshots

These were the upstream `main` commit SHAs resolved during this review, rather than inferred commit-search results:

| Repository | Observed `main` commit | Inspected file | Blob SHA |
|---|---|---|---|
| `tashfeenahmed/freellmapi` | `5646971602a89436ce4921b0f04b99ac7bcc3728` | `README.md` | `1087a3bd2fef4a2b86e0f487df1082083964a12f` |
| `tashfeenahmed/freellmapi` | `5646971602a89436ce4921b0f04b99ac7bcc3728` | `SECURITY.md` | `a7b3a3111dbd977408b00f05471a12d8bba753a4` |
| `tashfeenahmed/freellmapi` | `5646971602a89436ce4921b0f04b99ac7bcc3728` | `LICENSE` | `8eb2b075b37107bd0403ddacc47ddcb97d46843b` |
| `open-free-llm-api/awesome-freellm-apis` | `d04877f798520a680a0a954ced5a6ee5514406c0` | `README.md` | `cc6c909953d7bb9398e033a2c92d953507f4b2d4` |
| `open-free-llm-api/awesome-freellm-apis` | `d04877f798520a680a0a954ced5a6ee5514406c0` | `LICENSE` | `eac465657bf303c7359081715cec9a695c62f554` |

These pins describe the snapshots observed on 2026-10-24; they are not claims that upstream refs will remain unchanged.

## Focused findings

### FreeLLMAPI

- README and LICENSE were retrieved from the same observed `main` commit. The root license text is MIT.
- README advertises a local OpenAI-compatible gateway, multiple provider integrations, encrypted provider-key storage, routing/failover, and a signed catalog update mechanism. These feature/security statements have not been independently tested.
- SECURITY.md explicitly identifies the software as holding provider API keys, a unified API bearer token, and dashboard-account credentials. It describes encryption-at-rest and documents `ENCRYPTION_KEY`, backups, key import/export, Docker packaging, logs, and signed catalog feed as security-sensitive areas.
- **Security-policy version mismatch:** the retrieved SECURITY.md calls `0.13.x` the current supported line, while the releases page observed during this review lists `0.16.7` dated 2026-10-21. The policy may be stale. This is a documentation/update-process risk to resolve with the maintainer before relying on its support statements; it is not proof that the current release is vulnerable.
- The README itself says the project is for personal experimentation and learning, not production, and warns free-tier capacity is not a stable supported inference substrate. Respect that limitation: do not promote it to AURELIA production routing.
- Security review still needs actual code inspection of authentication, encryption-key lifecycle, catalog signature validation and rollback behavior, update/install scripts, MCP permission boundaries, request logging/redaction, outbound provider destinations, dependencies, CI, and tests.

### Awesome Free LLM APIs

- README and LICENSE were retrieved from the same observed `main` commit. The root license text is MIT.
- The observed README says the list was updated on 2026-10-24 and claims 536+ API entries across 31 providers at the time retrieved. Counts and provider/model availability are volatile catalog claims, not guarantees.
- This is a discovery catalogue, not an inference gateway, provider security assessment, or authorization source. Provider-specific official documentation must determine terms, endpoint authenticity, data retention, training use, regional handling, eligibility, quotas, and rate limits.
- Never automatically turn this list into a production routing allowlist. Any future ingestion must be read-only initially, versioned, provenance-tracked, and reviewed against official provider sources.

## Disposition

- FreeLLMAPI: `RESEARCH_ONLY / QUARANTINED`; do not connect production credentials, private trading data, broker interfaces, or capital-plane tools.
- Awesome Free LLM APIs: `READ_ONLY_DISCOVERY_ONLY`; use only to prepare a human-reviewed provider shortlist.
- Neither candidate has been cloned, installed, built, tested, scanned, or connected to a live provider as part of this review.

## AURELIA invariants

Preserve the canonical fail-closed state without exception:

- `LIVE_EXECUTION=BLOCKED`
- `FINAL_EXECUTION_AUTHORIZATION=false`
- `capital_plane_mode=VERIFY_ONLY`
- `research_capital_authority=false`
- `external_repositories_capital_forbidden=true`

No external model/router gets authority to alter Layer 6, risk limits, kill-switch state, release gates, broker credentials, or order submission.

## Outstanding gates

1. Full source inventory at these exact commits, including manifests, lockfiles, workflows, install/update scripts, MCP definitions, and network destinations.
2. Approved isolated SAST, dependency/CVE and secret scanning, SBOM generation, and review of the results.
3. Reproducible build and tests in a disposable sandbox with no real credentials and restricted egress.
4. Provider-by-provider official terms and privacy assessment before any API traffic.
5. Resolve the FreeLLMAPI SECURITY.md supported-version mismatch.
6. Independent human review before any deployment or runtime integration.

## Sources

- https://github.com/tashfeenahmed/freellmapi/tree/5646971602a89436ce4921b0f04b99ac7bcc3728
- https://github.com/tashfeenahmed/freellmapi/blob/5646971602a89436ce4921b0f04b99ac7bcc3728/SECURITY.md
- https://github.com/tashfeenahmed/freellmapi/blob/5646971602a89436ce4921b0f04b99ac7bcc3728/LICENSE
- https://github.com/tashfeenahmed/freellmapi/releases
- https://github.com/open-free-llm-api/awesome-freellm-apis/tree/d04877f798520a680a0a954ced5a6ee5514406c0
- https://github.com/open-free-llm-api/awesome-freellm-apis/blob/d04877f798520a680a0a954ced5a6ee5514406c0/LICENSE
