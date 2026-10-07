#!/usr/bin/env bash
set -euo pipefail

CONTAINER="aurelia-runtime"
HEALTH_URL="http://127.0.0.1:8080/health"
INTERVAL_SECONDS="\${AURELIA_WATCHDOG_INTERVAL_SECONDS:-30}"

while true; do
  running="$(sudo docker inspect --format '{{.State.Running}}' "$CONTAINER" 2>/dev/null || echo false)"
  if [ "$running" != "true" ]; then
    sudo docker start "$CONTAINER" >/dev/null 2>&1 || true
  elif ! curl --fail --silent --show-error --max-time 8 "$HEALTH_URL" >/dev/null 2>&1; then
    sudo docker restart "$CONTAINER" >/dev/null 2>&1 || true
  fi
  sleep "$INTERVAL_SECONDS"
done
