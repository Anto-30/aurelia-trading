# DeepSeekHarness external tool intake — 2026-10-23

Status: **PINNED AND REGISTERED FOR REVIEW — NOT INSTALLED OR CONNECTED**

This intake records four user-supplied repositories for engineering evaluation only. It does not authorize execution, deployment, persistent agent installation, access to production secrets, or changes to the AURELIA capital plane.

## Source pins

| Repository | Default branch | Reviewed HEAD | Declared license | Initial classification |
|---|---|---|---|---|
| https://github.com/mvschwarz/openrig | `main` | `48ea010b4c899af35114da0db0d2c9f437b54dbb` | Apache-2.0 | SANDBOX_ONLY; high-impact workstation/harness configuration |
| https://github.com/1jehuang/jcode | `master` | `7d342c133df9f8dfea05445bb91a5013c3639367` | MIT | TOOLCHAIN_ONLY pending source/dependency review |
| https://github.com/jgravelle/jcodemunch-mcp | `main` | `d56f459210cc0ef0c6ee8ec60b45112466a3f7b5` | Dual-Use License 1.2; GitHub API reports NOASSERTION | REFERENCE_ONLY until legal/commercial-use determination and security review |
| https://github.com/trycua/hermes-cua-spaces | `main` | `82bb8d31517d2d1b8f1ef7f64701558dcac8aea9` | MIT | SANDBOX_ONLY; isolated Cua Space adapter, not a trusted execution authority |

Pins are the default-branch HEADs observed on 2026-10-23. Re-check before any installation; do not silently advance pins.

## Initial risk findings

### OpenRig
OpenRig is a local agent orchestration daemon/CLI with MCP support. Its documentation says setup can write harness trust records, executable hooks, skills, plugins and workspace guidance; the kernel can receive broad permissions depending on runtime/provider configuration. Do not run its installer or setup against a developer home directory or AURELIA checkout as part of this intake. If evaluated, use a disposable OS user/container and inspect all file writes, hooks, permission defaults and network behavior first.

### jcode
jcode is a Rust coding-agent harness for parallel agent sessions. Its README presents a shell-pipe installer. Do not execute remote installer scripts directly. Review source, Cargo dependency graph, build scripts, subprocess permissions, network access and agent command policy at the pinned commit before building in a disposable environment.

### jcodemunch-mcp
This MCP server provides symbol-level code retrieval and indexing. Its repository license is a Dual-Use License (version 1.2, effective 2026-10-21), not a permissive open-source license: non-commercial use is free, while commercial use requires a paid license, and redistribution has additional restrictions. The license must be reviewed against the intended AURELIA/DeepSeekHarness use before installing or deploying it. Security documentation describes path traversal and symlink protections, ignore rules, and secret-file exclusion; verify these controls in tests and do not index production secrets, credentials, private keys, or unrelated home-directory content.

### Hermes on Cua Spaces
This plugin routes Hermes terminal, file and code operations into a Cua Space. Its README says the plugin skips risky-command prompts for Spaces it creates. That is a material trust boundary: never connect it to the AURELIA runtime, broker credentials, live account sessions, production secrets, or a workspace containing them. Any test must use a disposable Space, synthetic fixture repository, explicit egress restrictions and no authenticated broker endpoints. The plugin's own README installation instructions are documentation only, not an installation performed by this intake.

## Required controls

- Mode is research/reference/toolchain/sandbox only; `capital_authority=false`.
- No live orders, broker writes, secret access, deployment authority or mutation of `LIVE_LOCK.yaml`.
- External code execution is deny-by-default until exact-commit review.
- No `curl | sh`, `curl | bash`, `irm | iex`, or other remote installer execution in a trusted environment.
- Use disposable least-privilege workspaces with no host home mounts, no production environment variables, bounded CPU/memory/time, and allowlisted outbound network.
- Generate an SBOM and dependency/security scan for any selected component.
- Run only synthetic local smoke tests; record commands, tool versions, results and cleanup evidence.
- Independent review and passing CI are required before enabling any sandbox workflow.

