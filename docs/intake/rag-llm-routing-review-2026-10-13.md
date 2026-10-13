# RAG / LLM repository intake review — 2026-10-13

## Status

- Intake manifest: `docs/intake/rag-llm-agent-repositories-2026-10-13.json`
- Upstream commit pins were queried from GitHub's latest-commit API on 2026-10-13 UTC.
- **All 34 sources remain unapproved.** Registration does not establish license clearance, security clearance, production suitability, or successful installation.
- No candidate source was cloned, installed, executed, vendored, or connected to a production credential.
- Canonical registry and routing configuration were not updated in this change because the write attempts were blocked. This document and manifest are supplemental evidence only.

## Suggested specialist routing

| Workstream | Primary | Supporting review | Initial mode |
|---|---|---|---|
| RAG evaluation and observability: `vibrantlabsai/ragas`, `raga-ai-hub/RagaAI-Catalyst`, `Marker-Inc-Korea/AutoRAG` | ClaudeCode | ChatGPT, JEV, GrokBot | RESEARCH_ONLY |
| Graph/document/code retrieval: `microsoft/graphrag`, `HKUDS/LightRAG`, `OSU-NLP-Group/HippoRAG`, `VectifyAI/PageIndex`, `vitali87/code-graph-rag` | ClaudeCode | ChatGPT, GLM, JEV | RESEARCH_ONLY |
| Application/API surfaces: `infiniflow/ragflow`, `LibreChat-AI/rag-api`, `rag-web-ui/rag-web-ui`, `ragapp/ragapp`, `OpenBMB/UltraRAG` | ClaudeCode | ChatGPT, JEV, GrokBot | SANDBOX_ONLY or RESEARCH_ONLY per manifest |
| Agent memory and agentic RAG: `nageoffer/ragent`, `mll-lab-nu/RAGEN`, `datawhalechina/hello-agents` | ClaudeCode | ChatGPT, JEV, GrokBot | SANDBOX_ONLY or REFERENCE_ONLY per manifest |
| Tutorials and curated indexes | ChatGPT | ClaudeCode, JEV | REFERENCE_ONLY |

This routing is a proposal; it has **not** been written to `config/repo_agent_routing.json`.

## Required checks before reuse

1. Verify repository license and licenses of bundled examples, models, datasets, and copied snippets.
2. Pin a specific commit and preserve source provenance; do not follow a moving default branch in build or runtime.
3. Run dependency and secret scans, static analysis, and targeted tests in an isolated, credential-free environment.
4. Test prompt injection, retrieval poisoning, document parser exploits, SSRF/egress, access-control boundaries, tenant isolation, and secret leakage where applicable.
5. Evaluate retrieval quality on fixed held-out corpora with reproducible metrics; prevent test-set leakage and record model, embedding, chunking, reranking, and index versions.
6. For observability/evaluation tools, inspect telemetry retention and external data egress. For memory systems, test poisoning and cross-session/cross-tenant retrieval.
7. Keep all RAG systems outside the trading capital plane. They must not change strategy eligibility, calibrated probability gates, stake sizing, LIVE_LOCK, release authority, broker account truth, or order submission.
8. Record findings and artifact hashes in the existing PR. A passing intake workflow is not a substitute for a full source review.

## Specific cautions

- `Azure-Samples/rag-postgres-openai-python`: latest upstream commit message reports a SQL-injection fix. Verify the actual patch and add regression tests; the commit message alone is not proof of remediation.
- `souravkl11/raganork`: latest upstream commit message marks the project archived/deprecated; reference-only.
- `str4d/rage`: name is ambiguous and does not establish that it is a RAG project; reference-only until a concrete use case is verified.
- `ragapp/ragapp`: latest commit pin is older than most of the batch; check maintenance and dependency state before further consideration.
- Educational collections and awesome lists are indexes, not blanket license grants. Review each downstream project independently.

## Current PR gate state

PR #122 remains draft. The current-head Agent Federation Audit and Agent Continuity Watchdog passed. Repository Intake Supply-Chain Audit and AURELIA Assurance were pending at the time of this note:

- https://github.com/Anto-30/aurelia-trading/actions/runs/38437361047
- https://github.com/Anto-30/aurelia-trading/actions/runs/38437361185

Do not merge until required independent review and applicable gates are complete. Do not interpret this intake as evidence that AURELIA is qualified for live trading.
