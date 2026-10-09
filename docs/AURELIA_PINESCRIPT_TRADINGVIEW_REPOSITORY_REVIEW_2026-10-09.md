# AURELIA Pine Script / TradingView Repository Review

Date: 2026-10-09. This is a pinned source registry and review, not a production installation.

## Source pins

| Repository | Commit | License metadata | Mode | Assigned primary agent |
|---|---|---|---|---|
| [Mathieu2301/TradingView-API](https://github.com/Mathieu2301/TradingView-API) | `6a4f8ff9a2b332d0a59dbd27c75201eb84663045` | NOASSERTION | SANDBOX_ONLY | ClaudeCode |
| [tradesdontlie/tradingview-mcp](https://github.com/tradesdontlie/tradingview-mcp) | `c05b8f5755ed8e64ea242de88ddbf46aa24d56a4` | NOASSERTION | SANDBOX_ONLY | GrokBot |
| [fabston/TradingView-Webhook-Bot](https://github.com/fabston/TradingView-Webhook-Bot) | `7eff8f9e9e13f350d7a3f258329285eb3a0bbd37` | NOASSERTION | SANDBOX_ONLY | ClaudeCode |
| [pineforge-4pass/pineforge-engine](https://github.com/pineforge-4pass/pineforge-engine) | `873b25daa00687cd2b9b9d6b2e49c57149227edd` | Apache-2.0 | RESEARCH_ONLY | KimiK3 |
| [pinecone-io/pinecone-claude-code-plugin](https://github.com/pinecone-io/pinecone-claude-code-plugin) | `c383d38b5cc3c5ec219f2e68026e47ffbf46524a` | MIT | TOOLCHAIN_ONLY | ClaudeCode |
| [tmustier/pine-of-glass](https://github.com/tmustier/pine-of-glass) | `6e7dd5fd613198fee9fff71df1bc45a579030cce` | MIT | REFERENCE_ONLY | ClaudeCode |
| [FaustoS88/Pydantic-AI-Pinescript-Expert](https://github.com/FaustoS88/Pydantic-AI-Pinescript-Expert) | `03cbd93c486435df08d70185fbab9aa61fff5fbb` | MIT | RESEARCH_ONLY | KimiK3 |
| [be-thomas/OpenPineScript](https://github.com/be-thomas/OpenPineScript) | `a793e719043a0a05dc7c184b04ef4ad6985d0de9` | GPL-3.0 | RESEARCH_ONLY | KimiK3 |
| [jpantsjoha/pinescript-vscode-extension](https://github.com/jpantsjoha/pinescript-vscode-extension) | `b81aa3d88f6327328ebf84b851757bd6266e56f8` | NOASSERTION | TOOLCHAIN_ONLY | ClaudeCode |
| [double232/pinescript-skill](https://github.com/double232/pinescript-skill) | `107fd4c6f4abd6cf64639040d6d67b42d130aa3d` | NOASSERTION | REFERENCE_ONLY | ClaudeCode |
| [gugu91/pinet](https://github.com/gugu91/pinet) | `78b24b7ce6abd3e7cb793b31a399041c7d6a3c7a` | MIT | TOOLCHAIN_ONLY | ClaudeCode |
| [folknor/pine-tools](https://github.com/folknor/pine-tools) | `3dd9f3c941ece3368e500360dd9e6e125ad396f6` | NOASSERTION | TOOLCHAIN_ONLY | ClaudeCode |
| [dharmanan/PineScript-coder](https://github.com/dharmanan/PineScript-coder) | `5f4c0f65e58b60860a920c2c59670ed21b1a9eaa` | MIT | RESEARCH_ONLY | KimiK3 |
| [dotsystemsdevs/pineflow](https://github.com/dotsystemsdevs/pineflow) | `8d2dbbc2a5b3061d102c6beb2e9070c4c4f05e3d` | MIT | REFERENCE_ONLY | ClaudeCode |
| [batonogov/pine](https://github.com/batonogov/pine) | `c5ed7a4c4744c4dfd4ff88dd20cc94a2c81b96d1` | MIT | TOOLCHAIN_ONLY | ClaudeCode |
| [edeng23/pines](https://github.com/edeng23/pines) | `c6020543236360c92adff8ee48d621b1d4b3759f` | Apache-2.0 | TOOLCHAIN_ONLY | ClaudeCode |
| [TheFractalyst/PineMCP](https://github.com/TheFractalyst/PineMCP) | `c630de784c795d8abc5e15780881f5237dba8bdc` | MIT | SANDBOX_ONLY | GoogleAgentSkills |
| [85599/pinesprout](https://github.com/85599/pinesprout) | `48bcea15275351869dffa1a3ba5fa6ffebd1f983` | MIT | RESEARCH_ONLY | KimiK3 |
| [hasnocool/tradingview-script-downloader](https://github.com/hasnocool/tradingview-script-downloader) | `997d5417235c4fa9d4e20d56b02fe6b0fd3fd37d` | NOASSERTION | REFERENCE_ONLY | ClaudeCode |
| [coocolab/Coocolab-Tradingview-MCP](https://github.com/coocolab/Coocolab-Tradingview-MCP) | `cd16a7dc038762688e7807a26285a26337d6fc60` | NOASSERTION | SANDBOX_ONLY | GoogleAgentSkills |
| [daviddme/tradingview-indicator-search-mcp-server](https://github.com/daviddme/tradingview-indicator-search-mcp-server) | `1f8648936088cf189e4ac1a23b55c522c11d15cd` | MIT | SANDBOX_ONLY | GoogleAgentSkills |
| [kashsuks/Pinel](https://github.com/kashsuks/Pinel) | `1b10a5f8c8f772a27360d77dae33be5137bc7a66` | GPL-3.0 | TOOLCHAIN_ONLY | ClaudeCode |
| [pinecone-io/getting-started-with-pinecone-webinar](https://github.com/pinecone-io/getting-started-with-pinecone-webinar) | `76068a1b11a5c33dd82192f31ba5377c46c656cf` | MIT | REFERENCE_ONLY | ClaudeCode |

## Review decisions

- Pine Script engines, generators, and strategy assistants remain `RESEARCH_ONLY`. Generated scripts must be checked for repainting, lookahead leakage, session/timezone assumptions, order-fill semantics, commission/slippage, symbol mapping, and realistic out-of-sample results before any candidate can qualify.
- TradingView browser/MCP integrations remain `SANDBOX_ONLY`; do not mount a logged-in production browser profile, cookies, Deriv credentials, SSH keys, or production workspace.
- Public-source discovery is not permission to copy scripts. Verify author license and platform terms before reuse.
- GPL-3.0 projects `be-thomas/OpenPineScript` and `kashsuks/Pinel` require compatibility review before linking or redistribution. Projects with `NOASSERTION` are not approved for redistribution until their license is clarified.
- Pinecone plugin/examples are reference/toolchain only. No Pinecone account, key, or external Claude runtime was configured by this change.
- All new skill records have `capital_authority: false`; AURELIA's deterministic risk and execution plane remains the only capital authority.

## Status

23 source records are pinned in `config/external_repo_federation.json` and routed in `config/agent_capability_matrix.json`. Source registration does not claim physical installation, runtime connectivity, strategy qualification, broker authentication, or live trading readiness.
