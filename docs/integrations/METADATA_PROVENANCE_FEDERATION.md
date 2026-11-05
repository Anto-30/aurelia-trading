# AURELIA Metadata and Provenance Federation

**Status:** Pinned research/tooling references; no new runtime dependencies or services installed.
**Date:** 2026-11-05
**Owner:** ClaudeCode (logical routing assignment only); supporting governance/evidence/quantitative review by GoogleAgentSkills, JEV and KimiK3 when their runtimes are verified.

## Objective

Evaluate 19 requested repositories for specific metadata, lineage, agent-harness, CI and developer-tool capabilities. Preserve one canonical AURELIA evidence and release authority rather than adding overlapping metadata databases or agent supervisors.

## Inventory and pins

The exact pins, licence identifiers, routing assignments, intended mode and per-repository restrictions are recorded in `config/external_repo_federation.json` and `research/external_repositories/AURELIA_EXTERNAL_REPOSITORY_REGISTRY.md`. Pins were resolved from each repository's default branch on 2026-11-05.

The 19 sources span:
- Agent harness: oh-my-pi.
- Blockchain metadata: ethereum-lists/chains and Berachain metadata.
- Data context and semantics: OpenMetadata and Apache Ossie.
- Artifact and ML provenance: Grafeas, Google ML Metadata and OpenLineage.
- CI metadata: Docker metadata-action and Dependabot fetch-metadata.
- File/media metadata: Java and .NET metadata-extractor and Exiv2.
- Language/runtime metadata: Java Reflections, reflect-metadata, Win32 metadata and ILSpy.
- Query/site metadata: sql-metadata and Jekyll github-metadata.

## Recommended architecture

1. **Canonical source:** AURELIA's existing task journal, evidence archive, risk ledger, reconciliation records and release gates remain authoritative.
2. **Lineage interchange:** OpenLineage is the preferred schema/event reference for run/job/dataset lineage. AURELIA can map validation, walk-forward, paper, soak and release events to lineage facets without deploying a new backend.
3. **Artifact attestations:** Grafeas concepts can inform immutable artifact attestations (source commit, build run, SHA-256, SBOM, test suite and review state), but must not grant release permission.
4. **Experiment context:** ML Metadata is a comparison reference only; avoid a second experiment store unless a documented gap is proven.
5. **Semantic definitions:** Ossie is a schema candidate for canonical metric, strategy and instrument semantics. OpenMetadata is a possible future catalogue, not a default deployment.
6. **Agent harness:** oh-my-pi is not installed or executed. It has a broad shell/browser/desktop surface; any trial requires an OS-level sandbox, no broker credentials, a strict command allowlist, filesystem/network restrictions, and a worker adapter through AURELIA's existing JSONL protocol.
7. **CI supply chain:** Docker metadata-action and Dependabot fetch-metadata may be adopted in CI after immutable pinning, permission minimization and workflow review. They cannot merge or deploy.
8. **Domain-specific utilities:** chain metadata applies only to EVM integrations; media, Java/.NET, Win32, SQL and Jekyll tools remain reference-only until a concrete requirement exists.

## Licence and provenance constraints

- MIT and Apache-2.0 source licences still require notices, transitive dependency and vendored-code review.
- Exiv2's LICENSE.txt uses SPDX GPL-2.0-or-later; no embedding/redistribution without a legal decision or suitable commercial licence.
- Win32 metadata's repository-authored code is MIT-licensed, but its licence disclaimer preserves original Windows SDK header/artifact terms; GitHub reports NOASSERTION. Do not copy generated SDK-derived artifacts until provenance and legal review.
- Reflections reports WTFPL in GitHub metadata, but its root LICENSE was not found and its README says it is not actively maintained. Do not copy until exact path-level licence verification.
- Check the precise licence for every path, generated artifact and vendored component before any source reuse. A repository-level SPDX identifier does not establish every file's licence.

## Installation decision

No packages were added to AURELIA's Python dependencies, no external service was deployed, and no external agent process was started. This is deliberate:
- most projects do not apply to the current Python/Deriv synthetic-index runtime;
- OpenMetadata, MLMD and Grafeas introduce service/API/database operations not justified by current requirements;
- oh-my-pi is a separate, high-privilege agent harness and cannot be trusted as an unisolated worker;
- GPL and NOASSERTION licensing needs further review.

The Claude Code skill `.claude/skills/metadata-provenance/SKILL.md` is included. The capability matrix assigns the skill to all ten currently defined logical agents: ClaudeCode, KimiK3, GrokBot, GoogleAgentSkills, GLM, PlaywrightCLI, JEV, AURELIA, ChatGPT and Dev. This is repository configuration, not proof those providers are installed, connected or authenticated. ChatGPT's app itself cannot be modified by a GitHub commit.

## Non-negotiable boundaries

- No external source receives broker credentials, account sessions, signing keys or production secrets.
- No source may modify `config/LIVE_LOCK.yaml`, risk limits, strategy qualification or release authorization.
- No external lineage/catalogue event proves a broker order or account balance.
- No auto-promotion, auto-merge or live deployment based on external agent output.
- Keep `LIVE_EXECUTION: BLOCKED` and `FINAL_EXECUTION_AUTHORIZATION: false` unchanged.

## Acceptance criteria for future adoption

A candidate can move beyond reference-only only with a specific use case, exact pin, path-level licence review, SBOM/vulnerability review, isolated test, deterministic replay, regression evidence, independent security review and explicit human release approval.
