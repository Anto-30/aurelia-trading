#!/usr/bin/env bash
set -euo pipefail

SHA="${1:?source commit SHA required}"
APP_ROOT="/opt/aurelia"
RELEASE_ROOT="$APP_ROOT/releases"
RELEASE_DIR="$RELEASE_ROOT/$SHA"
CURRENT_LINK="$APP_ROOT/current"
ENV_DIR="/etc/aurelia"
ENV_FILE="$ENV_DIR/aurelia.env"
DATA_DIR="/var/lib/aurelia"
IMAGE="aurelia-runtime:$SHA"
CONTAINER="aurelia-runtime"
DEPLOYMENT_MODE="${AURELIA_DEPLOYMENT_MODE:-VERIFY_ONLY}"

if ! command -v sudo >/dev/null 2>&1; then
  echo "AURELIA_HOST_BLOCKED=SUDO_REQUIRED"
  exit 2
fi
sudo -n true

if [ ! -d "$RELEASE_DIR" ]; then
  echo "AURELIA_HOST_BLOCKED=MISSING_RELEASE_DIR"
  exit 2
fi

LOCK_FILE="$RELEASE_DIR/config/LIVE_LOCK.yaml"
test -f "$LOCK_FILE"

case "$DEPLOYMENT_MODE" in
  VERIFY_ONLY)
    grep -Eq "^live_trading_enabled:[[:space:]]*false[[:space:]]*$" "$LOCK_FILE"
    grep -Eq "^FINAL_EXECUTION_AUTHORIZATION:[[:space:]]*false[[:space:]]*$" "$LOCK_FILE"
    grep -Eq "^LIVE_EXECUTION:[[:space:]]*BLOCKED[[:space:]]*$" "$LOCK_FILE"
    grep -Eq "^capital_plane_mode:[[:space:]]*VERIFY_ONLY[[:space:]]*$" "$LOCK_FILE"
    ;;
  LIVE)
    grep -Eq "^live_trading_enabled:[[:space:]]*true[[:space:]]*$" "$LOCK_FILE"
    grep -Eq "^FINAL_EXECUTION_AUTHORIZATION:[[:space:]]*true[[:space:]]*$" "$LOCK_FILE"
    grep -Eq "^LIVE_EXECUTION:[[:space:]]*ENABLED[[:space:]]*$" "$LOCK_FILE"
    grep -Eq "^capital_plane_mode:[[:space:]]*LIVE[[:space:]]*$" "$LOCK_FILE"
    ;;
  *)
    echo "AURELIA_HOST_BLOCKED=INVALID_DEPLOYMENT_MODE"
    exit 2
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io curl
  else
    echo "AURELIA_HOST_BLOCKED=DOCKER_MISSING"
    exit 2
  fi
fi

if ! command -v curl >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y curl
  else
    echo "AURELIA_HOST_BLOCKED=CURL_MISSING"
    exit 2
  fi
fi

sudo systemctl enable --now docker
sudo install -d -m 700 "$ENV_DIR"
sudo install -d -m 700 "$DATA_DIR"
sudo install -d -m 755 "$RELEASE_ROOT"

if [ -f "$ENV_FILE" ]; then
  sudo chmod 600 "$ENV_FILE"
elif [ "$DEPLOYMENT_MODE" = "LIVE" ]; then
  echo "AURELIA_HOST_BLOCKED=MISSING_RUNTIME_SECRET_STORE"
  exit 2
else
  sudo tee "$ENV_FILE" >/dev/null <<'EOF'
PORT=8080
AURELIA_CONTINUOUS_RUNTIME=true
AURELIA_AUTONOMOUS_LOOP=false
AURELIA_VERIFY_DERIV_PUBLIC=true
AURELIA_VERIFY_DERIV_AUTH=false
AURELIA_RUN_ONCE=false
AURELIA_DEPLOYMENT_MODE=VERIFY_ONLY
AURELIA_PERSISTENT_WORKER_HEALTHY=true
AURELIA_READINESS_PATH=/tmp/aurelia/AURELIA_READINESS.json
AURELIA_JOURNAL_PATH=/tmp/aurelia/aurelia-events.ndjson
AURELIA_FEDERATION_JOURNAL_PATH=/tmp/aurelia/federation-events.ndjson
AURELIA_FEDERATION_LEASE_PATH=/tmp/aurelia/federation-leases.json
AURELIA_LEDGER_PATH=/tmp/aurelia/ledger.json
AURELIA_IDEMPOTENCY_PATH=/tmp/aurelia/idempotency.json
AURELIA_FENCE_PATH=/tmp/aurelia/executor-fence.txt
AURELIA_EXECUTION_JOURNAL_PATH=/tmp/aurelia/execution-events.ndjson
EOF
  sudo chmod 600 "$ENV_FILE"
