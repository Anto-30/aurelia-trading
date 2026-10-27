# AURELIA advisory-agent runtime setup

**Status:** advisory execution only. This guide does not authorize live trading and must not be used to change `config/LIVE_LOCK.yaml`.

## Current contract

The worker supervisor has built-in adapters for Claude Code, DeepSeek Harness, and Hermes Agent. Each accepts one bounded JSON task and returns one schema-validated result. Claude Code and Hermes run with tools disabled; DeepSeek Harness runs its headless profile using the read-only permission preset. Each worker runs under a dedicated non-root UID in the production container. A worker's API key is passed only to that worker; arbitrary parent environment variables and broker credentials are not inherited. The worker home is separate from the durable AURELIA capital-state volume.

The adapters are deliberately version-gated:

| Worker | Required CLI version | Required credentials/configuration | Runtime restrictions |
| --- | --- | --- | --- |
| ClaudeCode | `2.1.312` | `ANTHROPIC_API_KEY`, installed `claude` binary | `--tools ""`, `--disallowedTools "*"`, strict no-MCP configuration, one turn, updater disabled |
| DeepSeekHarness | `0.2.1-rc.2` | `DEEPSEEK_API_KEY`, installed `dsh` binary | `headless` profile, `read-only` permission preset, `--approval-policy never`; the OS user and filesystem permissions remain an independent boundary |
| HermesAgent | `v0.22.5` | provider-specific API key, `AURELIA_HERMES_PROVIDER`, `AURELIA_HERMES_MODEL`, installed `hermes` binary | `--safe-mode`, empty `--toolsets`, one-turn limit |

If an executable is absent, an API key is absent, a required Hermes provider/model selection is missing, or a version does not match the reviewed pin, the built-in healthcheck fails and the worker receives no active lease. Updating a version must be a reviewed code/config change followed by adapter tests and CI; do not bypass the version gate.

The base runtime image does **not** claim these CLIs are installed. They must be installed and verified in the actual deployment image, or mounted read-only into that image. Installing a CLI on the deployment host does not make it available inside the container.

## Install and verify the CLIs

Use official sources, verify vendor hashes/signatures where provided, and install only into the image or read-only path visible inside the container. Do not put provider executables in the writable AURELIA data volume.

### Claude Code

