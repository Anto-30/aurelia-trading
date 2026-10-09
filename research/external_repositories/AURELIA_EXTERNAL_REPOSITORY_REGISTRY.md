# AURELIA External Repository Registry

This registry pins external repositories requested for AURELIA intelligence and engineering synchronization. It is deliberately not a dependency lockfile: external source is reviewed before any runtime adoption.

## Authority boundary

External repositories may inform research, engineering, QA, security, UI, and operational tooling. They cannot:

- acquire capital authority;
- submit or modify broker orders;
- read production secrets;
- mutate LIVE_LOCK or FINAL_EXECUTION_AUTHORIZATION;
- bypass Balance Truth, Risk Warden, Execution Firewall, reconciliation, or release gates;
- convert external strategy signals into live trades.

## Pinned sources

### ajaxorg/ace
- Pin: `62d5ffd789b4eb29ef7c1acc17554c91c745a307`
- Role: Command Center UI / Engineering
- Status: candidate
- Integration: research reference; use package-level Ace only if/when a browser editor is actually required
- Notes: Standalone embeddable JavaScript editor; BSD license. Do not vendor the full source tree into runtime.

### remorses/playwriter
- Pin: `525732a474a14224d46469c2b85737dbcdc23e07`
- Role: Browser Automation / Operations QA
- Status: candidate
- Integration: sandbox/ops tooling only
- Notes: Connects agents to a running browser and exposes Playwright-style automation. Never use it to bypass AURELIA auth, release gates, or broker controls.

### openinterpreter/openinterpreter
- Pin: `cc054cf52fa3585a3de50e0d4e0be6f9ee6677e8`
- Role: Engineering Agent / Research Orchestrator
- Status: candidate
- Integration: sandbox-only research and code-maintenance tooling
- Notes: Current repository is a large agent/coding monorepo. Do not grant shell execution or capital authority from it.

### morluto/rea
- Pin: `a45fe86a39b9e7a7c21e3665b6de4763cb72d782`
- Role: Security / Reverse Engineering
- Status: candidate
- Integration: sandbox-only investigation tooling
- Notes: Reverse-engineering MCP for binaries, applications and runtime behavior. Use for inspection, not production execution.

### hackingthemarkets/tradingview-binance-strategy-alert-webhook
- Pin: `ddb18c96416014067658557ff0d8df29213d6dcf`
- Role: Strategy Research / Webhook Pattern Research
- Status: research-only
- Integration: reference only
- Notes: TradingView-to-Binance alert webhook. Binance execution semantics must not be mapped directly into Deriv execution.

### jamesmawm/High-Frequency-Trading-Model-with-IB
- Pin: `8e96ade54a8e3eb94ead04827a846225ae122864`
- Role: Quant Research / Microstructure
- Status: research-only
- Integration: reference only
- Notes: Interactive Brokers HFT/pairs/mean-reversion example. Repository README explicitly warns components are outdated and likely not working as intended.

### blampe/IbPy
- Pin: `cba912d2ecc669b0bf2980357ea7942e49c0825e`
- Role: Quant Research / Legacy Broker Study
- Status: quarantine
- Integration: reference only; do not install
- Notes: Repository is archived and its README says it is superfluous for Python 3 because Interactive Brokers has an official Python API.

### nntaoli-project/goex
- Pin: `0a7d6619669ffc3164aa8fdceb545a64dc7f2cc4`
- Role: Crypto Exchange Abstraction Research
- Status: research-only
- Integration: reference only; no broker adapter import
- Notes: Go exchange wrapper currently documents OKX/Binance support. It is not a Deriv adapter and cannot authorize or submit AURELIA orders.

## Installation policy

The current AURELIA Python runtime contains only its required runtime dependency set. These repositories are therefore synchronized as pinned intelligence sources first, rather than being injected wholesale into the production runtime. This avoids dependency pollution, supply-chain drift, and accidental broker-authority inheritance.

A later runtime dependency may be admitted only through an explicit bounded adapter, tests, provenance pin, license/security review, and existing release gates.


### BerriAI/litellm
- Pin: `5e1c5c0bd17781a83b4368c38ebebcf7bc683fcb`
- Role: Multi-provider LLM gateway / orchestration infrastructure
- Mode: `SANDBOX_ONLY`
- Integration: architecture reference; no production runtime install in this sync
- Security: recent upstream advisories include critical/high issues. LiteLLM's March 2026 security notice documented compromised PyPI releases `1.82.7` and `1.82.8`; do not install those versions. Review current advisories and verify a pinned, signed release before any future adoption.
- Boundary: no access to Deriv credentials, no production secrets, no authority to change LIVE_LOCK or execute trades.

### LiteLLM-Labs/litellm-agent-control-plane
- Pin: `53bfd20e2fec51fc8f665fb614512c6b138367da`
- Role: Agent control-plane architecture
- Mode: `SANDBOX_ONLY`
- Integration: compare agent routing and provider-control patterns; cannot control AURELIA's deterministic capital plane.

### BerriAI/litellm-docs
- Pin: `4a73adff0a530b948b043b0fa64bf96d2cc7c4ce`
- Role: Official LiteLLM documentation
- Mode: `REFERENCE_ONLY`
- Integration: documentation/security-advisory lookup only.

### BerriAI/liteLLM-proxy
- Pin: `1ef69ae92bf22600f9a42d15e3b992e1010c9a7e`
- Role: Legacy proxy reference
- Mode: `REFERENCE_ONLY`
- Integration: older repository; not the preferred current upstream implementation.

### numman-ali/cc-mirror
- Pin: `e0e6f289c78ebe7f38bd8afcad92d28ea7e4f1e5`
- Role: Isolated Claude Code / custom-provider developer tooling
- Mode: `SANDBOX_ONLY`
- Integration: developer tooling research; never route production credentials through modified coding-agent binaries.

### BerriAI/litellm-pgvector
- Pin: `5bd8f3ab1fa9129e758a2c4b17ba1c6f3047ba24`
- Role: Vector-memory integration
- Mode: `SANDBOX_ONLY`
- Integration: retrieval architecture reference only; no production account data or secrets.

### LiteLLM-Labs/litellm-rust
- Pin: `76f83257fce4dcc3d76e7e760934bbd725b624d9`
- Role: Rust LLM gateway prototype
- Mode: `SANDBOX_ONLY`
- Integration: reference only pending benchmark and security review.

### langchain-ai/langchain-litellm
- Pin: `5b8af479f783ae5a0d3eff9214c2cbb06473e513`
- Role: LangChain provider adapter
- Mode: `SANDBOX_ONLY`
- Integration: adapter reference pending compatibility and transitive dependency review.

