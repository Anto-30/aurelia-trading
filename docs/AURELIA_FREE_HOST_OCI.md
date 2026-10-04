# AURELIA Free Persistent Host: Oracle Cloud Always Free

## Decision

AURELIA should use an Oracle Cloud Infrastructure (OCI) Always Free Compute VM as the persistent host for the existing worker when Railway cannot be used.

This does not replace the AURELIA runtime, capital plane, Risk Warden, Execution Firewall, Deriv adapter, ledger, idempotency store, fencing, or LIVE_LOCK. It supplies compute only.

Oracle currently documents Always Free compute resources including up to two VM.Standard.E2.1.Micro instances or a VM.Standard.A1.Flex allowance of 1,500 OCPU-hours and 9,000 GB-hours per month. The A1 allowance is equivalent to 2 OCPUs and 12 GB of memory for an Always Free tenancy. Oracle also documents 200 GB of Always Free block-volume storage. Always Free compute must be created in the tenancy's home region. Oracle notes that temporary capacity shortages can prevent creation and that idle Always Free compute can be reclaimed under its documented idle criteria.

Official reference:
https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

## Recommended VM

Use an OCI Ampere A1 VM with 1 OCPU and 6 GB RAM, Ubuntu Linux, and a public IPv4 address.

This is deliberately below the documented 2 OCPU / 12 GB Always Free A1 allocation.

Open TCP port 22 for SSH only. Do not expose port 8080 publicly. The AURELIA container binds its health endpoint to 127.0.0.1 on the VM.

A1 is ARM-based. AURELIA's existing Python Docker image uses the standard Python 3.13 slim image and should be built for the host architecture without changing application code.

## GitHub deployment path

GitHub Actions remains the deployment transport. The repository is public, and GitHub documents standard GitHub-hosted runners as free and unlimited for public repositories.

Official reference:
https://docs.github.com/en/actions/reference/runners/github-hosted-runners

The workflow is:

1. GitHub Actions checks the exact source commit and verifies the fail-closed LIVE_LOCK.
2. GitHub Actions verifies that the exact commit has a completed-success AURELIA Assurance run.
3. The runner creates a source archive for the exact commit.
4. The runner transfers the archive over strict SSH to the OCI VM.
5. The existing Dockerfile builds the AURELIA runtime unchanged.
6. Docker runs the existing \`python -m runtime.main\` entry point.
7. AURELIA state under \`/tmp/aurelia\` is backed by the VM's \`/var/lib/aurelia\` directory.
8. The deployed source SHA is recorded durably at \`/var/lib/aurelia/DEPLOYED_SOURCE_SHA\`.
9. The worker is forced to keep \`AURELIA_AUTONOMOUS_LOOP=false\` and \`AURELIA_VERIFY_DERIV_AUTH=false\` in the persistent container.

The deployment workflow is manual by design. A green commit is not automatically promoted to the persistent host.

The workflow input `deployment_mode` defaults to **VERIFY_ONLY**. **LIVE** is an explicit option, but the workflow itself cannot flip the lock; it only deploys a source revision whose `LIVE_LOCK` already authorizes capital movement.

## One-time GitHub secrets

Create these repository secrets:

- \`OCI_HOST\`: VM public IPv4 address or resolvable hostname.
- \`OCI_USER\`: the OCI Linux user, normally \`ubuntu\` for Ubuntu images.
- \`OCI_SSH_KEY\`: the private SSH key used to access the VM.
- \`OCI_KNOWN_HOSTS\`: the verified SSH host-key line(s) for the VM.

Do not put DERIV credentials into these secrets.

Before saving \`OCI_KNOWN_HOSTS\`, obtain the SSH host fingerprint from a trusted environment and compare it with the fingerprint presented by the OCI VM. The workflow uses StrictHostKeyChecking and does not use blind host-key discovery.

## Persistent filesystem

The worker's existing runtime paths remain under \`/tmp/aurelia\` inside the container:

- federation journal
- federation lease state
- ledger
- idempotency state
- execution fence
- execution journal
- runtime journal

Docker bind-mounts \`/var/lib/aurelia\` to \`/tmp/aurelia\`, so restarts do not discard these files.

The host also retains the deployed source SHA and last health snapshot.

## Deriv verification sequence

Do not enable the autonomous execution loop on the persistent worker yet.

The existing repository's \`aurelia-assurance.yml\` already contains a non-capital-moving authenticated Deriv verifier. On the certified baseline, that step was skipped because the required Deriv GitHub secrets were not configured; the remainder of Assurance was green.

The next evidence step is therefore:

1. Configure the approved Deriv authentication credentials in the secure control plane used for the verification workflow. Never commit or print the token.
2. Run the existing authenticated Deriv session verifier.
3. Require exact account binding, account environment, currency, fresh balance, and \`orders_submitted=0\`.
4. Preserve the generated evidence artifact.
5. Separately exercise the existing Risk Warden / Execution Firewall / authorization and fencing tests. The existing executor refuses live submission when \`LIVE_LOCK\` is active.
6. Do not interpret proposal generation or control-path tests as a broker-confirmed transaction.
7. Only a future independently certified release may change the live authorization state.

## Important limitation

OCI Always Free is not a billing bypass for Railway. It is a separate free-tier compute option with provider-specific eligibility, quota, capacity, and account requirements.

Oracle documents that Always Free instances can be reclaimed when they remain sufficiently idle for the documented 7-day conditions. AURELIA's worker should produce regular process activity, but no cloud provider guarantee should be inferred from that. The host must therefore be monitored independently.

## Operational command

After the OCI VM and four GitHub secrets exist:

GitHub -> Actions -> **AURELIA OCI Always-Free Host Deploy** -> **Run workflow** -> select \`feat/autonomous-loop-federated-runtime\`.

The workflow is intentionally manual and will refuse to deploy if Assurance is not green for the exact commit or if the repository lock is not fail-closed.

## Current security posture

The persistent OCI worker is infrastructure-only.

\`LIVE_EXECUTION=BLOCKED\`

\`FINAL_EXECUTION_AUTHORIZATION=false\`

\`AURELIA_AUTONOMOUS_LOOP=false\`

\`AURELIA_VERIFY_DERIV_AUTH=false\`

The host integration does not authorize capital, submit orders, or mutate \`config/LIVE_LOCK.yaml\`.
