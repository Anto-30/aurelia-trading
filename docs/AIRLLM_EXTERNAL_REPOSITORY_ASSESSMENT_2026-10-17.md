# AirLLM Repository Assessment for AURELIA Agent Infrastructure
**Review date:** 2026-10-17  
**Disposition:** RESEARCH-ONLY candidate; not approved for production use  
**Repository:** https://github.com/lyogavin/airllm  
**Inspected default-branch HEAD:** `fd3bd7ef404f55961555f3f63651b5f9e33cf8bc`  
**Repository-reported license:** Apache-2.0  
**Release observed:** `v4.0.0`, published 2026-09-05

## Executive decision

AirLLM is a memory-frugal, disk-streamed LLM inference/training library. It is potentially relevant to an isolated agent-inference experiment when a suitable Linux/GPU host exists. It is **not** a trading strategy, market-data feed, broker adapter, task supervisor, or capital-risk engine.

Do not install it on the user's Android phone, add it to AURELIA's production dependency set, or use it to replace the existing multi-provider agent architecture now. Do not grant it broker credentials, network access to trading endpoints, write access to AURELIA's repository, or any capital-plane authority.

This assessment is based on GitHub repository metadata and selected source/README/setup/workflow files. The source was not cloned or executed here; no full SBOM, vulnerability/secret scan, GPU benchmark, or reproducible build is claimed.

## What was verified

- GitHub metadata identifies `lyogavin/airllm` as a public, non-archived Python repository. The default-branch HEAD at review was `fd3bd7ef404f55961555f3f63651b5f9e33cf8bc`; its latest commit is an unsigned automated star-history refresh. The SHA is a pin for review, not a trust certification.
- The repository describes layer-by-layer checkpoint streaming from disk to accelerator and exposes an `AutoModel.from_pretrained` interface.
- `air_llm/setup.py` declares AirLLM version 4.0.0 and dependencies including `torch>=2.4`, `transformers>=4.49,<6`, `accelerate>=1.0`, `safetensors`, `huggingface-hub`, `scipy`, and `sentencepiece`. Optional features add more dependencies.
- `air_llm/airllm/auto_model.py` calls Hugging Face `AutoConfig.from_pretrained(..., trust_remote_code=True)`. This can execute Python supplied by a model repository. Treat model repositories, custom code, tokenizer/config files, and checkpoint artifacts as separate untrusted supply-chain inputs.
- The README/release notes describe very large checkpoints. At least one current model path calls for roughly 360 GB of disk and a 64 GB host-RAM class machine; the low-VRAM claim does **not** mean low total memory, low disk, low latency, or free hosting. These numbers are model-specific, not universal requirements.
- The repo has a release workflow that builds an sdist/wheel and checks metadata before publishing via PyPI Trusted Publishing. This workflow's existence is not proof that the exact reviewed source was built/tested in this session.
- The current README says the code is Apache-2.0, and GitHub metadata reports Apache-2.0. Model weights and upstream model-specific code may have their own licenses and terms; review them separately.
- No `SECURITY.md` was found at the repository root during this check. That is a missing signal, not proof that the project has no security process.

## Risks and constraints

1. **Remote-code execution:** `trust_remote_code=True` is the primary security concern. Do not load arbitrary public models in a process that can access secrets, writable project files, SSH credentials, or unrestricted network access.
2. **Supply chain:** the README references moving Git branches for some Transformers/model support. Pin exact package versions and source commits; never rely on an unpinned `git+https` dependency in a reproducible deployment.
3. **Resource exhaustion:** checkpoint downloads, shard conversion, mmap, disk caches, CPU RAM, GPU VRAM, and prefetch workers can consume substantial storage/memory and time. Require disk quotas, memory limits, timeouts, and cache cleanup.
4. **Data governance:** model inputs/outputs can contain proprietary research. Keep any AURELIA strategy data out of hosted third-party inference unless the data handling terms and network boundaries are explicitly approved.
5. **Performance/quality:** smaller VRAM does not establish throughput, tail latency, output quality, calibration, or cost efficiency. Agent quality must be evaluated against current providers on a fixed task set.
6. **Model license is distinct:** Apache licensing for AirLLM code does not grant permission to use every model, weight set, dataset, or remote-code dependency.
7. **No security clearance:** no isolated execution, malware scan, SBOM, dependency audit, secret scan, benchmark, or independent code review was run in this session.

