# AURELIA Agent Workspace Bootstrap

## Purpose

This branch prepares a browser-based Linux development workspace for credential-free AURELIA research and engineering. It is a workspace bootstrap only; it is not a production release, merge authorization, or approval to install external tools globally.

Branch: `ops/free-codespaces-agent-workspace-20261110`

Base: PR #292 security-fix head `024fa88d247b532b261b194d549e5fa53e9a4f56`.

## Workspace policy

- Use a personal GitHub Codespaces account's included quota and select the smallest 2-core Linux machine offered.
- Set an idle timeout of 5–10 minutes, stop the codespace when finished, and monitor the included quota before long jobs.
- Do not attach payment methods or raise spending limits solely for this workspace. GitHub Free personal accounts currently include monthly Codespaces compute/storage quota; usage is restricted after quota exhaustion when no payment method is attached.
- This dev container intentionally has no `postCreateCommand`, `postStartCommand`, feature install script, secret import, broker connectivity, or automatic agent execution.
- Use a separate research branch for work. Do not merge this workspace branch into `main`; do not create a PR to `main` until PR #292's security and signature gates are independently cleared.

## First checks

After opening the Codespace terminal:

```bash
git status --short --branch
git rev-parse HEAD
python --version
node --version
```

Expected base source is the security-fix branch. Confirm `config/LIVE_LOCK.yaml` remains fail-closed before any research:
- `live_trading_enabled: false`
- `FINAL_EXECUTION_AUTHORIZATION: false`
- `LIVE_EXECUTION: BLOCKED`
- `capital_plane_mode: VERIFY_ONLY`

Do not use `pip install -r requirements.txt` until the dependency file and package install hooks have been reviewed in this disposable workspace.

## Agent roles

The project Claude Code subagents are in `.claude/agents/`. They are deliberately read-only and limited to `Read`, `Grep`, and `Glob`. Their assigned specialisms are security, market-data QA, quantitative research, simulator/statistics review, CI/release review, and evidence provenance.

No agent is allowed to:
- read or store production secrets;
- call a broker, inspect an account, request a proposal, or transmit an order;
- edit `config/LIVE_LOCK.yaml`, risk policy, capital authority, or execution controls;
- merge, deploy, change environment protections, or override a release gate.

A later implementation worker must use a separate worktree/branch and must be independently reviewed. Do not give a Claude subagent shell or write tools to make path restrictions appear stronger than they are.

## Attach the Codespace to ChatGPT through Desktop Commander

After the Codespace has been created and its terminal is open:

1. Open [Desktop Commander](https://mcp.desktopcommander.app/) and follow its **Add Device** instructions.
2. In the Codespaces terminal, run:

   ```bash
   npx @wonderwhy-er/desktop-commander@latest remote
   ```

3. Keep that remote process running. Do not paste any pairing code, access token, or credential into chat.
4. Confirm the device appears online in Desktop Commander.

When it connects, the first remote action must inspect its configuration and restrict `allowedDirectories` to the Codespace's AURELIA workspace path. Never set `allowedDirectories` to an empty array; Desktop Commander documents that as full-filesystem access. Do not install tools or inspect sensitive paths until the restriction is verified.

## Installing agent runtimes

Review each official install guide immediately before running an installer:
- Claude Code: https://docs.anthropic.com/en/docs/claude-code/getting-started
- DeepSeek Harness: https://www.deepseek.com/harness/en/
- Hermes Agent: https://hermes-agent.nousresearch.com/docs/getting-started/installation/

The dev container only provides Python 3.13 and Node.js 22. It does not install these runtimes automatically. CLI software may be free while model inference requires a paid subscription, an API key, or a limited free-tier account. Do not store credentials in Git, repository files, issue comments, build logs, or Codespaces secrets shared with untrusted code.

Before enabling Claude Code MCPs, inspect `.mcp.json` and verify each command, package source, and permission boundary. No external MCP server is preinstalled or trusted by this branch.

## Required verification before using an agent

1. Confirm runtime binary/version and vendor source.
2. Confirm model-provider authentication and cost/usage limits through the provider's official UI.
3. Start with a harmless read-only prompt against this document.
4. Confirm the subagent's tool allowlist and deny shell/network/write tools unless a separately reviewed task needs them.
5. Record task, agent, model/provider, runtime version, exact commit, output, and reviewer in the evidence ledger.
6. Re-check `LIVE_LOCK` and working-tree state after each task.

This workspace is not a trading runtime and has no capital authority.