fi

AUTH_CONFIGURED=false
if grep -Eq "^(DERIV_AUTH_TOKEN|DERIV_PAT)=.+$" "$ENV_FILE" \
  && grep -Eq "^(DERIV_EXPECTED_LOGINID|DERIV_AUTHORIZED_ACCOUNT_ID)=.+$" "$ENV_FILE" \
  && grep -Eq "^DERIV_EXPECTED_CURRENCY=.+$" "$ENV_FILE" \
  && grep -Eq "^DERIV_AUTH_MODE=(pat|oauth)$" "$ENV_FILE"; then
  if ! grep -Eq "^DERIV_AUTH_MODE=pat$" "$ENV_FILE" \
    || grep -Eq "^DERIV_APP_ID=.+$" "$ENV_FILE"; then
    AUTH_CONFIGURED=true
  fi
fi

if [ "$DEPLOYMENT_MODE" = "LIVE" ] && [ "$AUTH_CONFIGURED" != "true" ]; then
  grep -Eq "^(DERIV_AUTH_TOKEN|DERIV_PAT)=.+$" "$ENV_FILE" || {
    echo "AURELIA_HOST_BLOCKED=MISSING_DERIV_CONFIG:DERIV_AUTH_TOKEN_OR_DERIV_PAT"
    exit 2
  }
  grep -Eq "^(DERIV_EXPECTED_LOGINID|DERIV_AUTHORIZED_ACCOUNT_ID)=.+$" "$ENV_FILE" || {
    echo "AURELIA_HOST_BLOCKED=MISSING_DERIV_CONFIG:DERIV_EXPECTED_LOGINID_OR_DERIV_AUTHORIZED_ACCOUNT_ID"
    exit 2
  }
  grep -Eq "^DERIV_EXPECTED_CURRENCY=.+$" "$ENV_FILE" || {
    echo "AURELIA_HOST_BLOCKED=MISSING_DERIV_CONFIG:DERIV_EXPECTED_CURRENCY"
    exit 2
  }
  grep -Eq "^DERIV_AUTH_MODE=(pat|oauth)$" "$ENV_FILE" || {
    echo "AURELIA_HOST_BLOCKED=DERIV_AUTH_MODE_INVALID_OR_MISSING"
    exit 2
  }
  if grep -Eq "^DERIV_AUTH_MODE=pat$" "$ENV_FILE"; then
    grep -Eq "^DERIV_APP_ID=.+$" "$ENV_FILE" || {
      echo "AURELIA_HOST_BLOCKED=MISSING_DERIV_APP_ID"
      exit 2
    }
  fi
  echo "AURELIA_HOST_BLOCKED=DERIV_AUTH_CONFIGURATION_INVALID"
  exit 2
fi

if [ "$DEPLOYMENT_MODE" = "LIVE" ]; then
  AUTONOMOUS_LOOP=true
  VERIFY_DERIV_AUTH=true
  VERIFY_DERIV_PUBLIC=true
  FINAL_AUTH=true
  LIVE_EXECUTION=ENABLED
else
  AUTONOMOUS_LOOP=false
  VERIFY_DERIV_AUTH="$AUTH_CONFIGURED"
  VERIFY_DERIV_PUBLIC=true
  FINAL_AUTH=false
  LIVE_EXECUTION=BLOCKED
fi

sudo install -m 700 "$RELEASE_DIR/scripts/deploy/aurelia-watchdog.sh" /usr/local/sbin/aurelia-watchdog.sh
sudo tee /etc/systemd/system/aurelia-runtime-watchdog.service >/dev/null <<'EOF'
[Unit]
Description=AURELIA runtime health watchdog
After=docker.service
Requires=docker.service

