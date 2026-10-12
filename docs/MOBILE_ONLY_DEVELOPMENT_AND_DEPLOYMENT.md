# AURELIA phone-only engineering and deployment path

## Why this exists

AURELIA's current agent contract requires a user-controlled development host before the Dev profile can become active. The connected Desktop Commander inventory currently reports no paired device. This guide provides a browser-only engineering alternative that does not require owning a laptop.

## Option A — GitHub Codespaces from an Android phone

GitHub Codespaces runs a development environment on GitHub-hosted cloud compute and can be opened in a browser. It is suitable for code inspection, tests, and isolated repairs; it is **not** a persistent production worker and does not itself authorize trading.

1. Open https://github.com/Anto-30/aurelia-trading/pull/119 in your phone browser and sign in to GitHub.
2. After the review branch contains `.devcontainer/devcontainer.json`, open the repository, choose the branch `research/repository-intake-2026-10-12`, then tap **Code → Codespaces → Create codespace on this branch**. If the Codespaces option is unavailable, open https://github.com/codespaces and check whether Codespaces is enabled for your account.
3. Wait for the cloud environment to build. If asked to authorize the Codespaces feature, review and approve it in GitHub.
4. Use the integrated terminal in the browser to run:
   ```bash
   python -m compileall -q runtime research assurance tests
   python -m unittest discover -s research/labs/tests -p 'test_*.py' -v
   python -m unittest discover -s assurance -p 'test_*.py' -v
   python -m unittest discover -s tests -p 'test_*.py' -v
   python -m pytest -q tests/test_secret_presence_report.py
   python -m unittest assurance.test_hardening_controls -v
   ```
5. Keep work on a branch and use a pull request. Do not paste Deriv tokens, OAuth secrets, private keys, attestation signing keys, or production environment files into the Codespace or chat.

### Important limitations

- Codespaces may consume account quota or incur charges if included usage is exhausted. Review the GitHub Codespaces billing page before starting a large or long-running environment: https://github.com/settings/billing/summary
- A Codespace can stop after inactivity and is not an always-on runtime. Do not deploy the AURELIA worker inside it.
- The Codespace is for code and test work only. The default environment forces `VERIFY_ONLY`, disables authenticated Deriv verification and disables the autonomous loop. These defaults are convenience safeguards, not a substitute for the canonical production gates.
- Never add live broker credentials as Codespaces secrets. Production credentials belong only in the approved protected runtime secret store.
- The repository's canonical deployment policy currently specifies a Linux/Docker host, immutable release by exact Git commit, strict SSH host verification, protected secret files, persistent state, and a systemd health watchdog. Codespaces does not satisfy those production requirements.

## Option B — hosted CI for automated checks

GitHub Actions already runs AURELIA's compilation, research, assurance, runtime, hardening, container-build and fail-closed release-gate checks on hosted runners. Use the Actions tab and inspect the run for the exact commit being reviewed. A green run validates that commit's automated checks; it does not prove a real Deriv session, persistent worker health, broker transaction verification or live-release qualification.

## Production remains a separate step

The current deployment policy selects `self_hosted`, `linux_docker`, `ssh_immutable_archive`, and a persistent Linux host with a systemd watchdog. The repository's `.github/workflows/self-hosted-runtime-deploy.yml` uses a protected `production` environment and exact `main` source. No production host or its SSH identity is created by this guide.

Before a production deployment, an authorized host and protected secret store must be configured; fresh authenticated Deriv real-account evidence, read-only broker account evidence, verify-only transaction lifecycle evidence, current source-linked attestations, a healthy persistent runtime, the soak period, reconciliation and independent release checks must all pass. Keep `config/LIVE_LOCK.yaml` fail-closed until every required condition is proven.

## Current mobile unblock status

- Desktop Commander: no paired device was visible, so remote desktop commands cannot run against a phone alone.
- Browser-based Codespaces: `.devcontainer/devcontainer.json` and this guide are committed on the review branch in PR #119. The agent federation audit and continuity watchdog passed for commit `aa177d88cf9fb33b0e16b4aaa121d7e73aa5ca67`. AURELIA Assurance run [38272112360](https://github.com/Anto-30/aurelia-trading/actions/runs/38272112360) completed successfully at the workflow level: compilation, research, assurance, runtime, secret-presence, hardening, container-build and public Deriv transport steps passed. This is not production certification: authenticated Deriv session/account/verify-only lifecycle steps were skipped because `DERIV_AUTH_CONFIGURED=false`; the certification report is `NOT_READY` because required broker lifecycle, recovery, 3600-second soak, prospective OOS, calibration, execution economics, security audit, deployment and strategy-eligibility evidence artifacts are missing. `FINAL_EXECUTION_AUTHORIZATION=false` and `LIVE_EXECUTION=BLOCKED` remain enforced. Starting a Codespace requires the account owner to initiate it in GitHub's UI; this connector cannot create one on the user's behalf.
- Production deployment: not executed. No host credentials, deployment target or production secret values are requested or recorded in this document.