## Readiness ledger

| Gate | Status |
|---|---|
| Repository and default branch identified | COMPLETE |
| Exact HEAD pins recorded | COMPLETE |
| Initial license/security triage | PARTIAL; detailed review pending |
| Registry integration | COMPLETE for metadata only; both canonical JSON registries updated and re-read/JSON-parsed |
| Dependencies installed | NO |
| SBOM / vulnerability scan | NOT RUN |
| Isolated smoke tests | NOT RUN |
| DeepSeekHarness runtime binding | NOT CONNECTED |
| Independent review | PENDING |
| Production/capital authority | DENIED |

## Registry commits and verification

- `config/external_repo_federation.json`: commit `0b1951d05682a43af933702646fad59219aaf5cc`; four pinned entries appended; total registry entries: 303.
- `config/agent_tool_skill_assignment.json`: commit `731950fbe4ddba059e5662ec35e738a4f66d8157`; records the batch, guardrails and pending validation status.
- Both files were fetched again and parsed as JSON after the writes. All four repository pins and `capital_authority=false` were confirmed.
- `config/LIVE_LOCK.yaml` on this branch has the same blob SHA as `main` (`b2cddd1efb0f25f35a6a08354290f805812bf34c`); it remains locked in `VERIFY_ONLY` with live execution blocked.
- Pull request #174 remains open and draft. CI workflows triggered by the registry commits were still queued/waiting at the last check; no passing result is claimed.

The registries contain metadata only. This is not evidence of installation, source-code execution, completed SBOM/scans, passing tests, independent approval, or runtime connectivity.


## Additional repository batch — 2026-10-23

Status: **REGISTERED FOR REVIEW — NO INSTALLATION OR RUNTIME CONNECTION**

The following 27 supplied URLs were checked for repository identity and default branch where available, then recorded in the canonical external repository registry. This batch adds 26 new records; `gessen/majutsu-delta` was already present and remains unpinned. Registry total after the update: 329 entries. Commit observations are not treated as verified default-branch HEAD pins until rechecked against the branch ref. Entries marked `UNPINNED_BLOCKED` must not be installed or executed.

