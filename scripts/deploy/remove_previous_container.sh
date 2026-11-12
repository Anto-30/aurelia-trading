#!/usr/bin/env bash
set -euo pipefail

CONTAINER="$1"
if [[ -z "$CONTAINER" || ! "$CONTAINER" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]]; then
  echo "AURELIA_DEPLOY_BLOCKED=INVALID_CONTAINER_NAME"
  exit 2
fi

# A successful daemon health check plus an exact-name listing distinguishes
# an absent container from a Docker daemon/CLI failure.
sudo docker info >/dev/null
container_ids="$(sudo docker ps --all --quiet --filter "name=^/$CONTAINER$")"

if [[ -n "$container_ids" ]]; then
  while IFS= read -r container_id; do
    [[ -n "$container_id" ]] || continue
    # Do not suppress errors: any failed stop/removal aborts the deployment.
    sudo docker rm -f "$container_id"
  done <<< "$container_ids"
fi
