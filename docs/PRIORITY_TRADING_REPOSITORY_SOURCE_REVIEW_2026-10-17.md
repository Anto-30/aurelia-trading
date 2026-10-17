# Priority Trading Repository Source Review — 2026-10-17

**Purpose:** Focused review of source paths most relevant to trading, order placement, risk controls, broker authentication, tool permissions, and execution safety.

**Disposition:** No external repository is approved for direct AURELIA runtime, capital-plane, broker-authentication, or order-execution integration. These are source-level findings only; the repositories were not cloned, installed, built, executed, or subjected to a full isolated dependency/secret/malware audit in this review. Exact source pins below make follow-up reproducible.

## Executive findings

| Repository | Pinned upstream commit | License metadata | Main finding | AURELIA disposition |
|---|---|---|---|---|
| [FlintTrade](https://github.com/navaneeshnagarajan/FlintTrade/tree/a1f4adfc99e62d1f1a8ef6cb04e2dfef16993d9d) | `a1f4adfc99e62d1f1a8ef6cb04e2dfef16993d9d` | AGPL-3.0 | Source documentation describes layered order admission, safety checks, one-shot context gates and broker-router validation; this is not an independent verification of the implementation. Licensing also needs review before any reuse. | Sandbox/reference only; no code reuse without legal and technical review. |
| [OpenTrader](https://github.com/euriska/opentrader/tree/d430a4448ebd7002e77d3996e678cf752edecfdd) | `d430a4448ebd7002e77d3996e678cf752edecfdd` | Apache-2.0 | Shared risk helper explicitly fails open on missing/invalid data; all three risk limits default to zero/disabled. Compose also includes weak fallback secrets and publishes Grafana on host port 3000 with a fallback admin password. | Block deployment/adoption until fail-closed risk and infrastructure hardening are demonstrated; sandbox only. |
| [OpenMM MCP](https://github.com/QBT-Labs/openmm-mcp/tree/7f1036837d3100625f750e6bd7801534641c2295) | `7f1036837d3100625f750e6bd7801534641c2295` | MIT | MCP exposes create/cancel/cancel-all order tools. HTTP mode binds a port without an explicit loopback host, and the non-payment branch has no app-level authentication in the inspected handler. A local Unix socket is chmod 0600, which is a useful compensating control only for that local socket path. | Sandbox/testnet only; do not expose HTTP mode to a network or grant production credentials. |
| [OpenEtradeMcp](https://github.com/kerryjiang/OpenEtradeMcp/tree/a53a007c1dba329e79669adbc58a3552a2f4f74e) | `a53a007c1dba329e79669adbc58a3552a2f4f74e` | Apache-2.0 | Configuration defaults `UseSandbox=false` and `EnableOrderConfirmation=false`; the confirmation filter is not active unless enabled. Order placement/cancellation/modification tools exist. | Reject as-is for unattended use. Require explicit sandbox setting, enforced confirmation, auth review, and integration tests. |
| [Bitget Agent Hub](https://github.com/Bitget-AI/agent_hub/tree/2551419578abff99baad19b018cab1a963c62306) | `2551419578abff99baad19b018cab1a963c62306` | MIT | Repository metadata describes a toolkit spanning many exchange operations; only metadata/license and entry-point inventory were inspected here, not all operation schemas or auth paths. | Reference/research only; no execution tools in AURELIA. |
| [Superior Skills](https://github.com/Superior-Trade/superior-skills/tree/9d41db54b231f77e35610a73230eaeffcb456215) | `9d41db54b231f77e35610a73230eaeffcb456215` | MIT | Skills describe account/wallet, backtesting, deployment and live venue operations. Text-level instructions to seek confirmation are not a deterministic authorization boundary. | Prompt/reference only; disable write-capable tools; never treat skills as risk controls. |
| [MT5-Quant](https://github.com/masdevid/mt5-quant/tree/2a6cd8015a246032a286864d131309a0094c2d17) | `2a6cd8015a246032a286864d131309a0094c2d17` | MIT | MCP tools enumerate, search and copy MQL files into a configured project directory; a configuration field exists for a backtest password. Workspace scope and file permissions require an isolated test. MT5/EA behavior is not portable proof of Deriv compatibility. | Unprivileged tooling sandbox only; no production filesystem, credentials, or execution authority. |
| [Oracle3](https://github.com/YichengYang-Ethan/oracle3-prediction-market-agent/tree/267fb7c48dae7c4ff8922c02a3a223443e51bf0b) | `267fb7c48dae7c4ff8922c02a3a223443e51bf0b` | Apache-2.0 | Inspected live adapters include account/order identity checks, durable order journaling and reconciliation patterns. Its `StandardRiskManager` defaults include a 20% drawdown threshold, a $1,000 single-trade ceiling and optional daily-loss limit—materially different from AURELIA policy. Venue and settlement semantics are specific to prediction markets. | Research-only; extract design ideas for independent reimplementation, not direct integration. |

## Pinned source observations

### OpenTrader — fail-open risk helper and deployment defaults

Inspected:
- [`python/shared/risk_controls.py`](https://github.com/euriska/opentrader/blob/d430a4448ebd7002e77d3996e678cf752edecfdd/python/shared/risk_controls.py)
- [`python/traders/equity_trader.py`](https://github.com/euriska/opentrader/blob/d430a4448ebd7002e77d3996e678cf752edecfdd/python/traders/equity_trader.py)
- [`compose.yml`](https://github.com/euriska/opentrader/blob/d430a4448ebd7002e77d3996e678cf752edecfdd/compose.yml)
- [`python/traders/smart_order.py`](https://github.com/euriska/opentrader/blob/d430a4448ebd7002e77d3996e678cf752edecfdd/python/traders/smart_order.py)

The shared helper's documented and implemented behavior is fail-open for unavailable bid/ask and volume data; the default maximum slippage, minimum volume and maximum daily-loss values are all zero, interpreted as disabled. Redis read failures fall back to those defaults, while daily P&L read errors return zero. The equity trader imports these controls and the smart-order helper submits child orders into a broker-command stream. This design is unsuitable as AURELIA's independent deterministic capital gate, where stale or unverified risk inputs must reject a trade.

Compose defaults include `DB_PASSWORD=trading_secret`, `VAULT_TOKEN=vault_dev_token`, and `GRAFANA_PASSWORD=admin`; Grafana is mapped as `3000:3000`, while the Vault development listener is configured as `0.0.0.0:8200` inside the container network. These defaults must not be used for any accessible deployment. Network exposure and container isolation require a deployment-specific review; this finding does not assert that all internal ports are published to the host.

### OpenMM MCP — order tools and HTTP mode

Inspected:
- [`src/tools/trading.ts`](https://github.com/QBT-Labs/openmm-mcp/blob/7f1036837d3100625f750e6bd7801534641c2295/src/tools/trading.ts)
- [`src/server.ts`](https://github.com/QBT-Labs/openmm-mcp/blob/7f1036837d3100625f750e6bd7801534641c2295/src/server.ts)
- [`src/ipc/server.ts`](https://github.com/QBT-Labs/openmm-mcp/blob/7f1036837d3100625f750e6bd7801534641c2295/src/ipc/server.ts)

The inspected trading tools call connectors to create orders, cancel a specific order, and cancel all orders for a trading pair. In HTTP mode the server calls `listen(port)` without explicitly binding to loopback. The inspected non-x402 HTTP handler serves `/mcp` directly through the MCP transport and contains no app-level authentication check. Therefore HTTP mode must be treated as unsafe to expose to an untrusted network unless a separately verified authentication and network boundary is added. Payment gating, when enabled, is not a substitute for AURELIA's order authorization/risk gate.

Positive control: the Unix IPC socket is chmod'd to mode `0600`. However, connected local processes can request exchange credentials over that socket, so local-user/process isolation still matters. Do not provide production secrets or a production wallet to this candidate.

### OpenEtradeMcp — optional confirmation is off by default

Inspected:
- [`src/OpenEtradeMcp/EtradeConfig.cs`](https://github.com/kerryjiang/OpenEtradeMcp/blob/a53a007c1dba329e79669adbc58a3552a2f4f74e/src/OpenEtradeMcp/EtradeConfig.cs)
- [`src/OpenEtradeMcp/OrderConfirmationFilter.cs`](https://github.com/kerryjiang/OpenEtradeMcp/blob/a53a007c1dba329e79669adbc58a3552a2f4f74e/src/OpenEtradeMcp/OrderConfirmationFilter.cs)
- [`src/OpenEtradeMcp.Server/Program.cs`](https://github.com/kerryjiang/OpenEtradeMcp/blob/a53a007c1dba329e79669adbc58a3552a2f4f74e/src/OpenEtradeMcp.Server/Program.cs)

The guard's token/elicitation logic is only registered when `ETRADE_EnableOrderConfirmation=true`; configuration initializes it to false. `UseSandbox` is also initialized to false. This does not by itself prove an exploit, but it means a deployment that omits explicit configuration can lack the advertised confirmation behavior and use the production base URL. Require sandbox mode plus confirmation enabled, test every mutating operation and bypass path, and review OAuth token lifetime/storage before considering any integration.

### MT5-Quant — tool/file scope

Inspected:
- [`src/mcp_server.rs`](https://github.com/masdevid/mt5-quant/blob/2a6cd8015a246032a286864d131309a0094c2d17/src/mcp_server.rs)
- [`src/models/config.rs`](https://github.com/masdevid/mt5-quant/blob/2a6cd8015a246032a286864d131309a0094c2d17/src/models/config.rs)
- [`src/tools/handlers/experts.rs`](https://github.com/masdevid/mt5-quant/blob/2a6cd8015a246032a286864d131309a0094c2d17/src/tools/handlers/experts.rs)

The inspected handlers can search MQL directories and copy a provided source file into a configured project directory. The config model includes a `backtest_password` field, though this review did not establish whether any caller persists or exposes that value in all modes. Run only with explicit least-privilege workspace paths, sanitized target names, restricted filesystem access, and no secrets. Do not grant arbitrary MCP instructions access to a user's full MT5/Wine home directory.

### Oracle3 — useful lifecycle patterns, incompatible authority model

Inspected:
- [`oracle3/trader/kalshi_trader.py`](https://github.com/YichengYang-Ethan/oracle3-prediction-market-agent/blob/267fb7c48dae7c4ff8922c02a3a223443e51bf0b/oracle3/trader/kalshi_trader.py)
- [`oracle3/trader/polymarket_trader.py`](https://github.com/YichengYang-Ethan/oracle3-prediction-market-agent/blob/267fb7c48dae7c4ff8922c02a3a223443e51bf0b/oracle3/trader/polymarket_trader.py)
- [`oracle3/risk/risk_manager.py`](https://github.com/YichengYang-Ethan/oracle3-prediction-market-agent/blob/267fb7c48dae7c4ff8922c02a3a223443e51bf0b/oracle3/risk/risk_manager.py)
- [`tests/test_live_order_integrity.py`](https://github.com/YichengYang-Ethan/oracle3-prediction-market-agent/blob/267fb7c48dae7c4ff8922c02a3a223443e51bf0b/tests/test_live_order_integrity.py)

The adapters show design patterns worth studying: durable intent journaling, refusing blind resubmission after ambiguous submission, and verifying venue order identity and fill details. The cited tests use mocked network/auth entry points and therefore are not evidence of live venue correctness. Prediction-market settlement, fees, collateral, contract units and venues differ from Deriv synthetic/forex products. Do not port its strategy metrics or risk limits as-is.

### FlintTrade and prompt/tool catalogs

Inspected:
- [`docs/ORDER_SAFETY.md`](https://github.com/navaneeshnagarajan/FlintTrade/blob/a1f4adfc99e62d1f1a8ef6cb04e2dfef16993d9d/docs/ORDER_SAFETY.md)
- [`docker-compose.yml`](https://github.com/navaneeshnagarajan/FlintTrade/blob/a1f4adfc99e62d1f1a8ef6cb04e2dfef16993d9d/docker-compose.yml)
- [`skills/superior-trade/SKILL.md`](https://github.com/Superior-Trade/superior-skills/blob/9d41db54b231f77e35610a73230eaeffcb456215/skills/superior-trade/SKILL.md)
- repository/package metadata for [Bitget Agent Hub](https://github.com/Bitget-AI/agent_hub/tree/2551419578abff99baad19b018cab1a963c62306)

FlintTrade's safety document describes a multi-stage order admission and broker routing design; the inspected Compose file binds its backend API port to loopback and uses container hardening options. These are positive design indicators, not independent verification, and AGPL-3.0 licensing needs legal clearance before code reuse. Superior Trade's skill text covers wallet and live deployment workflows and instructs explicit user confirmation, but prompt instructions alone cannot be the only capital-movement control. Bitget Agent Hub has many operation surfaces per repository metadata; each tool's exact schema, permission, venue behavior and live-write path must be enumerated before any use.

## Requirements before any external-source adoption

1. Pin an immutable commit and verify its origin; inspect license and bundled/subdirectory licenses.
2. Clone/extract only in a disposable, unprivileged sandbox; never execute install scripts with production secrets or network access.
3. Generate an SBOM; run dependency, malware, secret, license and provenance checks against the exact pin; preserve machine-readable artifacts and tool versions.
4. Review server bind address, authentication, authorization, tool schemas, filesystem permissions, secret storage, outbound network access and deployment configuration.
5. Test malformed/stale/missing inputs, broker rejects, timeouts, duplicate requests, partial fills, restart recovery, cancellation safety, reconciliation and kill-switch behavior.
6. Reimplement accepted ideas behind AURELIA's own registry/interfaces. Third-party strategy code, prompts and runtime agents have no capital authority and cannot alter `LIVE_LOCK`.
7. Require independent human review and successful exact-commit assurance before merging any adoption-related change.

## Limitations and final disposition

This was a focused source-path inspection across eight selected repositories. It was not a complete audit of any repository, dependency graph, package artifact, model weight, generated file, deployment, or live behavior. No third-party code was copied into AURELIA, no credentials were read, no services were installed, no paid resources were created, and no broker orders were submitted.

**All eight candidates remain unapproved for AURELIA runtime/capital integration.** AURELIA's own release blockers remain separate: disabled repository rulesets / unverified branch protection, no independent PR review, missing authenticated Deriv read-only/verify-only evidence and broker-derived minimum-stake verification, missing OOS/calibration/economics/recovery/security/deployment/strategy-eligibility artifacts, and no demonstrated 3,600-second soak on a persistent authorized host. Keep `config/LIVE_LOCK.yaml` fail-closed.
