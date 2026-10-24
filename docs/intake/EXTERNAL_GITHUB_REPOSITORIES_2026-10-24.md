# External GitHub Repository Intake — 2026-10-24

**Status:** preliminary / research-only. **No repository has been installed, executed, or promoted.**  
**AURELIA execution posture:** `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`.

This manifest pins the 30 user-supplied repositories to default-branch commit SHAs observed on 2026-10-24. GitHub API license metadata is indicative only; it is not a legal determination and does not replace root/nested LICENSE, NOTICE, per-file, dependency, and transitive-license review.

| # | Repository | Branch | Commit SHA | GitHub API license metadata | Initial disposition |
|---:|---|---|---|---|---|
| 1 | [PacktPublishing/Hands-On-Machine-Learning-for-Algorithmic-Trading](https://github.com/PacktPublishing/Hands-On-Machine-Learning-for-Algorithmic-Trading) | master | `c7291523e95bce9dde21ea1b8acd5682f96f5cac` | MIT | Research/education only; pinned source last committed 2023-01-18; old Python/scientific stack and strategy results require revalidation |
| 2 | [semantic-release/github](https://github.com/semantic-release/github) | master | `0c577cbaefd8c7402a22729f69180c3d9b3cbf1c` | MIT | Sandbox-only release automation; synthetic credentials and disposable repository |
| 3 | [github/github-mcp-server](https://github.com/github/github-mcp-server) | main | `f38526264abb14961b32cea386e38ec6d3cf674f` | MIT | Sandbox-only; broad read/write GitHub tool surface; least privilege and prompt-injection/egress review required |
| 4 | [521xueweihan/HelloGitHub](https://github.com/521xueweihan/HelloGitHub) | master | `030121514da552ed91e640ef8bde4083c753dd52` | Not detected | Reference-only; verify licensing of the project and linked third-party repositories individually |
| 5 | [anuraghazra/github-readme-stats](https://github.com/anuraghazra/github-readme-stats) | master | `54a7985aeefda00d5eadb55b80c17c7f976c37d2` | MIT | Profile/web tooling only; review external API, caching, rate-limit and deployment exposure |
| 6 | [521xueweihan/GitHub520](https://github.com/521xueweihan/GitHub520) | main | `6ea5e106d236e12c1e69341eea410a8d5dd27ba6` | Not detected | Reference-only; no automatic host/network configuration changes |
| 7 | [skills/introduction-to-github](https://github.com/skills/introduction-to-github) | main | `dbe048e0b08f0ba1e1a2634ae69aa10f6327832a` | MIT | Educational reference |
| 8 | [gitbutlerapp/gitbutler](https://github.com/gitbutlerapp/gitbutler) | master | `8b922fedf1a651e1cbd1abcb11fcfa53bcce58a4` | NOASSERTION | Developer workstation tool only; license gate remains open |
| 9 | [conwnet/github1s](https://github.com/conwnet/github1s) | master | `bf13d041f1e3ece9fa0bce7639bc093203871db5` | MIT | Reference/developer tool; no private repository data unless explicitly authorized |
| 10 | [academicpages/academicpages.github.io](https://github.com/academicpages/academicpages.github.io) | master | `7b958332ce9970cfb6987a049d7684ac615397e8` | MIT | Website template only; inspect theme/build dependencies before deployment |
| 11 | [desktop/desktop](https://github.com/desktop/desktop) | development | `bf4ec63e50eae5c5cde7043fe2eb7c94c881dd34` | MIT | Developer workstation tool only |
| 12 | [pwntester/octo.nvim](https://github.com/pwntester/octo.nvim) | master | `8461d99d13cca243f89848bf4d9fadee096f0a48` | MIT | Editor integration sandbox; review token scopes and commands |
| 13 | [refined-github/refined-github](https://github.com/refined-github/refined-github) | main | `12ab2729861f438f168a56338b9598e67925d53f` | MIT | Browser extension sandbox; inspect permissions/content scripts/update chain |
| 14 | [maxiaof/github-hosts](https://github.com/maxiaof/github-hosts) | master | `00f8f9c094964e503d58401a509aa921a0648dcc` | NOASSERTION | Reference-only; no host-file changes without source review and rollback plan |
| 15 | [abhisheknaiidu/awesome-github-profile-readme](https://github.com/abhisheknaiidu/awesome-github-profile-readme) | master | `a2f2de46099a6d503d9240d8f90b4f504755b27f` | CC0-1.0 | Curated reference list; downstream projects need separate review |
| 16 | [google/go-github](https://github.com/google/go-github) | master | `64e5188a52deb30d534dc4d5b30a5c6c3541b334` | BSD-3-Clause | Candidate Go REST SDK; pin dependency version and test auth/pagination/rate-limit behavior |
| 17 | [gitkraken/vscode-gitlens](https://github.com/gitkraken/vscode-gitlens) | main | `5a7c061756ae3059973c98182c2b58e133670977` | NOASSERTION | Editor extension; LICENSE and LICENSE.plus both exist; resolve licensing/feature scope before use |
| 18 | [PyGithub/PyGithub](https://github.com/PyGithub/PyGithub) | main | `5aeb43916b197a0fe8016600817b868fc894af5a` | LGPL-3.0 (API field) | Candidate Python REST SDK; COPYING and COPYING.LESSER exist; inspect all applicable terms and dependencies |
| 19 | [mouredev/hello-git](https://github.com/mouredev/hello-git) | main | `103093203ceff26a05c629bc4798153000224a1e` | Apache-2.0 | Educational reference |
| 20 | [arslanbilal/git-cheat-sheet](https://github.com/arslanbilal/git-cheat-sheet) | main | `4098de6b02a1a9ccb0f7e1eb8b6da29d91c67841` | Not detected | Reference-only; license verification required before redistribution |
| 21 | [ineo6/hosts](https://github.com/ineo6/hosts) | master | `11fde366b4318acb322a25174e1721b2f1113d81` | MIT | Host/network utility; package scripts and network data source require review; do not run or apply automatically |
| 22 | [jenkinsci/github-branch-source-plugin](https://github.com/jenkinsci/github-branch-source-plugin) | master | `801e40614d00819c1b7f379e260aa7c071a47b12` | MIT | Sandbox-only CI integration; test webhook/credential/job-trigger boundaries |
| 23 | [Wechat-ggGitHub/Awesome-GitHub-Repo](https://github.com/Wechat-ggGitHub/Awesome-GitHub-Repo) | main | `b580168c397e5345ddd1454272da90a115cc80b7` | CC0-1.0 | Curated reference list; downstream projects need separate review |
| 24 | [ekalinin/github-markdown-toc](https://github.com/ekalinin/github-markdown-toc) | master | `7af407ac43d0106664bb3b7fc9cf882964042ef7` | MIT | Documentation build helper; unprivileged evaluation only |
| 25 | [GTFOBins/GTFOBins.github.io](https://github.com/GTFOBins/GTFOBins.github.io) | master | `acd524623f9c406acedd2754ebd9c2431f3675ad` | GPL-3.0 | Security reference only; no operational integration into trading infrastructure |
| 26 | [CarGuo/gsy_github_app_flutter](https://github.com/CarGuo/gsy_github_app_flutter) | master | `93a055576a94ca250b67434bf11ac23546c8013f` | Apache-2.0 | Educational Flutter app; not a trading runtime dependency |
| 27 | [CarGuo/GSYGithubAPP](https://github.com/CarGuo/GSYGithubAPP) | master | `f6c15328ddca8b6b9e2a1812108a1a006bd098be` | Apache-2.0 | Related React Native app; compare overlap with Flutter variant before any reuse |
| 28 | [robotze/GithubDesktopZhTool](https://github.com/robotze/GithubDesktopZhTool) | main | `61a7c4cddf78498be84116547c4f76fc20073113` | Not detected | Desktop-client localization/modification; license and patch/install behavior unverified |
| 29 | [jonbarron/jonbarron.github.io](https://github.com/jonbarron/jonbarron.github.io) | master | `2ccee987d9690acd43a3914415f60960fa54da25` | Not detected | Personal website reference only; no reuse pending license check |
| 30 | [ryo-ma/github-profile-trophy](https://github.com/ryo-ma/github-profile-trophy) | master | `e3c89df995e92e67cdd4b2acaab9d974583dc1f7` | MIT | Profile widget only; review API/rate-limit and deployment exposure |

## Focused source inspection performed

Root directory listings were inspected for the following pinned repositories: Packt's algorithmic-trading examples, GitHub MCP Server, semantic-release GitHub plugin, go-github, PyGithub, GitLens, and both host-file utilities.

- Packt's repository includes `environment.yml`, platform-specific environment files, chapter notebooks/scripts, and a LICENSE. Its README describes a legacy Python 2.7/3.5-era stack. Treat it as historical learning material; do not transplant old dependencies or accept strategy claims without independent, cost-adjusted, no-lookahead replays.
- GitHub MCP Server's README explicitly describes reading code and managing issues, pull requests, and workflows. It is a privileged integration surface, not a passive read-only library by default. `server.json` documents OAuth/PAT authentication and a local container OAuth callback port. Any trial must use a dedicated least-privilege identity, disabled write-capable tools where possible, restricted egress, synthetic/non-production repositories, and attributable logs.
- `semantic-release/github` contains `package.json` and `package-lock.json`; its package declares Node engine requirements and dependencies including Octokit retry/throttling/pagination plugins. A release token and publish workflow make this a CI supply-chain component; no production release credentials during evaluation.
- `google/go-github` contains Go module and checksum files; `PyGithub` contains `pyproject.toml`, `COPYING`, and `COPYING.LESSER`. Dependency and license scans are not yet complete.
- GitLens root includes `LICENSE`, `LICENSE.plus`, `ThirdPartyNotices.txt`, `package.json`, and `pnpm-lock.yaml`. The API's `NOASSERTION` is a hold, not a clean license result.
- `ineo6/hosts` has `package.json`, lockfiles, a CLI entry point, and host data. Its package includes network/DNS-related dependencies and build/binary-packaging scripts. Do not run its CLI or alter host configuration before a full code review and reversible test.

These are bounded metadata/root-file observations, not a complete source, license, vulnerability, malware, or behavioral audit. No packages were installed and no candidate code was executed.

## Required remaining gates

1. Review complete LICENSE/NOTICE and nested/per-file licensing, especially repositories with no API license or `NOASSERTION`; obtain legal review where needed.
2. Run exact-SHA dependency inventory, SBOM and vulnerability scans; verify scan coverage and triage by reachable package/version/path/fix availability.
3. Review install/build/release scripts, GitHub Actions, extension permissions, token scopes, network egress, telemetry, filesystem and command access.
4. Run focused tests only in disposable unprivileged environments with synthetic credentials and restricted network access. Do not test privileged MCP/CI components against production.
5. For the Packt repository, port no code until compatibility, provenance, licensing and independent cost-adjusted research validation are complete.
6. Obtain independent human review before merging this documentation PR or changing any admission status.
7. Keep every candidate outside the AURELIA production runtime until a separately reviewed promotion record explicitly authorizes it.

## Safety invariants

- No live orders, broker credentials, capital authority, execution permissions, or release authority for external repositories.
- No changes to `config/LIVE_LOCK.yaml`, production secrets/environment, or deployment.
- `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY` remain mandatory.
- DeepSeekHarness/other external agents remain unavailable until authenticated runtime connection and attributable execution evidence exist.


## Additional exact-SHA tree inventory — 2026-10-24

Recursive Git tree API responses were retrieved at the pinned commits for eight additional/high-priority source snapshots. These checks identify files and dependency surfaces; they do not execute builds or establish vulnerability status.

| Repository at pinned SHA | Tree result | License files observed | Dependency/build surface observed | Disposition update |
|---|---:|---|---|---|
| `github/github-mcp-server` — `f38526264abb14961b32cea386e38ec6d3cf674f` | 660 files; not truncated | Root `LICENSE` plus numerous vendored third-party LICENSE/NOTICE files | `go.mod`, `go.sum`, `Dockerfile`, `.github/actions/build-ui/action.yml`, `ui/package.json`, `ui/package-lock.json` | Inventory is substantial; must reconcile vendored notices/SBOM and review container/action/tool permissions before sandbox execution |
| `semantic-release/github` — `0c577cbaefd8c7402a22729f69180c3d9b3cbf1c` | 50 files; not truncated | Root `LICENSE` | `package.json`, `package-lock.json` | Exact dependency lock exists; no install/test or vulnerability scan run |
| `PacktPublishing/Hands-On-Machine-Learning-for-Algorithmic-Trading` — `c7291523e95bce9dde21ea1b8acd5682f96f5cac` | 882 files; not truncated | Root `LICENSE` | Root and chapter-level Conda `environment.yml` files, including Zipline/Pyfolio environments | Do not install the historical environment on a host; recreate in isolated disposable environment only after licensing and compatibility review |
| `jenkinsci/github-branch-source-plugin` — `801e40614d00819c1b7f379e260aa7c071a47b12` | 568 files; not truncated | Root `LICENSE.txt` | Maven `pom.xml`, demo Dockerfile | Sandbox CI/webhook/credential boundaries only |
| `gitkraken/vscode-gitlens` — `5a7c061756ae3059973c98182c2b58e133670977` | 2,920 files; not truncated | `LICENSE`, `LICENSE.plus`, package-specific licenses, third-party notices observed in prior root listing | Root `package.json`, `pnpm-lock.yaml`, many package manifests including plus/AI/GitHub integrations | License and feature-scope review required; do not assume the root license covers all Plus features |
| `ineo6/hosts` — `11fde366b4318acb322a25174e1721b2f1113d81` | 29 files; not truncated | Root `LICENSE` | `package.json`, `package-lock.json`, `yarn.lock` | Two lockfiles require reconciliation; inspect data source, install/build scripts and exact host-write behavior before use |
| `maxiaof/github-hosts` — `00f8f9c094964e503d58401a509aa921a0648dcc` | 11 files; not truncated | Root `LICENSE` exists despite GitHub API returning `NOASSERTION` | Maven `pom.xml` | Read the actual license text and inspect update/host-write behavior; API metadata alone is insufficient |
| `PyGithub/PyGithub` — `5aeb43916b197a0fe8016600817b868fc894af5a` | 1,504 files; not truncated | `COPYING`, `COPYING.LESSER` | `pyproject.toml` | Read the applicable license terms and resolve dependency/license obligations before bundling |

### Evidence boundary

- The recursive-tree responses were complete (GitHub returned `truncated: false`) for the eight repositories above.
- Root-file existence is not a full license determination. No full text legal review, SPDX normalization, license compatibility decision, SBOM generation, CVE scan, secret scan, static analysis, dynamic analysis, install, or test was completed by this pass.
- No dependency installation was performed; the tree API only returned paths and object metadata.
- The earlier GitHub API license label `NOASSERTION` for `maxiaof/github-hosts` does not mean no license file exists: a root `LICENSE` file is present at the pinned commit. Its text still needs review.
- GitHub MCP Server contains vendored third-party licenses and multiple build surfaces; this increases the need for SBOM/license reconciliation and sandboxing rather than reducing it.

## Closure decision

**Intake stage: complete. Admission stage: not approved.** The only safe closure for this batch without performing the missing code-security/legal work is to keep all 30 candidates research/reference/sandbox-only and keep PR #194 as a draft pending independent review. No candidate is approved for production or trading runtime.


## Root-level license and dependency manifest presence across all 30 candidates

Checked the pinned branch names' root directory listings through the GitHub Contents API on 2026-10-24. This table records file presence only; it is not proof that all nested licenses or dependencies have been enumerated. Rows marked `none observed` are held from reuse until licensing is resolved.

| Repository | Root license/notice file(s) observed | Root dependency/build files observed |
|---|---|---|
| PacktPublishing/Hands-On-Machine-Learning-for-Algorithmic-Trading | `LICENSE` | `environment.yml` |
| semantic-release/github | `LICENSE` | `package.json`, `package-lock.json`, `.github/` |
| github/github-mcp-server | `LICENSE` | `go.mod`, `go.sum`, `Dockerfile`, `.github/` |
| 521xueweihan/HelloGitHub | none observed | `.github/` |
| anuraghazra/github-readme-stats | `LICENSE` | `package.json`, `package-lock.json`, `.github/` |
| 521xueweihan/GitHub520 | none observed | `requirements.txt`, `.github/` |
| skills/introduction-to-github | `LICENSE` | `.github/` |
| gitbutlerapp/gitbutler | `LICENSE.md` | `Cargo.toml`, `Cargo.lock`, `package.json`, `pnpm-lock.yaml`, `Makefile`, `.github/` |
| conwnet/github1s | `LICENSE` | `package.json`, `package-lock.json`, `.github/` |
| academicpages/academicpages.github.io | `LICENSE` | `Gemfile`, `package.json`, `Dockerfile` |
| desktop/desktop | `LICENSE` | `package.json`, `yarn.lock`, `.github/` |
| pwntester/octo.nvim | `LICENSE` | `Makefile`, `.github/` |
| refined-github/refined-github | `license` | `package.json`, `package-lock.json`, `.github/` |
| maxiaof/github-hosts | `LICENSE` | `pom.xml` |
| abhisheknaiidu/awesome-github-profile-readme | `LICENSE` | `.github/` |
| google/go-github | `LICENSE` | `go.mod`, `go.sum`, `.github/` |
| gitkraken/vscode-gitlens | `LICENSE`, `LICENSE.plus` | `package.json`, `pnpm-lock.yaml`, `.github/` |
| PyGithub/PyGithub | `COPYING`, `COPYING.LESSER` | `pyproject.toml`, `.github/` |
| mouredev/hello-git | `LICENSE` | no common dependency manifest observed at root |
| arslanbilal/git-cheat-sheet | none observed | no common dependency manifest observed at root |
| ineo6/hosts | `LICENSE` | `package.json`, `package-lock.json`, `yarn.lock`, `.github/` |
| jenkinsci/github-branch-source-plugin | `LICENSE.txt` | `pom.xml`, `.github/` |
| Wechat-ggGitHub/Awesome-GitHub-Repo | `LICENSE` | no common dependency manifest observed at root |
| ekalinin/github-markdown-toc | `LICENSE` | `Dockerfile`, `Makefile`, `.github/` |
| GTFOBins/GTFOBins.github.io | `LICENSE` | `Gemfile`, `Dockerfile`, `Makefile`, `.github/` |
| CarGuo/gsy_github_app_flutter | `LICENSE` | `pubspec.yaml`, `.github/` |
| CarGuo/GSYGithubAPP | `LICENSE` | `package.json`, `package-lock.json`, `.github/` |
| robotze/GithubDesktopZhTool | none observed | no common dependency manifest observed at root |
| jonbarron/jonbarron.github.io | none observed | no common dependency manifest observed at root |
| ryo-ma/github-profile-trophy | `LICENSE` | `Dockerfile`, `.github/` |

### Corrective license triage

- GitHub's repository metadata returned `NOASSERTION` for `maxiaof/github-hosts`, but the pinned root tree does contain `LICENSE`. Read and classify that actual license before reuse.
- GitLens has `LICENSE` and `LICENSE.plus`; the latter and feature-specific packages require separate terms review. Do not assume one root label covers every feature.
- PyGithub has `COPYING` and `COPYING.LESSER`; its actual applicable license obligations and dependency notices must be checked before bundling.
- No root license file was observed for HelloGitHub, GitHub520, arslanbilal/git-cheat-sheet, robotze/GithubDesktopZhTool, or jonbarron/jonbarron.github.io at the checked roots. Keep these reference-only and do not redistribute or incorporate code until an authoritative license is found.
- The root listing does not prove absence of nested licenses, data-set terms, notebook content rights, or third-party assets. Recursive tree and per-file review remains necessary for every candidate.


## Recursive tree completeness check — all 30 pinned snapshots

GitHub's recursive Git Trees API was queried for each exact commit SHA in the table above. All 30 requests returned successfully with `truncated: false`. The counts below are blob/file entries returned by GitHub for the pinned tree, not audited or tested file counts.

| Repository | Blob entries | Tree response truncated? | License files found in recursive path scan |
|---|---:|---|---|
| PacktPublishing/Hands-On-Machine-Learning-for-Algorithmic-Trading | 882 | No | `LICENSE` |
| semantic-release/github | 50 | No | `LICENSE` |
| github/github-mcp-server | 660 | No | Root `LICENSE` plus numerous vendored third-party licenses/notices |
| 521xueweihan/HelloGitHub | 266 | No | None matching the root/nested license filename scan |
| anuraghazra/github-readme-stats | 132 | No | `LICENSE` |
| 521xueweihan/GitHub520 | 17 | No | None matching the license filename scan |
| skills/introduction-to-github | 25 | No | `LICENSE` |
| gitbutlerapp/gitbutler | 5,573 | No | `LICENSE.md` plus image/icon asset files whose names contain “license” |
| conwnet/github1s | 391 | No | Root `LICENSE` and extension-specific licenses |
| academicpages/academicpages.github.io | 313 | No | `LICENSE` |
| desktop/desktop | 2,609 | No | Root `LICENSE`, vendor licenses and fixture license files |
| pwntester/octo.nvim | 139 | No | `LICENSE` |
| refined-github/refined-github | 593 | No | Root `license` |
| maxiaof/github-hosts | 11 | No | `LICENSE` |
| abhisheknaiidu/awesome-github-profile-readme | 11 | No | `LICENSE` |
| google/go-github | 578 | No | `LICENSE` |
| gitkraken/vscode-gitlens | 2,920 | No | `LICENSE`, `LICENSE.plus`, `ThirdPartyNotices.txt`, and package-specific licenses |
| PyGithub/PyGithub | 1,504 | No | `COPYING`, `COPYING.LESSER` |
| mouredev/hello-git | 95 | No | `LICENSE` |
| arslanbilal/git-cheat-sheet | 18 | No | None matching the license filename scan |
| ineo6/hosts | 29 | No | `LICENSE` |
| jenkinsci/github-branch-source-plugin | 568 | No | `LICENSE.txt` |
| Wechat-ggGitHub/Awesome-GitHub-Repo | 2 | No | `LICENSE` |
| ekalinin/github-markdown-toc | 58 | No | `LICENSE` |
| GTFOBins/GTFOBins.github.io | 518 | No | `LICENSE` |
| CarGuo/gsy_github_app_flutter | 596 | No | Root `LICENSE` and vendored dependency licenses |
| CarGuo/GSYGithubAPP | 292 | No | `LICENSE` |
| robotze/GithubDesktopZhTool | 3 | No | None matching the license filename scan |
| jonbarron/jonbarron.github.io | 353 | No | None matching the license filename scan |
| ryo-ma/github-profile-trophy | 53 | No | `LICENSE` |

### What this proves — and what it does not

- **Proves:** all 30 pinned SHA tree responses were returned and none was marked truncated by GitHub.
- **Does not prove:** source correctness, absence of malicious code, legal compatibility, full license coverage (filename heuristics can miss unusual names), dependency safety, absence of CVEs/secrets, build reproducibility, runtime behavior, or trading value.
- A repository with no license file detected remains on hold for code reuse/redistribution unless an authoritative license is established. A repository with a license file still requires review of its text, subcomponents, embedded data, vendored files and dependencies.
- No repository was cloned or built from this API-only tree check. No SBOM, vulnerability scan, secret scan, static analyzer, dynamic test, or isolated execution was run in this step.

## Intake gate outcome after tree check

**Source inventory is complete for this batch at the metadata/tree level. Security/legal qualification is still incomplete.** Do not mark all candidates “audited” or “approved”; retain the existing per-candidate restrictions and require separate evidence for any promotion.


## Selected license-text spot checks at pinned commits

Read the beginning of the following exact license files, beyond relying on GitHub's metadata field:

- github/github-mcp-server/LICENSE: MIT License, copyright GitHub (2025). This covers the project's own license text; vendored dependencies still require their individual notices/terms to be preserved.
- semantic-release/github/LICENSE: MIT License, copyright Contributors (2017).
- PacktPublishing/Hands-On-Machine-Learning-for-Algorithmic-Trading/LICENSE: MIT License, copyright Packt (2018). This does not qualify any strategy, notebook output, dataset, or external data source as economically valid or necessarily covered by the same terms.
- gitkraken/vscode-gitlens/LICENSE explicitly says paths in or under a directory named plus are instead covered by LICENSE.plus. The LICENSE.plus file is headed “GitLens Pro License” and identifies GitKraken; therefore the API NOASSERTION must not be interpreted as permission to use Plus features under the base license.
- PyGithub/PyGithub/COPYING.LESSER contains GNU LGPL version 3 terms. The repository also contains COPYING; verify the complete applicable license and distribution obligations, plus third-party dependency terms, before bundling.
- maxiaof/github-hosts/LICENSE contains the Mulan Permissive Software License, Version 2, in Chinese. This explains why GitHub's API NOASSERTION label is not the same as an absent license file; obtain a reliable interpretation of the actual terms before reuse.

These are targeted text spot checks, not a full legal opinion or exhaustive license-compliance review. No code was executed and no dependency packages were installed.


## Additional candidate 31 — Bruno API client

**Repository:** https://github.com/usebruno/bruno  
**Pinned ref:** `main` at commit `ab6e3efa6346cd7778971d73404cc45ba3bfc47d` (commit timestamp reported by GitHub: `2026-10-24T10:20:09Z`; captured 2026-10-24).  
**Repository metadata:** public, active, default branch `main`; GitHub API license metadata and root `license.md` both identify MIT.  
**Tree inventory:** 5,049 blob entries; recursive Git Trees response `truncated: false`. Root `package.json` and `package-lock.json`; multiple package workspaces with individual `package.json` files; several package-level license files; Dockerfiles for CLI images; seven GitHub Actions workflow files observed.

**Purpose and potential relevance:** Bruno is a desktop API client and CLI for exploring/testing APIs; its README describes file-based plain-text request collections and local/offline-first storage. It may be useful as a human-operated API verification harness for AURELIA's non-production endpoints and mock/test fixtures. It is not a trading strategy, broker execution adapter, risk engine, or proof of Deriv API compatibility.

**Security and integration guardrails:**
- Treat all Bruno collections, scripts, environment files, imported certificates, and request bodies as executable or secret-bearing test artifacts. Never place production/live Deriv tokens in collections or environments.
- Trial only against local mocks or an explicitly authorized non-production endpoint with synthetic credentials; disable write/destructive operations where possible and inspect scripts, pre/post-request hooks, environment interpolation and imported collection content first.
- Keep collection variables free of real secrets; avoid committing auth headers, client certificates, account identifiers or response data. Use dedicated throwaway credentials if authentication is necessary.
- Do not install the desktop app/CLI or run its scripts as part of this intake. Review package manifests, lockfile, package-level licenses, CI permissions, release provenance, and applicable advisories before any sandbox trial.
- The public repository Security page lists historical advisories, including advisories concerning OAuth callback state validation, the Axios npm supply-chain incident, a transitive `@postman/tunnel-agent` compromise, Safe-Mode handling in asserts, and XSS in environment names. These are **review leads, not a finding that the pinned commit is vulnerable**; verify each advisory's affected and patched ranges against the pinned dependency graph and release before any use.
- The MIT root license does not automatically settle terms for every dependency, icon, logo, or paid/commercial feature. The README separately identifies the Bruno name as a trademark and the logo source as OpenMoji under CC BY-SA 4.0.

**Status:** `INTAKE_ONLY — NOT SECURITY-QUALIFIED — NOT INSTALLED — NOT EXECUTED — NOT PROMOTED`. No SBOM, CVE scan, secret scan, build, or test was performed in this intake. The SHA pins source identity only; it does not attest to safety or suitability.
