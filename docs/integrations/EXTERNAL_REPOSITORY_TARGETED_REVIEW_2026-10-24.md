# Targeted Source Review Notes — 2026-10-24

This is a targeted read-only inspection of selected files at the exact commit pins recorded in `EXTERNAL_REPOSITORY_SOURCE_EVIDENCE_2026-10-24.md`. It is not a complete security audit. No source was executed and no repository was cloned.

## Findings from selected source files

### Open Interpreter

At inspected commit `ac1fcc8fe57aba51fcc3c79afd57a0883237fe87`, GitHub search surfaced the project's approval policy templates and shell escalation code, including an explicit unsandboxed escalation path. This confirms that the product's security boundary depends on its sandbox and approval configuration, not merely on being an agent harness.

- Candidate use: isolated developer tooling only.
- Required checks: default sandbox policy, escalation UI and API, command approval, filesystem mounts, network policy, environment-variable inheritance, MCP tool permissions, and audit logging.
- Do not run its remote shell installer as part of the audit. Review its exact script/release provenance before any user-side installation.

Source references:
- [Approval policy template](https://github.com/openinterpreter/openinterpreter/blob/ac1fcc8fe57aba51fcc3c79afd57a0883237fe87/codex-rs/prompts/templates/permissions/approval_policy/on_request.md)
- [Shell escalation protocol](https://github.com/openinterpreter/openinterpreter/blob/ac1fcc8fe57aba51fcc3c79afd57a0883237fe87/codex-rs/shell-escalation/src/unix/escalate_protocol.rs)

### Pi Kimi Code provider

At inspected commit `54dbd3e11ac3a441f10b6f6460d355342d4c651c`, `src/oauth.ts` includes code that reads/writes Pi's `auth.json` and the Kimi Code OAuth file under the configured Kimi home directory, uses file locks around token refresh, and attempts to restrict credential file permissions to owner-only. The code also supports synchronization between credential stores.

This is a real credential-handling component. File mode and locking are useful controls, but do not by themselves prove secure token lifecycle, OS backup protection, safe multi-user operation, or absence of credential leakage elsewhere.

- Candidate use: optional provider adapter only after an isolated review.
- Never copy a personal OAuth file to CI, AURELIA, a shared host, a repository, or logs.
- Use a disposable account/session, confirm exact home paths and region, verify token refresh/revocation behavior, and keep Moonshot server-side tools disabled until explicitly approved.

Source reference:
- [OAuth implementation at inspected commit](https://github.com/Leechael/pi-provider-kimi-code/blob/54dbd3e11ac3a441f10b6f6460d355342d4c651c/src/oauth.ts)

### DeepSeek Harness free-model plugin

At inspected commit `f3ecb7abcf5a0351645cfcbd638b9c7fbbcb3e97`, the English README says the plugin uses public OpenCode Zen and Kilo AI gateways and contacts them directly. The README also describes model-list refreshes, availability probing, in-app downloads/updates, hot reload, and an optional local OpenAI-compatible forwarding port.

These are important trust boundaries even though the plugin reports zero dependencies. Public gateways are external data processors; zero package dependencies does not mean zero network risk.

- **Disposition: quarantine; no sensitive prompt or code traffic.**
- Before any trial, inspect the full endpoint-selection and request code, announcement feed and HTML allowlist, update signature/hash validation, local forwarding-port authentication/bind address, background timers, data retention terms, and the gateway providers' own policies.
- If later tested, use a disposable profile, synthetic prompts, network allowlisting, and a loopback-only listener. Do not connect it to AURELIA's internal context.

Source reference:
- [English README at inspected commit](https://github.com/Ebony-Vinyl/dsh-our-free-model/blob/f3ecb7abcf5a0351645cfcbd638b9c7fbbcb3e97/README_EN.md)

### Deltafin

At inspected commit `aaad15d1faa77b317053a6c56077bb453a6da426`, `native/deltafin/src/setup_k3.rs` shows a native HTTPS metadata setup path. The visible code uses a staging directory, owner-only directory restriction, digest verification of expected metadata, validates model configuration/tokenizer/inventory, and atomically publishes the metadata directory. It explicitly reports that this metadata-only path does not download model weights.

This is positive evidence about the reviewed setup path, not a full safety verdict for the project. The complete download transport, URL derivation, model-weight installation path, update paths, server API, and all native dependencies still need review and tests.

- Do not run setup or download model weights in this intake.
- If selected for future testing, first inspect `trusted_download`, `k3_source`, the complete model-weight path, API bind/auth controls, and build dependencies; use a disposable directory and network allowlist.

Source reference:
- [K3 metadata setup implementation at inspected commit](https://github.com/gavamedia/deltafin/blob/aaad15d1faa77b317053a6c56077bb453a6da426/native/deltafin/src/setup_k3.rs)

## Audit status

| Control | Status |
|---|---|
| Selected README/LICENSE files retrieved and blob hashes recorded | Complete for the listed files |
| Targeted source inspection | Partial; the selected files above only |
| Full code audit / threat model | Not complete |
| Current default branch tips resolved and pinned | Not complete |
| Build scripts, workflows, transitive dependencies, submodules reviewed | Not complete |
| SBOM, SAST, secret scan, dependency and malware scan | Not run |
| Reproducible build/test and artifact verification | Not run |
| External services and data-processing terms verified | Not complete |
| Any installation or live runtime connection | Not performed |

## AURELIA decision

These repositories remain unapproved for production. No external agent, inference server, provider plugin, or model runtime may read broker credentials, mutate Layer 6 risk authority, access the execution adapter, change `config/LIVE_LOCK.yaml`, or submit trades. Preserve `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, and `capital_plane_mode=VERIFY_ONLY`.
