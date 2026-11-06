# Claude Code GitHub Actions — read-only review

## Purpose

AURELIA can use the official Claude Code GitHub Action as an optional, read-only reviewer for internal pull requests. This does not create a persistent Claude daemon, an implementation agent, or a trading agent. The workflow is disabled by default.

## Required owner configuration

In the repository's GitHub Actions settings, configure:

1. Non-secret repository variable: `CLAUDE_REVIEW_ENABLED=true`.
2. Exactly one Anthropic credential as a GitHub Actions Secret:
   - `CLAUDE_CODE_OAUTH_TOKEN` (OAuth token generated locally with `claude setup-token`), or
   - `ANTHROPIC_API_KEY` (API key from Anthropic Console).

The workflow prefers the OAuth token when both are present. It only prints the selected authentication *method*, never credential values. Do not send either credential in chat, commit it to Git, or expose it in workflow output. The GitHub connector cannot configure protected Actions secrets.

To disable this reviewer, set `CLAUDE_REVIEW_ENABLED` to `false` or remove it.

## Execution boundary

- Trigger: non-draft pull requests from this same repository only; fork pull requests are not run.
- Both GitHub Actions and Claude Code Action are pinned to commit SHAs.
- `actions/checkout` does not persist its token.
- The job token has read-only repository, pull-request, issue, and Actions permissions.
- Claude Code's built-in tools are restricted to `Read`, `Grep`, and `Glob`; MCP tools are denied.
- The workflow uses Plan mode, does not post comments, does not edit or commit files, and does not deploy.
- The reviewed diff is captured as inert text. PR content and repository files are untrusted input; embedded instructions must be ignored.
- No Deriv, broker, capital, production-secret, or live-execution context is provided.
- `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, and `capital_plane_mode=VERIFY_ONLY` remain unchanged.

The CI run is evidence that the workflow can run, not proof that Claude credentials are configured or a Claude review actually executed. Until the opt-in variable and credential exist, the action explicitly reports a skipped state.