| Repository | Default branch | Recorded commit / pin status | Classification |
|---|---|---|---|
| https://github.com/vinta/awesome-python | master | `8c385dcab9b1a7b6029a6ecb7c5b1f52597fd418` — observed commit, HEAD recheck required | REFERENCE_ONLY |
| https://github.com/jobbole/awesome-python-cn | master | UNPINNED — blocked | REFERENCE_ONLY |
| https://github.com/mahmoud/awesome-python-applications | master | `ee6ff705d902d4b59f3203c44015ec8e7c759c8a` — observed commit, HEAD recheck required | REFERENCE_ONLY |
| https://github.com/Shubhamsaboo/awesome-llm-apps | main | `6c16b23f1bacd0fdf240bb5141ef45e59e82c306` — observed commit, HEAD recheck required | REFERENCE_ONLY |
| https://github.com/521xueweihan/HelloGitHub | master | UNPINNED — blocked | REFERENCE_ONLY |
| https://github.com/lukasmasuch/best-of-ml-python | main | UNPINNED — blocked | REFERENCE_ONLY |
| https://github.com/DjangoEx/awesome-python-resources | main | UNPINNED — blocked | REFERENCE_ONLY |
| https://github.com/uhub/awesome-python | master | UNPINNED — blocked | REFERENCE_ONLY |
| https://github.com/duckdb/duckdb | main | `1641475ef1db08ec063631ff6a8f08d9d6736ae7` — observed commit, HEAD recheck required | TOOLCHAIN_ONLY |
| https://github.com/gessen/majutsu-delta | master | UNPINNED — blocked; repository README lookup returned 404 | REFERENCE_ONLY |
| https://github.com/duckdb/duckdb-web | main | `5d13ec7734088f793b3547f852a8eb0878fa4ceb` — observed commit, HEAD recheck required | REFERENCE_ONLY |
| https://github.com/duckdb/duckdb-ui | main | UNPINNED — blocked | TOOLCHAIN_ONLY |
| https://github.com/duckdb/duckdb-httpfs | main | `77392a72077a85897db2519fae11e2c0da972b8a` — observed commit, HEAD recheck required | TOOLCHAIN_ONLY |
| https://github.com/duckdb/duckdb-java | main | `679d526542cf9dfb24322d9d9c75641624f24bc1` — observed commit, HEAD recheck required | TOOLCHAIN_ONLY |
| https://github.com/duckdb/duckdb-rs | main | `4acbea84794582c4cd962ee971a3d7a5dcb72e39` — observed commit, HEAD recheck required | TOOLCHAIN_ONLY |
| https://github.com/duckdb/duckdb-python | main | `4154efc6aa9114a04ee705e2182e044e13381fff` — observed commit, HEAD recheck required | TOOLCHAIN_ONLY |
| https://github.com/duckdb/dbt-duckdb | master | `a993eaee5674de1acc2226279739842012f929e3` — observed commit, HEAD recheck required | TOOLCHAIN_ONLY |
| https://github.com/duckdb/duckdb-postgres | main | `487235919b12b66cc6fdbf2ec1511273aac168d0` — observed commit, HEAD recheck required | TOOLCHAIN_ONLY |
| https://github.com/duckdb/pg_duckdb | main | UNPINNED — blocked | TOOLCHAIN_ONLY |
| https://github.com/duckdb/duckdb-wasm | main | `1f85a503e0c25f0c0980f205915de328c923f476` — observed commit, HEAD recheck required | TOOLCHAIN_ONLY |
| https://github.com/davidgasquez/awesome-duckdb | main | `2fe7c07d3e6f1fdb02f3bba703f0d5f5037f93b0` — observed commit, HEAD recheck required | REFERENCE_ONLY |
| https://github.com/rustyorg/rustygit | main | UNPINNED — blocked | TOOLCHAIN_ONLY |
| https://github.com/dandavison/magit-delta | master | UNPINNED — blocked | TOOLCHAIN_ONLY |
| https://github.com/dandavison/dandavison.github.io | master | UNPINNED — blocked | REFERENCE_ONLY |
| https://github.com/openai/php2shell-checker | main | `ffcd3fc82e5b404f2a04a95b2805ca7639d530fa` — observed commit, HEAD recheck required | REFERENCE_ONLY |
| https://github.com/9bie/php2shell-bypass-aslr-exp | main | `80eae705288de858d73f075795dc7e1b0fdb7479` — observed commit, HEAD recheck required | REFERENCE_ONLY |
| https://github.com/omnigent-ai/omnigent | main | `464fba3e9520516838f0e184a56bb7dc8d379169` — observed commit, HEAD recheck required | SANDBOX_ONLY |

### Batch-specific security decisions

- **Awesome lists and catalogues:** discovery/reference material only. A listing is not a security endorsement; review each linked package separately before adding dependencies or agent skills.
- **DuckDB core and integrations:** toolchain evaluation only. Before use, pin mutually compatible engine/client/extension versions, produce an SBOM, scan dependencies, and test with synthetic data. Specifically review remote-file access and outbound network behavior in `duckdb-httpfs`; review extension permissions, SQL semantics and database isolation for Postgres integrations; review build scripts and native dependencies for language clients. No database migration or production connection is authorized by these registry entries.
- **Git tooling:** `rustygit`, `magit-delta` and `majutsu-delta` remain blocked from execution until exact commits and licenses are confirmed.
- **PHP2Shell checker:** defensive version-warning utility only. It checks advertised HTTP headers and may send HEAD/GET requests; this is not proof that a server is patched. Only check systems with authorization.
- **PHP2Shell ASLR bypass:** the README explicitly describes remote code execution against a PHP/Apache target. This source is retained as defensive threat-intelligence reference only. Do not execute it, test it against any target, deploy it, or wire it into AURELIA, CI, or any agent workflow.
- **Omnigent:** alpha multi-agent meta-harness. Sandbox-only, no broker session, production secrets, home-directory mounts, or capital-plane access.