[Service]
Type=simple
ExecStart=/usr/local/sbin/aurelia-watchdog.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable aurelia-runtime-watchdog.service

sudo docker build --pull --tag "$IMAGE" "$RELEASE_DIR"
sudo docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

sudo docker run --detach \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  --env AURELIA_DEPLOYMENT_MODE="$DEPLOYMENT_MODE" \
  --env AURELIA_AUTONOMOUS_LOOP="$AUTONOMOUS_LOOP" \
  --env AURELIA_VERIFY_DERIV_AUTH="$VERIFY_DERIV_AUTH" \
  --env AURELIA_VERIFY_DERIV_PUBLIC="$VERIFY_DERIV_PUBLIC" \
  --env AURELIA_RUN_ONCE=false \
  --env FINAL_EXECUTION_AUTHORIZATION="$FINAL_AUTH" \
  --env LIVE_EXECUTION="$LIVE_EXECUTION" \
  --env GITHUB_SHA="$SHA" \
  --mount "type=bind,src=$DATA_DIR,dst=/tmp/aurelia" \
  --publish 127.0.0.1:8080:8080 \
  "$IMAGE"

healthy=0
for attempt in $(seq 1 45); do
  if curl --fail --silent --show-error http://127.0.0.1:8080/health >/tmp/aurelia-health.json 2>/tmp/aurelia-health.err; then
    healthy=1
    break
  fi
  sleep 2
done

if [ "$healthy" -ne 1 ]; then
  echo "AURELIA_RUNTIME_HEALTH=FAILED"
  cat /tmp/aurelia-health.err 2>/dev/null || true
  sudo docker logs "$CONTAINER" 2>&1 | tail -100 || true
  exit 1
fi

health="$(cat /tmp/aurelia-health.json)"
python - "$DEPLOYMENT_MODE" <<'PY'
import json
import sys
from pathlib import Path

mode = sys.argv[1]
payload = json.loads(Path("/tmp/aurelia-health.json").read_text(encoding="utf-8"))
assert payload.get("liveness") is True, payload
if mode == "VERIFY_ONLY":
    assert payload.get("capital_can_open_new_exposure") is False, payload
PY
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx "AURELIA_AUTONOMOUS_LOOP=$AUTONOMOUS_LOOP"
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx "FINAL_EXECUTION_AUTHORIZATION=$FINAL_AUTH"
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx "LIVE_EXECUTION=$LIVE_EXECUTION"

image_id="$(sudo docker inspect "$CONTAINER" --format '{{.Image}}')"
runtime_source_hash="$(find "$RELEASE_DIR" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')"
runtime_health_hash="$(printf '%s' "$health" | sha256sum | awk '{print $1}')"
cat <<EOF | sudo tee "$DATA_DIR/DEPLOYMENT_LINEAGE.json" >/dev/null
{
  "schema": "aurelia.deployment_lineage.v2",
  "source_commit": "$SHA",
  "runtime_source_hash": "$runtime_source_hash",
  "runtime_artifact_hash": "$image_id",
  "runtime_health_hash": "$runtime_health_hash",
  "deployment_mode": "$DEPLOYMENT_MODE",
  "capital_protection": true,
  "live_execution": "$LIVE_EXECUTION",
  "final_execution_authorization": $FINAL_AUTH,
  "generated_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
sudo chmod 600 "$DATA_DIR/DEPLOYMENT_LINEAGE.json"

sudo systemctl restart aurelia-runtime-watchdog.service
sudo ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
printf '%s\n' "$SHA" | sudo tee "$DATA_DIR/DEPLOYED_SOURCE_SHA" >/dev/null
printf '%s\n' "$health" | sudo tee "$DATA_DIR/LAST_HEALTH.json" >/dev/null

echo "AURELIA_RUNTIME_DEPLOYMENT=SUCCESS"
echo "AURELIA_SOURCE_COMMIT=$SHA"
echo "AURELIA_DEPLOYMENT_MODE=$DEPLOYMENT_MODE"
echo "AURELIA_LIVE_EXECUTION=$LIVE_EXECUTION"
echo "AURELIA_FINAL_EXECUTION_AUTHORIZATION=$FINAL_AUTH"
