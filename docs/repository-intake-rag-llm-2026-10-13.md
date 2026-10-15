# RAG and LLM Repository Intake — 2026-10-13

## Scope and admission state

This batch contains 34 distinct GitHub repositories. Default-branch tip SHAs were read from GitHub's commits API on 2026-10-13 UTC and are recorded in `config/external_repo_federation.json`. Pins are inspection identifiers, not approval.

**All 34 entries remain unapproved.** RAG engines and services are `SANDBOX_ONLY`; research frameworks are `RESEARCH_ONLY` or `SANDBOX_ONLY`; tutorials and curated lists are `REFERENCE_ONLY`. Every entry has `physical_runtime_install=NOT_CLAIMED` and `security_review_status=PENDING`. No candidate may read production secrets, submit broker transactions, alter `LIVE_LOCK`, change capital/execution code, deploy to production, or authorize release.

The 34 sources were registered and role-routed in the existing AURELIA branch. This does **not** mean that source archives were downloaded, cloned, installed, executed, or fully audited.

## Inventory and first-pass disposition

| Repository | Pinned default-branch tip | Category / disposition |
|---|---|---|
| `infiniflow/ragflow` | `d2ede485bfe87dc42b6c23598a2e36ab8f964030` | RAG engine; sandbox-only. Inspect ingestion/parser isolation, API auth, tenant boundaries, SSRF, plugins and resource caps. |
| `raga-ai-hub/RagaAI-Catalyst` | `ab67893310891140211280a496402003e52cdab5` | Agent/LLM observability; sandbox-only. Review telemetry redaction, retention and outbound data paths. |
| `HKUDS/RAG-Anything` | `da6e2d87a7d3f2746c4541f59953b8764213f6a2` | Multimodal RAG; sandbox-only. Review file parsers, prompt injection and data exfiltration boundaries. |
| `HKUDS/LightRAG` | `4d0afc1bc36e6a34d4a5895b68efe9413748627a` | Graph RAG; research-only. Benchmark provenance, consistency and poisoning resistance. |
| `NirDiamant/RAG_Techniques` | `cbf9e528206bbb5cd23970ff612d12c1074e02dc` | Tutorial/reference; selectively reuse reviewed examples only. |
| `souravkl11/raganork` | `4161bec86639ae8234d81ed8fd7f7dcf4099e2e2` | Deprecated/archive-labeled project; reference-only, no deployment. |
| `datawhalechina/all-in-rag` | `cec956e80ae28d6c0ca84c9d39dddcf61ad633fd` | Curated learning reference; linked projects need separate review. |
| `vibrantlabsai/ragas` | `298b68274234c060deacab3cf5fb52aa3a20e885` | RAG evaluation; priority candidate for faithfulness, relevance and context precision/recall; calibrate judge bias. |
| `bragai/bRAG-langchain` | `33aca8325f728ab3e96988add9f8bdd2987dadc6` | Agentic RAG framework; sandbox-only, review tool routing and prompt injection. |
| `GiovanniPasq/agentic-rag-for-dummies` | `f0d9a3c89adc7ebd146ffe173057fe013dd41739` | Educational agentic RAG; reference-only, inspect workflow/dependency changes. |
| `str4d/rage` | `b5b68c4f4f7ea5c368bc060f6fe0237549c3a13f` | Name collision/out-of-scope encryption utility; reference-only unless a concrete need emerges. |
| `Azure-Samples/rag-postgres-openai-python` | `2c23c488bb8698159739b0a01c22396b788f7de6` | PostgreSQL RAG sample; sandbox-only. Latest commit says SQL injection in search filters was fixed; independently review the patch and regression tests. |
| `Andrew-Jang/RAGHub` | `bd7f46a3cb47ea78ba5044b74cf166f9c5b9fef9` | RAG app framework; sandbox-only, review upload/parser and tenant boundaries. |
| `LibreChat-AI/rag-api` | `c4e5cbf79fcece1df9adfff5dfed983a5990ca9f` | RAG API service; sandbox-only, review auth, ingestion, SSRF and tenant isolation. |
| `rag-web-ui/rag-web-ui` | `905fb04669ae6f2a0cb3690d82a547b860e80dd4` | Web UI; sandbox-only, review auth, upload limits and backend endpoint configuration. |
| `datawhalechina/hello-agents` | `930c0b2bc80880c24ad0eca17de23fe9680c8a5f` | Agent learning reference; examples only. |
| `mll-lab-nu/RAGEN` | `d97bb3284e99568adfd44ee15c736d7685c07512` | Agentic RAG research; establish scope and reproducible baseline. |
| `RUC-NLPIR/FlashRAG` | `f7be4d976b10e2d590451533486c03761c29f6b9` | RAG research/benchmark framework; check dataset licensing and evaluation leakage. |
| `datawhalechina/happy-llm` | `1e0b3a1e6f8936b8ba4bbd0673e8e2227d196c96` | LLM learning reference; educational only. |
| `patchy631/ai-engineering-hub` | `be534adc47ae3357253025d6e0ab769b465086d7` | Curated engineering examples; each subproject is a separate trust/license boundary. |
| `datawhalechina/llm-universe` | `77beb748047e8a0d8ff708716606a8e0b132dc45` | LLM learning reference; educational only. |
| `OSU-NLP-Group/HippoRAG` | `d5c8329422e0a0b834a15874545cb6a74b4f9b26` | Graph retrieval research; review MCP/plugin surface and poisoning resistance. |
| `honeyandme/RAGQnASystem` | `6d91e2ec76f70dd604b8a897a63b2ac6fba3ec95` | RAG Q&A system; sandbox-only, verify maintenance and dependencies. |
| `langchain-ai/rag-from-scratch` | `1fdb7d0e4f1d3e731c8397332452715512f18667` | Foundational tutorial; reference-only. |
| `nageoffer/ragent` | `34b438d3f2ef356ad49a28becb058b1d69985fae` | Agent/memory framework; inspect memory arbitration, persistence and tool execution. |
| `VectifyAI/PageIndex` | `af92d9658a6a9c0ae31171b43198db28951af2f4` | Hierarchical document indexing; benchmark citations and indexing cost against alternatives. |
| `Marker-Inc-Korea/AutoRAG` | `5dd4066340e8f3cc1c8024d5af04062b9e46f717` | RAG evaluation/optimization; review split isolation and artifact/runtime handling. |
| `OpenBMB/UltraRAG` | `185e2032d9f134099405b8b483edbbad95274080` | RAG workflow framework; inspect frontend dependencies and orchestration surfaces. |
| `microsoft/graphrag` | `5faaaf4f5685fa2056fa8c3bf9342cb089f2942f` | Graph RAG; measure extraction error, provenance, updates and cost. |
| `vitali87/code-graph-rag` | `fb6799e94d99da674d8525b21e2b0f298731f1be` | Code graph RAG; treat indexed code as untrusted instructions and restrict filesystem/model access. |
| `ragapp/ragapp` | `f7f88892a92c110853dfa019f2c4a605a4a7b6f5` | RAG application; last observed commit is from 2024, so maintenance/compatibility require extra scrutiny. |
| `StarTrail-org/PixelRAG` | `b4fe76301465eaee3d8ac75e0bec54664e53c072` | Multimodal RAG; review parsers, dataset rights and reproducibility. |
| `souravkl11/raganork-md` | `82816b1e1fc5e8c9740f4f37872fe2656fc01251` | Likely messaging-bot/name collision rather than RAG; reference-only pending purpose confirmation. |
| `Shubhamsaboo/awesome-llm-apps` | `4bf51ab704fb2c5b3803cd5191b30d7dcdb51dc2` | Curated LLM app list; individual linked apps are not pre-vetted. |

