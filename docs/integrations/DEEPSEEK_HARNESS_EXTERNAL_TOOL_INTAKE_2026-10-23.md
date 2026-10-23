# DeepSeekHarness external tool intake — 2026-10-23

Status: **PINNED FOR REVIEW — NOT INSTALLED OR CONNECTED**

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
| Registry integration | DOCUMENTED IN THIS INTAKE; canonical JSON registry update not confirmed |
| Dependencies installed | NO |
| SBOM / vulnerability scan | NOT RUN |
| Isolated smoke tests | NOT RUN |
| DeepSeekHarness runtime binding | NOT CONNECTED |
| Independent review | PENDING |
| Production/capital authority | DENIED |

The existing AURELIA live lock must remain unchanged. This document is not evidence of installation, execution, successful tests, or runtime connectivity.