## Agent assignment

| Agent | Assignment for this candidate | Required output |
|---|---|---|
| **ClaudeCode** | If a safe runner becomes available, prototype an optional provider adapter behind a feature flag; pin AirLLM and dependencies; do not modify the capital plane. | Reproducible lockfile, minimal isolated adapter, install/build report, rollback path, no production dependency changes. |
| **GoogleAgentSkills** | Threat-model model-loading and remote-code execution; define sandbox, filesystem, network-egress, and resource boundaries. | Threat model, permission matrix, safe execution profile, explicit deny-list. |
| **KimiK3** | Design a fair local-vs-current-provider benchmark with fixed prompts/tasks, repeatability, quality scoring, and leakage checks. | Benchmark protocol and acceptance thresholds before any performance claims. |
| **JEV** | Independently review exact source pin, dependency lock, test outputs, sandbox profile, and benchmark reproducibility. | Separate pass/fail report on the exact commit; author cannot self-approve. |
| **GLM** | Validate evidence bundle, input hashes, model revision, package versions, hardware profile, and output artifacts. | Machine-readable evidence manifest; missing artifacts remain UNKNOWN. |
| **GrokBot** | Track the experiment as a non-blocking research task; report owner, dependencies, blockers, and results. | Status summary only; no automatic install or promotion. |
| **ChatGPT** | Maintain architecture fit, compare results against alternatives, and document limitations. | Decision memo grounded in artifacts, not marketing claims. |
| **PlaywrightCLI** | No direct role in model inference; optionally test an operator-facing provider selector using mocked responses only. | UI tests that confirm status is not presented as production readiness. |
| **Dev** | Own isolated host provisioning only after an authorized persistent Linux/GPU host is available and owner-approved. No paid resources without explicit approval. | Host isolation, resource quota, restart/cleanup and telemetry evidence. |
| **AURELIA risk/release plane** | No integration work required. Enforce that this candidate cannot authorize trades, change risk settings, or write broker transactions. | Existing fail-closed policy remains unchanged. |

## Safe proof-of-concept acceptance criteria

All must pass before considering a bounded trial:
- Immutable source commit and exact wheel/package hashes recorded.
- License/NOTICE review for AirLLM, every dependency, and the selected model/weights/custom code.
- Clean isolated build; SBOM, vulnerability report, secret scan, malware scan where available, and install/build-script review retained.
- Model loading with `trust_remote_code` disabled wherever possible. If a model requires remote code, it must run in a disposable, non-privileged sandbox with no secrets, read-only source, strict egress allowlist, quotas, and an explicit model-revision pin.
- No production broker credentials, account sessions, deployment tokens, or writable canonical repository mount in the inference environment.
- Fixed benchmark against the existing agent provider(s), including task correctness, hallucination/unsupported-claim rate, reproducibility, first-token/total latency, throughput, peak RAM/VRAM, disk consumption, failure recovery, and cost.
- Independent JEV review and documented owner approval.
- Explicit feature flag and rollback; default off. No influence on live authorization or risk policy.

## Integration decision

**Keep as `RESEARCH_ONLY`** in the external-source intake process. Do not promote to `TOOLCHAIN_ONLY` or production until the above criteria are evidenced. Given the current lack of a verified persistent authorized Linux/GPU host, the immediate action is source-level documentation only; no install or resource creation is justified.

## Sources
- Repository: https://github.com/lyogavin/airllm
- Reviewed source pin: https://github.com/lyogavin/airllm/commit/fd3bd7ef404f55961555f3f63651b5f9e33cf8bc
- README: https://github.com/lyogavin/airllm/blob/main/README.md
- Package metadata: https://github.com/lyogavin/airllm/blob/main/air_llm/setup.py
- Model loader: https://github.com/lyogavin/airllm/blob/main/air_llm/airllm/auto_model.py
- Release workflow: https://github.com/lyogavin/airllm/blob/main/.github/workflows/release.yml
- Latest release: https://github.com/lyogavin/airllm/releases/tag/v4.0.0