## Agent routing

- **Claude Code**: implementation feasibility, isolated prototypes, tests, and code-level security review.
- **ChatGPT**: architecture, source triage, evidence lineage, registry and assurance review.
- **JEV**: deterministic evaluation harnesses, dataset split checks, regression tests, and acceptance evidence.
- **Grok**: adversarial challenge, prompt-injection scenarios, external-context critique, and independent review support.

Routing entries are logical assignments only. They do not activate agents or connect plugins/workspaces.

## Required next gates

1. Extend supply-chain scanning to this 34-source batch using a bounded method. The current 30-source audit does **not** cover these new pins; do not count its results as evidence for them.
2. Avoid increasing archive limits blindly. Large repositories should receive a bounded Git-tree/manifest/license inventory first; full dependency scanning can then be scoped to relevant lockfiles and package roots.
3. Produce per-source manifest/lockfile inventories, SBOMs where feasible, OSV results, secret scans, license/NOTICE review, and pinned-source spot checks for authentication, uploads/parsers, SSRF, prompt injection, telemetry and tool execution.
4. Build a small, fixed evaluation corpus with provenance and held-out questions. Measure retrieval recall/precision, answer faithfulness, citation correctness, injection resilience, latency, cost and failure handling. Keep evaluation data and any indexed private data outside broker/capital systems.
5. Preserve the research/capital boundary. No live trading or production readiness follows from RAG evaluation success.

## Not claimed

No source was installed, cloned into agent workspaces, executed, or merged into runtime paths by this registry change. No production secrets, broker permissions, capital/execution code, `LIVE_LOCK.yaml`, or release authorization was changed. Independent human review and supply-chain clearance remain outstanding.