### Verification and readiness

- Canonical external repository registry update: commit `614ecf4729f853a0522d86327b43b59b08bf6161`.
- Canonical agent/tool assignment metadata update: commit `ee351d782530978dbfd52d10dd054120db4aa7f4`.
- Registry JSON parsing succeeded after the writes. Four entries from the prior batch plus this batch remain metadata-only; all new records deny capital authority, live-order submission, broker transaction writes, secret reading and live-lock mutation.
- Exact default-branch HEAD verification for all observed commits: **PENDING**. Eleven repositories previously lacking a recorded revision now have immutable commit IDs recorded from GitHub recent-commit search results. These IDs are not verified as default-branch HEADs; build/install remains blocked until the exact intended branch/ref is independently confirmed.
- SBOM, dependency/secret scans, isolated smoke tests and independent review: **NOT RUN / PENDING**.
- Installation, code execution and runtime connection: **NOT PERFORMED**.

The AURELIA `config/LIVE_LOCK.yaml` must remain unchanged and VERIFY_ONLY. This intake is not an installation or release approval.


### Revision-pin follow-up

- Registry follow-up commit: `bbe0deb9eaf0a866f90f8fc1c0d394988f21b612`.
- The 11 formerly unpinned records now have immutable revision IDs from recent-commit search results. Some are old; for example, `jobbole/awesome-python-cn` has a 2021 commit and the Git tooling repositories include commits from 2022. This is sufficient to identify a reproducible historical snapshot, but not to certify currentness or compatibility.
- The source default-branch refs were not independently resolved to those exact SHAs. All 11 therefore remain blocked from installation/build pending default-branch ref verification and source/license review.


## Cloudflare and crypto-arbitrage intake — 2026-10-23

### Intake summary

- Repositories submitted: 19.
- New registry records: 18; `manu354/cryptocurrency-arbitrage` was already registered and has been refreshed with an observed immutable revision.
- Registry size after update: 347 records.
- Registry commit: `5c1c124ce14b45339c6c84cd4f76ddd229f5f4bd`.
- Assignment-ledger commit: `763dec2e54eae930941cbdf6b94b2dae23e70db2`.
- Every newly observed SHA below comes from GitHub recent-commit search. It is an immutable revision identifier, **not a verified default-branch HEAD**. Installation/build remains blocked pending explicit ref verification, license review and security qualification.

### Per-repository triage

