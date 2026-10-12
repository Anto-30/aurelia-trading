# Cloud-hosted AURELIA runtime alternative

This deployment path removes the dependency on a continuously connected personal desktop. It runs the existing Dockerized AURELIA runtime on a persistent private cloud service with a mounted data disk. It does not bypass the canonical runtime, capital-plane controls, live lock, or certification gates.

## Deployment state

- Blueprint is a proposed deployment configuration; it has not been deployed.
- Automatic deployment is disabled so changes do not silently restart a service.
- Runtime starts with explicit execution authorization disabled and live execution blocked.
- Journal, federation, readiness, performance, and Deriv evidence paths point to persistent storage.
- No broker credentials or provider secrets are included in this file. Add them only through the host's encrypted secret/environment-variable interface after a security review.
- A cloud process being online is not proof that external agents are authenticated, the broker account is verified, strategies are qualified, or live trading is permitted.

## Deploy using Render

1. Connect the canonical repository `Anto-30/aurelia-trading` to a Render account that you control.
2. Create a Blueprint deployment from this branch and review the service plan and persistent-disk cost before applying it.
3. Keep live execution blocked. Do not add Deriv credentials until the secret-storage audit is complete and the account/session verification path is ready.
4. After deployment, verify the service's `/health` and `/ready` endpoints from an authorized private-network diagnostic, inspect runtime logs, and confirm persistent evidence survives a controlled restart. The Blueprint uses a private service so runtime diagnostics are not exposed as public endpoints.
5. Complete authenticated provider request/result tests, Deriv verify-only lifecycle checks, failure/recovery tests, prospective out-of-sample qualification, calibration, execution economics, and the 3600-second soak before any release review.

## Limits

This is a persistent cloud runtime alternative, not a Desktop Commander connection. It can run AURELIA's server process on a host the owner authorizes, but it cannot access files or applications on the user's personal computer. It does not itself supply authenticated Claude/Grok/other provider sessions. The configured local agent-worker command protocol still needs a real, authenticated provider adapter that follows the JSONL contract documented in the code.