## Hosting-provider check (2026-10-12)

The connected Vercel account was inspected. Its linked projects were `tales-and-trails-safaris` and `tales-and-trails-safaris-hjip`; no AURELIA project was returned. Therefore Vercel is not a verified AURELIA production target in this account, and no deployment was attempted. The checked-in AURELIA deployment policy remains the source of truth and specifies a persistent Linux/Docker host rather than a serverless web project.


## Codespaces cost guard

GitHub's current billing documentation states that personal Free accounts include 120 core-hours and 15 GB-month of Codespaces storage per month. Usage beyond included quota can be billed if a payment method and budget permit it; without a valid payment method, usage is blocked when quota is exhausted. Check current usage and budgets before leaving a Codespace running: https://docs.github.com/en/billing/concepts/product-billing/github-codespaces


## Protected GitHub Actions configuration — Deriv verify-only

This checklist is for the repository owner. It does not grant live trading authority and does not replace production-host provisioning.

1. Open the repository in a browser, then **Settings → Environments → production**. Confirm the environment exists and retain any configured required reviewers / deployment branch restrictions. Add environment secrets here rather than committing them to files.
2. For PAT authentication, add these exact names as **environment secrets**:
   - `DERIV_AUTH_TOKEN` (preferred canonical name) **or** `DERIV_PAT` — a newly created Deriv Personal Access Token with only the permissions needed for the account-read and verify-only checks.
   - `DERIV_APP_ID` — the application ID for the Deriv application associated with that PAT.
   - `DERIV_EXPECTED_LOGINID` — the exact account login ID AURELIA is authorized to inspect; alternatively use `DERIV_AUTHORIZED_ACCOUNT_ID`.
   - `DERIV_EXPECTED_CURRENCY` — `USD` for the currently supported verification path.
3. Under **Settings → Environments → production → Environment variables**, set `DERIV_AUTH_MODE=pat`. The workflows default to `pat` if this variable is absent. Only choose `oauth` if the OAuth integration has been configured and tested according to its own flow; do not mix OAuth and PAT assumptions.
4. Never send or paste the token, app credentials, private keys, or secret values into ChatGPT, issue comments, PR text, workflow inputs, logs, or source files. If a value may have been exposed, revoke it and create a replacement before proceeding.
5. Once secrets are saved, open **Actions** on the canonical `main` branch and manually run **AURELIA Deriv Authenticated Session Verification** with environment `real` for account verification. Inspect the run and its uploaded evidence; do not treat secret-presence alone as authentication. Then run **AURELIA Deriv Verify-Only Evidence** and **AURELIA Deriv Verify-Only Lifecycle** only after the preceding session/account evidence passes. The lifecycle workflow validates a proposal/intent and explicitly asserts zero submitted orders.
6. These workflows intentionally pin `FINAL_EXECUTION_AUTHORIZATION=false` and `LIVE_EXECUTION=BLOCKED`. Do not dispatch the self-hosted deployment workflow in `LIVE` mode to test credentials.

### Additional secrets required only after a real production host is provisioned

The self-hosted deployment workflow additionally expects `AURELIA_HOST`, `AURELIA_USER`, `AURELIA_SSH_KEY`, and `AURELIA_KNOWN_HOSTS` environment secrets. Generate a dedicated least-privilege deployment identity on the actual Linux host and populate `AURELIA_KNOWN_HOSTS` from a trusted, independently verified SSH host key; do not disable strict host checking. The LIVE path also references `AURELIA_ATTESTATION_SIGNING_KEY`, `AURELIA_OPERATOR_RESET_SIGNING_KEY`, and the `AURELIA_RUNTIME_ID` variable. Those are not substitutes for a host, security review, attestations, recovery testing, or runtime qualification.

The GitHub connector available to the engineering assistant does not expose an operation for creating environment secrets, configuring environment protection, or provisioning a Codespace/production host. These account-owner UI operations therefore cannot be performed by the assistant. After the owner completes the steps above, the assistant can inspect workflow results and help diagnose failures without seeing secret values.