| Repository | Observed revision | Disposition | Main review concern |
|---|---|---|---|
| `manu354/cryptocurrency-arbitrage` | `853d1d0d026997ace7c380aba350978c064a6519` | REFERENCE_ONLY | Legacy price-comparison app; upstream README says active trading-bot code is private. No order execution or capital authority. |
| `cloudflare/cloudflare-os` | `03cf8766ecebd6e6b59b7bdd1902eeefc45643eb` | SANDBOX_ONLY | Application provenance, permissions and dependency review. |
| `caddy-dns/cloudflare` | `a8737d095ad5a48ca031cea6ab704057dbc2d250` | TOOLCHAIN_ONLY | DNS/ACME provider can mutate records; least-privilege token and dependency review required. |
| `zhuima/awesome-cloudflare` | `4d90410f80178f4c41655c1252a7d5b653e8e8bd` | REFERENCE_ONLY | Catalogue is not an endorsement; review each linked project separately. |
| `MarSeventh/CloudFlare-ImgBed` | `fbd4785d1a577c85da824eef232b36b11a2180eb` | SANDBOX_ONLY | Upload validation, access control, storage exposure, XSS, Sentry and secret handling. |
| `cloudflare/cloudflared` | `8cc81c7fcc524a2b1ebec51506685180652ea25d` | TOOLCHAIN_ONLY | Tunnel client can create network ingress/egress paths; no tunnels into AURELIA, no production service exposure. |
| `dreamhunter2333/cloudflare_temp_email` | `8bdd353efcdd65559fb5c0ea6f036a69541595d5` | SANDBOX_ONLY | Email/attachment privacy, tenant isolation, SMTP/IMAP exposure, XSS and retention controls. |
| `yonggekkk/Cloudflare-vless-trojan` | `4a61f9c4e2b96b0ee05519570cf92ff29a6d1b22` | REFERENCE_ONLY | Do not deploy proxy/tunnel configuration or connect it to production agents. |
| `cloudflare/cloudflare-docs` | `06eb1cd432068d63617dbaa973682e1ccda46dbc` | REFERENCE_ONLY | Documentation reference only; not executable authority. |
| `XIU2/CloudflareSpeedTest` | `50b42c7f95cfb06413740ce6e1967578ebe63380` | SANDBOX_ONLY | Network probes only against authorized endpoints; no automatic route changes. |
| `sarperavci/CloudflareBypassForScraping` | `97e4d9777c7d12f9449b9581383858ec06fcbaee` | REFERENCE_ONLY | Do not use to bypass access controls or scrape protected targets; authorized defensive research only. |
| `gslege/CloudflareIP` | `597aea7ae4dfd4e971846a7664b1884f164f3355` | REFERENCE_ONLY | Auto-updated IP lists are untrusted indicators; verify provenance/freshness before firewall use. Never apply automatically. |
| `cloudflare/cloudflare-go` | `91580cb481bde15bf5738770243f6b7f5908c8a9` | TOOLCHAIN_ONLY | API SDK permissions depend on token; least-privilege test credentials only, no production writes. |
| `maillab/cloud-mail` | `c0009ddae326197e22c44986b6537ca7d97e803a` | SANDBOX_ONLY | RBAC, tenant isolation, mail abuse, attachment access and secret handling. |
| `timothymiller/cloudflare-ddns` | `545f49d016fdd21f9d5e63f29b5756ed40c4ea24` | TOOLCHAIN_ONLY | DNS mutation capability; dry-run only, no production token or DNS writes. |
| `cloudflare/mcp-server-cloudflare` | `a21972e219289337731a066befb5c66886b9ce7b` | SANDBOX_ONLY | Privileged agent surface; audit tool inventory, OAuth scopes, prompt-injection/exfiltration paths; no production credentials or write scopes. |
| `cloudflare/terraform-provider-cloudflare` | `9b51a582458f5c5d46d8547ed2604fcba91fb861` | TOOLCHAIN_ONLY | Plan/validate only; no `terraform apply` or destroy without separately approved infrastructure change. |
| `Jazee6/cloudflare-ai-web` | `50d49147225010eff862053604c453d34910bd5b` | SANDBOX_ONLY | Auth, API routes, model access, prompt injection, rate limiting and secrets. |
| `supermemoryai/cloudflare-saas-stack` | `600a5b385e30e8a387dce6d0d782b5a6283db872` | SANDBOX_ONLY | Historical revision; current maintenance, dependencies, tenant isolation and secrets need review. |

### Required controls and gates

- External code execution remains deny-by-default. No repository was installed, built, executed, deployed, or connected to an agent runtime in this intake.
- DNS, Terraform, Cloudflare API SDK and MCP server privileges must remain unavailable to production AURELIA agents. No API token was requested or stored.
- No Cloudflare tunnel, DNS record, firewall list, email service, storage bucket, or infrastructure resource was changed.
- SBOM, dependency/secret scans, isolated smoke tests, default-branch HEAD verification, independent review and canonical CI: **NOT RUN / PENDING**.
- `config/LIVE_LOCK.yaml` must remain unchanged; AURELIA remains VERIFY_ONLY and LIVE_EXECUTION BLOCKED.