Official installation and CLI reference: [Claude Code setup](https://docs.anthropic.com/en/docs/claude-code/getting-started) and [CLI usage](https://docs.anthropic.com/en/docs/claude-code/cli-usage).

The upstream native installer is documented at:

```sh
curl -fsSL https://claude.ai/install.sh | bash
claude --version
```

The native installer may track a moving release. The adapter deliberately expects version `2.1.312`; an installed binary with any other version is blocked until the pin is reviewed and updated. Vendor documentation currently marks the global npm install as deprecated; avoid switching to an unpinned auto-updating CLI just to bypass this gate. The worker sets `DISABLE_AUTOUPDATER=1` on inference calls.

This adapter currently uses the Anthropic API key path. A user's interactive Claude subscription login is not automatically transferred into the isolated worker home.

### DeepSeek Harness

The official project documents Node.js `^22.19.0` or `>=24.0.0` and the `dsh --profile headless` mode. Reference: [official CLI help](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cli-help.md) and [CLI package](https://github.com/deepseek-ai/deepseek-harness/tree/master/apps/cli).

The current adapter pins package version `0.2.1-rc.2`, which is a release-candidate version. Install that exact published package in a controlled build environment and verify `dsh --version` matches before shipping the image. Do not silently substitute `latest`, `next`, a source-tree main branch, or a different pre-release. The adapter uses `--profile headless --permission-mode read-only --approval-policy never -` and provides the task text through stdin. The `read-only` preset is not treated as an OS sandbox; the dedicated non-root identity and inaccessible capital-state directory are additional controls.

### Hermes Agent

Official install guide: [Hermes Agent installation](https://hermes-agent.nousresearch.com/docs/getting-started/installation); [CLI reference](https://hermes-agent.nousresearch.com/docs/reference/cli-commands).

The upstream installer is available from:

```sh
curl -fsSL https://hermes-agent.nousresearch.com/install.sh
```

Fetch and inspect the script before executing it in a build. Prefer a reviewed, immutable source revision and verify `hermes --version` is exactly `v0.22.5`; the adapter intentionally refuses an unpinned version. The tested source tag points to commit `bf0203a794a07aac3ff764972ab9087baa4e4f4e` (the upstream tag is not cryptographically signed, so verify upstream provenance before production use). The adapter invokes `hermes chat --safe-mode --ignore-user-config --ignore-rules --toolsets "" --max-turns 1 --query-file -` and feeds the request over stdin. Explicit model/provider settings are required because safe mode does not inherit a profile's configured default model.

## Provision API credentials separately

Create the optional provider-only secret store on the deployment host:

`/etc/aurelia/aurelia-agent-provider-secrets.env`

Use an administrative editor such as `sudoedit`; do not place actual keys in the repository, this chat, a command-line argument, or a log. Keep the file owned by root with exact mode `0600`. The deployment script validates it and injects it through Docker's `--env-file` only if it exists.

Allowed names are strictly limited to provider API-key variables:

- `ANTHROPIC_API_KEY`
- `DEEPSEEK_API_KEY`
- `OPENROUTER_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `GOOGLE_API_KEY`
- `XAI_API_KEY`
- `ZAI_API_KEY`
- `ZHIPU_API_KEY`
- `MOONSHOT_API_KEY`
- `KIMI_API_KEY`
- `LITELLM_API_KEY`
- `HERMES_API_KEY`

The allowlist rejects Deriv/broker tokens, GitHub tokens, arbitrary command overrides, duplicate keys, symlinks and loose permissions. It prints variable names/counts and status only, never values. Configure `AURELIA_HERMES_PROVIDER` and `AURELIA_HERMES_MODEL` as non-secret variables in `/etc/aurelia/aurelia.env`; the secret-store validator does not allow them in the credential file.

Validate a prepared file without exposing its contents:

```sh
sudo python3 scripts/deploy/validate_agent_provider_secrets.py /etc/aurelia/aurelia-agent-provider-secrets.env
```

A result of `VALID` means only that the file satisfies the allowlist/permission contract. It does not verify that a key is valid or that a model endpoint is reachable.

## Set CLI paths and re-deploy in VERIFY_ONLY

If CLIs are not on the container's runtime `PATH`, set the absolute container paths in `/etc/aurelia/aurelia.env`:

```ini
AURELIA_CLAUDE_CLI=/usr/local/bin/claude
AURELIA_DSH_CLI=/usr/local/bin/dsh
AURELIA_HERMES_CLI=/opt/hermes/.venv/bin/hermes
AURELIA_HERMES_PROVIDER=deepseek
AURELIA_HERMES_MODEL=deepseek-chat
```

Those paths are examples; verify the binaries exist at those locations in the image. Preserve the current `config/LIVE_LOCK.yaml`, and run deployment in `VERIFY_ONLY` mode only. Do not set custom `AURELIA_AGENT_*_COMMAND` values unless the command is a reviewed, trusted adapter implementing the expected JSON-stdio protocol.

After deployment, run the no-secret report and worker probe inside the image:

```sh
python scripts/agent_runtime_availability.py
python scripts/agent_worker_probe.py --timeout-seconds 10
python scripts/agent_worker_probe.py --require-active --timeout-seconds 60
```

The non-strict probe can return `PASS` when it accurately reports that a provider is blocked. Examine each agent's `status` and `missing_prerequisites`. Only a row with a recent `WORKER_HEALTHCHECK_LEASE_ACTIVE` proves a worker passed its current configured healthcheck; provider identity, task quality and authorization remain separate checks. `--require-active` intentionally fails until all nine local worker roles have active leases.

A ChatGPT connector/tool catalog is not automatically forwarded to a local model process. Skill inventory registration is not local skill installation, and a configured plugin name is not evidence of a connected plugin. Those bridges need explicit adapters and authorization reviews.

## Release gates remain external

Making an advisory model call work does not authorize a broker order. Before any human considers enabling live execution, the system still needs verified Deriv account/session and verify-only lifecycle evidence, instrument- and contract-specific verified costs, frozen historical data, chronological walk-forward and sealed OOS evidence, prospective paper reconciliation, durable runtime health/soak, and independent review. Missing or stale evidence remains an abort condition. The model-agent layer never gains capital authority and may not edit the live lock.
