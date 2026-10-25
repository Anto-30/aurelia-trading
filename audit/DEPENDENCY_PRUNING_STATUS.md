# Dependency Pruning and Audit Status — 2026-10-25

## Scope and evidence boundary

This record reflects read-only inspection of the GitHub repository at the time of review. It is not a completed third-party repository security audit. No repository was cloned or executed for this report, and no dependency scanner output is represented as having run.

## Phase 1 candidate checks

| Candidate | Search result in repository code | Dependency manifest evidence | Action |
|---|---|---|---|
| `coder/agentapi` | No indexed match found in GitHub repository code search | `requirements.txt` on `main` contains only `websockets==17.1`; no root `package.json` was found in the inspected PR branch | No dependency entry was found to remove. Do not delete unrelated files or references based on a name-only search. |
| `composio-community/awesome-codex-skills` | No indexed match found in GitHub repository code search | Same as above | No dependency entry was found to remove. |
| `cline/prompts` | No indexed match found in GitHub repository code search | Same as above | No dependency entry was found to remove. |

A GitHub code-search miss is not a complete proof that a string is absent from every branch, Git history, generated artifact, or external submodule. Before claiming complete pruning, search the exact PR head and repository history locally or in a controlled CI job. These candidates were not removed from research documentation because documenting a candidate is not the same as installing it as a dependency.

## Phase 2 — remaining candidate inventory

The earlier intake record for PR #198 lists eight deduplicated repository URLs, not the 19 candidates referenced in the supplied rubric. It explicitly says exact upstream source-head pinning, clone, SBOM, license/dependency/security scans, and isolated tests had not been run. The exact identities of the purported 19 remaining candidates are not present in that intake record. OpenHands, Aider, Goose, Codex, and libiec61850 were examples in the instruction, not a complete, pinned candidate manifest.

**Disposition: BLOCKED pending a complete candidate manifest.** Do not claim 19 repositories have been audited and do not install or execute candidate code merely to create audit logs. For each candidate, record the canonical repository URL, exact commit SHA, license evidence, lockfiles, maintainer/maintenance evidence, scanner versions, scan exit codes, artifact hashes, and explicit keep/reject decision.

## Current in-repository dependency evidence

- Python runtime requirement: `websockets==17.1` in `requirements.txt`.
- `pyproject.toml` declares `websockets>=17.1,<18` and optional `torch>=2.6,<3`.
- No `package.json` was found at the inspected repository root; therefore `npm audit` and `license-checker` cannot be treated as applicable to a root Node dependency graph without locating an actual Node project.
- No `pip-audit`, license, SAST, secret-scan, SBOM, or malware-scan result is asserted by this document.

## Required next evidence

1. Supply or commit the exact list of the 19 candidates and their intended use.
2. Run pinned, secret-free scans against the exact candidate commit SHAs in disposable, network-restricted environments.
3. Attach raw outputs and SHA-256 manifests; preserve non-zero scanner exit codes and distinguish scanner errors from clean results.
4. Review license obligations, transitive dependencies, install scripts, model/data terms, secrets in Git history, and any network/file execution surface.
5. Keep all candidates outside the AURELIA production runtime and capital plane until independent review.

## Safety state

`LIVE_EXECUTION=BLOCKED`; `FINAL_EXECUTION_AUTHORIZATION=false`; `capital_plane_mode=VERIFY_ONLY`. No broker/payment API call, payment, withdrawal, verification-code dispatch, or trading order is authorized by this audit record.
