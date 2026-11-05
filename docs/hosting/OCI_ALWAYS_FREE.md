# AURELIA hosting: OCI Always Free reference deployment

## Recommendation

The strongest currently documented $0 candidate for AURELIA's persistent Linux/Docker runtime is **Oracle Cloud Infrastructure (OCI) Always Free Ampere A1**, subject to account eligibility, home-region capacity, and published Always Free limits. This is a host recommendation, not a deployed or verified runtime.

Official references:
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm

OCI documents a monthly Always Free A1 allowance equivalent to up to 2 OCPUs and 12 GB RAM (1,500 OCPU-hours and 9,000 GB-hours). Compute must be provisioned in the tenancy home region. Capacity may not be available at signup or at provisioning time.

## Why it fits AURELIA

AURELIA already has a provider-neutral self-hosted deployment contract:
- `config/deployment_policy.json`
- `.github/workflows/self-hosted-runtime-deploy.yml`
- `scripts/deploy/bootstrap_and_deploy.sh`
- persistent state root `/var/lib/aurelia`
- private health endpoint `127.0.0.1:8080/health`
- systemd watchdog and Docker restart policy

A VM is a better fit for a persistent Python worker, WebSocket reconnect loop, Docker runtime, and durable local state than a serverless function or free web tier that sleeps. The current Dockerfile uses `python:3.13-slim`; the first host acceptance test must verify ARM64 image build and runtime. Do not assume optional native dependencies or third-party agent binaries support ARM64.

## Provider constraints

- OCI may reclaim an Always Free compute instance if, over a 7-day period, 95th-percentile CPU utilization is below 20%, network utilization is below 20%, and (for A1) memory utilization is below 20%. Do not evade provider policy with artificial traffic.
- Always Free is not an SLA. Regional capacity, maintenance, account eligibility, and service availability are not guaranteed.
- Signup commonly requires phone verification and a payment card. Paid resources or usage outside Always Free limits can incur charges if the account is upgraded.
- A single VM is a single failure domain, not high availability. Backups and restore tests are mandatory.
- Keep the host private, restrict egress, use key-only SSH and strict host-key pinning, and never expose control or health endpoints publicly.
- Do not put Deriv credentials in GitHub Actions or agent prompts. Secrets belong only in the protected host secret store after credential rotation and security review.

## Provisioning sequence

1. Create an OCI Free Tier account and choose a home region with A1 capacity.
2. Provision one Ampere A1 VM within the aggregate Always Free allowance (up to 2 OCPUs and 12 GB RAM), with a supported Linux image.
3. Attach persistent storage within the free allowance. Configure backup/snapshot and test restore.
4. Install Docker and the SSH deployment prerequisites. Create a dedicated non-root `aurelia` OS user. Restrict SSH to keys and trusted source IPs.
5. Verify ARM64 and build the image from an exact AURELIA commit. Confirm the runtime starts natively without emulation.
6. Configure the GitHub Actions production environment with the existing deployment secrets: `AURELIA_HOST`, `AURELIA_USER`, `AURELIA_SSH_KEY`, `AURELIA_KNOWN_HOSTS`. Keep strict host-key verification enabled.
7. Deploy in `VERIFY_ONLY` only. Verify exact commit, health, persistence across restart, kill-switch persistence, backups, restore, log redaction, time synchronization, reconnect/reconciliation, and a 3,600-second VERIFY_ONLY soak.
8. Keep `config/LIVE_LOCK.yaml` blocked. Hosting success is not broker verification, strategy qualification, or live authorization.

## Why not Render, Koyeb, Cloudflare Workers, or Google e2-micro?

- Render free web services sleep after 15 minutes without inbound traffic, use ephemeral local filesystems, and free Postgres expires after 30 days. Render explicitly says not to use free instances for production.
- Koyeb's free service scales to zero after one hour, cannot run worker services, and cannot attach persistent volumes.
- Cloudflare Workers are event-driven with per-invocation CPU limits; they are not a persistent Python/Docker worker host.
- Google Cloud's always-free e2-micro is limited to US regions and 1 GB RAM, which is a weak fit for the full Docker runtime.

## Evidence state

`HOST_SELECTED_FOR_EVALUATION=OCI_ALWAYS_FREE_A1`

`HOST_ACCOUNT_CONNECTED=false`

`HOST_PROVISIONED=false`

`ARM64_BUILD_VERIFIED=false`

`RUNTIME_DEPLOYED=false`

`PERSISTENCE_RESTART_TEST=NOT_RUN`

`3600S_SOAK=NOT_RUN`

`LIVE_EXECUTION=BLOCKED`

Change these values only when new, attributable host evidence exists.