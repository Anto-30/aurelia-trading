# AURELIA Federation Plugin

Cross-agent engineering plugin for the existing AURELIA architecture.

Supported packaging targets:
- Claude Code via `.claude-plugin/plugin.json`
- Grok via `.grok-plugin/plugin.json`
- Kimi Code via `kimi.plugin.json`

The plugin intentionally contains no capital-moving MCP server, hook, order tool, broker credential reader, or live-release mutator.

Use alongside the pinned ecosystem registry in `config/agent_skill_federation.json`.
