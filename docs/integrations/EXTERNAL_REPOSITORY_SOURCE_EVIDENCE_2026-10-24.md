# External Repository Source Evidence — 2026-10-24

This evidence record follows the preliminary intake document. It records repository content and commit objects fetched through GitHub's authenticated connector on 2026-10-24. A commit returned by a latest-commit search is a reproducible commit pin for inspection, but this record does **not** assert that every commit is the current default-branch tip. Blob hashes identify the exact README and LICENSE objects inspected.

## Exact inspected commit and document objects

| Repository | Commit pin returned by commit search | README blob SHA | LICENSE blob SHA | Source branch/path observed |
|---|---|---|---|---|
| [openinterpreter/openinterpreter](https://github.com/openinterpreter/openinterpreter) | [ac1fcc8fe57aba51fcc3c79afd57a0883237fe87](https://github.com/openinterpreter/openinterpreter/commit/ac1fcc8fe57aba51fcc3c79afd57a0883237fe87) | `6be2f5c02341f3284d97594800672e0d2551d0c2` | `4606e72e042564097e8780d66c1d4dcb611869bd` | main |
| [FareedKhan-dev/kimi-k3-in-c](https://github.com/FareedKhan-dev/kimi-k3-in-c) | [81bb6c23ccee2154bc35cad922588ab66494a9a9](https://github.com/FareedKhan-dev/kimi-k3-in-c/commit/81bb6c23ccee2154bc35cad922588ab66494a9a9) | `4286dfa7a57365cd9f6ea7895e189ace5ce4c591` | `d645695673349e3947e8e5ae42332d0ac3164cd7` | main |
| [gavamedia/deltafin](https://github.com/gavamedia/deltafin) | [aaad15d1faa77b317053a6c56077bb453a6da426](https://github.com/gavamedia/deltafin/commit/aaad15d1faa77b317053a6c56077bb453a6da426) | `2de9fc2cfd802d20453e8dc68193244186a63d20` | `9e3a562b0ad647996ddf327bfdd264ad91afe8a9` | main |
| [MoonshotAI/Kimi-K3](https://github.com/MoonshotAI/Kimi-K3) | [3cb39dfd32e51c3328e2e4b4af21341247d06c43](https://github.com/MoonshotAI/Kimi-K3/commit/3cb39dfd32e51c3328e2e4b4af21341247d06c43) | `21fe1f27c13dd41d8e45da6ea628e98abc105b60` | `0de9f0698195e20305982b95f47246bfd85602e5` | main |
| [sqliteai/warp](https://github.com/sqliteai/warp) | [09fcff352ca55223b08ee222d15054b90546c6a9](https://github.com/sqliteai/warp/commit/09fcff352ca55223b08ee222d15054b90546c6a9) | `7a70ac070a85c87f1bf345729c0cda20531e15ce` | `6d2d1fc078b860bf8e649ae59b49192f812470ae` | main |
| [baidu-baige/LoongForge](https://github.com/baidu-baige/LoongForge) | [a8268b7973e108fb61676a2cb967961dccb9851f](https://github.com/baidu-baige/LoongForge/commit/a8268b7973e108fb61676a2cb967961dccb9851f) | `ff749cb5fb7cc09582a1fbd8b9a950879e45144a` | `c41c1c4c741f3afb85deb75d6292fcd4fc6110fc` | master |
| [Leechael/pi-provider-kimi-code](https://github.com/Leechael/pi-provider-kimi-code) | [54dbd3e11ac3a441f10b6f6460d355342d4c651c](https://github.com/Leechael/pi-provider-kimi-code/commit/54dbd3e11ac3a441f10b6f6460d355342d4c651c) | `ee99356f966e2c03fdefe8acf0a3ff1e6cf9e0b9` | `b77bf2ab726c6e7cb5a81a9d3b7dc38266ebfd3d` | main |
| [Ebony-Vinyl/dsh-our-free-model](https://github.com/Ebony-Vinyl/dsh-our-free-model) | [f3ecb7abcf5a0351645cfcbd638b9c7fbbcb3e97](https://github.com/Ebony-Vinyl/dsh-our-free-model/commit/f3ecb7abcf5a0351645cfcbd638b9c7fbbcb3e97) | `5bc6c22158aaf65a5e2f1d619b628c85111816ed` | `0d5e2a61dc66dd531b7894bcd038599c5b723888` | main |

## Source-backed observations

- **Open Interpreter:** the current README advertises command execution, sandboxing, provider/harness switching, MCP, skills, hooks, permissions, and an install command that pipes a remote script into a shell. Do not execute that installation command as an audit step. Obtain a release artifact with verified provenance or review the exact script and its hash first. The project license is Apache-2.0.
- **kimi-k3-in-c:** the README makes very large-model inference and memory/performance claims. They remain upstream claims until reproduced on recorded hardware with pinned model artifacts, commands, and hashes. The source license is Apache-2.0; this does not automatically establish the separate model checkpoint's terms.
- **Deltafin:** the README describes a native local inference runtime and publishes performance claims; its LICENSE is MIT but explicitly identifies third-party components and states Kimi K3 code/model assets are governed by Moonshot AI's separate license. Audit the setup/downloader, native build chain, API bind address/authentication, and third-party notices before a test.
- **MoonshotAI/Kimi-K3:** the inspected license includes additional terms for certain large Model-as-a-Service businesses and certain very large commercial products. A license review must consider the actual deployment model and scale; do not assume a generic permissive OSS license applies.
- **WARP:** README describes a C inference engine with direct disk paging and very large model files. Apache-2.0 applies to the project code as stated in the repo; inspect NOTICE and bundled third-party directories before redistribution. No large model file was downloaded.
- **LoongForge:** README describes a training framework for LLM/VLM/diffusion/embodied models. Its stated Apache-2.0 project license and dependency notices still need an SBOM and license scan before reuse. This is not a runtime integration candidate by default.
- **Pi Kimi Code provider:** README describes sharing/synchronizing Kimi Code OAuth sessions and optional Moonshot server-side tools. This is a sensitive credential boundary. Do not sync a personal OAuth file into CI, a shared host, or AURELIA; use a disposable test session and inspect exact credential file paths, scopes, redaction, and tool opt-in behavior.
- **DSH Our Free Model:** the inspected README explicitly advertises use of third-party public gateways (including OpenCode Zen and Kilo AI) without user-supplied keys, and says model availability is checked through the user's network egress. That means prompts and code may be sent to those upstream operators. Do not send proprietary code, private prompts, trading data, or secrets through it until endpoint ownership, routing, retention, training use, terms, and security behavior are independently verified. The repository's MIT license does not confer rights over third-party gateway services or make them privacy-safe.

## What this evidence does and does not prove

**Proves:** GitHub returned the listed commit objects and README/LICENSE blobs; the links and hashes permit later retrieval and comparison; these source-level statements were visible in the inspected documents.

**Does not prove:** that the commit is the current branch tip; source code is secure; tests pass; binaries are reproducible; upstream benchmark claims are correct; all transitive licenses are compatible; model weights are safe; endpoints are trustworthy; or any software is installed, authenticated, connected, or running.

## Next required action

Use these pins as the starting points for a controlled audit. Resolve and verify the exact default-branch tip separately, inspect workflows and installation/update/download code, collect lockfiles and submodules, generate an SBOM, scan for secrets and suspicious network behavior, and run only isolated no-secret tests. Do not change AURELIA's runtime or capital-plane configuration from this evidence alone.

## AURELIA invariant

Preserve `config/LIVE_LOCK.yaml`: `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`, and `external_repositories_capital_forbidden=true`.
