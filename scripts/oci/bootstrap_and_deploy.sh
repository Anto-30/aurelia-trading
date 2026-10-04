#!/usr/bin/env bash
set -euo pipefail

SHA="\${1:?source commit SHA required}"
APP_ROOT="/opt/aurelia"
RELEASE_ROOT="$APP_ROOT/releases"
RELEASE_DIR="$RELEASE_ROOT/$SHA"
CURRENT_LINK="$APP_ROOT/current"
ENV_DIR="/etc/aurelia"
ENV_FILE="$ENV_DIR/aurelia.env"
DATA_DIR="/var/lib/aurelia"
IMAGE="aurelia-runtime:$SHA"
CONTAINER="aurelia-runtime"

if ! command -v sudo >/dev/null 2>&1; then
  echo "OCI_HOST_BLOCKED=PASSWORDLESS_SUDO_REQUIRED"
  exit 2
fi

sudo -n true

if [ ! -d "$RELEASE_DIR" ]; then
  echo "OCI_RELEASE_BLOCKED=MISSING_RELEASE_DIR"
  exit 2
fi

LOCK_FILE="$RELEASE_DIR/config/LIVE_LOCK.yaml"
test -f "$LOCK_FILE"

grep -Eq '^live_trading_enabled:[[:space:]]*false[[:space:]]*$' "$LOCK_FILE"
grep -Eq '^FINAL_EXECUTION_AUTHORIZATION:[[:space:]]*false[[:space:]]*$' "$LOCK_FILE"
grep -Eq '^LIVE_EXECUTION:[[:space:]]*BLOCKED[[:space:]]*$' "$LOCK_FILE"
grep -Eq '^capital_plane_mode:[[:space:]]*VERIFY_ONLY[[:space:]]*$' "$LOCK_FILE"

if ! command -v docker >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io curl
  else
    echo "OCI_HOST_BLOCKED=DOCKER_MISSING_INSTALL_DOCKER_ON_UBUNTU_OR_PREINSTALL"
    exit 2
  fi
fi

if ! command -v curl >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y curl
  else
    echo "OCI_HOST_BLOCKED=CURL_MISSING"
    exit 2
  fi
fi

sudo systemctl enable --now docker

sudo install -d -m 700 "$ENV_DIR"
sudo install -d -m 700 "$DATA_DIR"
sudo install -d -m 755 "$RELEASE_ROOT"

DEPLOYMENT_MODE="${AURELIA_DEPLOYMENT_MODE:-VERIFY_ONLY}"

case "$DEPLOYMENT_MODE" in
  VERIFY_ONLY)
    grep -Eq '^live_trading_enabled:[[:space:]]*false[[:space:]]*
sudo docker build --pull --tag "$IMAGE" "$RELEASE_DIR"

sudo docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

sudo docker run --detach \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  --env AURELIA_AUTONOMOUS_LOOP=false \
  --env AURELIA_VERIFY_DERIV_AUTH=false \
  --env AURELIA_VERIFY_DERIV_PUBLIC=false \
  --env AURELIA_RUN_ONCE=false \
  --env FINAL_EXECUTION_AUTHORIZATION=false \
  --env LIVE_EXECUTION=BLOCKED \
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
  echo "OCI_RUNTIME_HEALTH=FAILED"
  cat /tmp/aurelia-health.err 2>/dev/null || true
  sudo docker logs "$CONTAINER" 2>&1 | tail -100 || true
  exit 1
fi

health="$(cat /tmp/aurelia-health.json)"
printf '%s\n' "$health" | grep -q '"liveness": true'
printf '%s\n' "$health" | grep -q '"capital_can_open_new_exposure": false'

sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx "AURELIA_AUTONOMOUS_LOOP=$AUTONOMOUS_LOOP"
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx "AURELIA_VERIFY_DERIV_AUTH=$VERIFY_DERIV_AUTH"

sudo ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
printf '%s\n' "$SHA" | sudo tee "$DATA_DIR/DEPLOYED_SOURCE_SHA" >/dev/null
printf '%s\n' "$health" | sudo tee "$DATA_DIR/LAST_HEALTH.json" >/dev/null

echo "OCI_RUNTIME_DEPLOYMENT=SUCCESS"
echo "OCI_SOURCE_COMMIT=$SHA"
echo "OCI_DEPLOYMENT_MODE=$DEPLOYMENT_MODE"
echo "OCI_LIVE_EXECUTION=$LIVE_EXECUTION"
echo "OCI_FINAL_EXECUTION_AUTHORIZATION=$FINAL_AUTH"
 "$LOCK_FILE"
    grep -Eq '^FINAL_EXECUTION_AUTHORIZATION:[[:space:]]*false[[:space:]]*
sudo docker build --pull --tag "$IMAGE" "$RELEASE_DIR"

sudo docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

sudo docker run --detach \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  --env AURELIA_AUTONOMOUS_LOOP=false \
  --env AURELIA_VERIFY_DERIV_AUTH=false \
  --env AURELIA_VERIFY_DERIV_PUBLIC=false \
  --env AURELIA_RUN_ONCE=false \
  --env FINAL_EXECUTION_AUTHORIZATION=false \
  --env LIVE_EXECUTION=BLOCKED \
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
  echo "OCI_RUNTIME_HEALTH=FAILED"
  cat /tmp/aurelia-health.err 2>/dev/null || true
  sudo docker logs "$CONTAINER" 2>&1 | tail -100 || true
  exit 1
fi

health="$(cat /tmp/aurelia-health.json)"
printf '%s\n' "$health" | grep -q '"liveness": true'
printf '%s\n' "$health" | grep -q '"capital_can_open_new_exposure": false'

sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_AUTONOMOUS_LOOP=false'
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_VERIFY_DERIV_AUTH=false'

sudo ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
printf '%s\n' "$SHA" | sudo tee "$DATA_DIR/DEPLOYED_SOURCE_SHA" >/dev/null
printf '%s\n' "$health" | sudo tee "$DATA_DIR/LAST_HEALTH.json" >/dev/null

echo "OCI_RUNTIME_DEPLOYMENT=SUCCESS"
echo "OCI_SOURCE_COMMIT=$SHA"
echo "OCI_LIVE_EXECUTION=BLOCKED"
echo "OCI_FINAL_EXECUTION_AUTHORIZATION=false"
 "$LOCK_FILE"
    grep -Eq '^LIVE_EXECUTION:[[:space:]]*BLOCKED[[:space:]]*
sudo docker build --pull --tag "$IMAGE" "$RELEASE_DIR"

sudo docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

sudo docker run --detach \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  --env AURELIA_AUTONOMOUS_LOOP=false \
  --env AURELIA_VERIFY_DERIV_AUTH=false \
  --env AURELIA_VERIFY_DERIV_PUBLIC=false \
  --env AURELIA_RUN_ONCE=false \
  --env FINAL_EXECUTION_AUTHORIZATION=false \
  --env LIVE_EXECUTION=BLOCKED \
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
  echo "OCI_RUNTIME_HEALTH=FAILED"
  cat /tmp/aurelia-health.err 2>/dev/null || true
  sudo docker logs "$CONTAINER" 2>&1 | tail -100 || true
  exit 1
fi

health="$(cat /tmp/aurelia-health.json)"
printf '%s\n' "$health" | grep -q '"liveness": true'
printf '%s\n' "$health" | grep -q '"capital_can_open_new_exposure": false'

sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_AUTONOMOUS_LOOP=false'
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_VERIFY_DERIV_AUTH=false'

sudo ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
printf '%s\n' "$SHA" | sudo tee "$DATA_DIR/DEPLOYED_SOURCE_SHA" >/dev/null
printf '%s\n' "$health" | sudo tee "$DATA_DIR/LAST_HEALTH.json" >/dev/null

echo "OCI_RUNTIME_DEPLOYMENT=SUCCESS"
echo "OCI_SOURCE_COMMIT=$SHA"
echo "OCI_LIVE_EXECUTION=BLOCKED"
echo "OCI_FINAL_EXECUTION_AUTHORIZATION=false"
 "$LOCK_FILE"
    grep -Eq '^capital_plane_mode:[[:space:]]*VERIFY_ONLY[[:space:]]*
sudo docker build --pull --tag "$IMAGE" "$RELEASE_DIR"

sudo docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

sudo docker run --detach \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  --env AURELIA_AUTONOMOUS_LOOP=false \
  --env AURELIA_VERIFY_DERIV_AUTH=false \
  --env AURELIA_VERIFY_DERIV_PUBLIC=false \
  --env AURELIA_RUN_ONCE=false \
  --env FINAL_EXECUTION_AUTHORIZATION=false \
  --env LIVE_EXECUTION=BLOCKED \
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
  echo "OCI_RUNTIME_HEALTH=FAILED"
  cat /tmp/aurelia-health.err 2>/dev/null || true
  sudo docker logs "$CONTAINER" 2>&1 | tail -100 || true
  exit 1
fi

health="$(cat /tmp/aurelia-health.json)"
printf '%s\n' "$health" | grep -q '"liveness": true'
printf '%s\n' "$health" | grep -q '"capital_can_open_new_exposure": false'

sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_AUTONOMOUS_LOOP=false'
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_VERIFY_DERIV_AUTH=false'

sudo ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
printf '%s\n' "$SHA" | sudo tee "$DATA_DIR/DEPLOYED_SOURCE_SHA" >/dev/null
printf '%s\n' "$health" | sudo tee "$DATA_DIR/LAST_HEALTH.json" >/dev/null

echo "OCI_RUNTIME_DEPLOYMENT=SUCCESS"
echo "OCI_SOURCE_COMMIT=$SHA"
echo "OCI_LIVE_EXECUTION=BLOCKED"
echo "OCI_FINAL_EXECUTION_AUTHORIZATION=false"
 "$LOCK_FILE"
    ;;
  LIVE)
    grep -Eq '^live_trading_enabled:[[:space:]]*true[[:space:]]*
sudo docker build --pull --tag "$IMAGE" "$RELEASE_DIR"

sudo docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

sudo docker run --detach \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  --env AURELIA_AUTONOMOUS_LOOP=false \
  --env AURELIA_VERIFY_DERIV_AUTH=false \
  --env AURELIA_VERIFY_DERIV_PUBLIC=false \
  --env AURELIA_RUN_ONCE=false \
  --env FINAL_EXECUTION_AUTHORIZATION=false \
  --env LIVE_EXECUTION=BLOCKED \
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
  echo "OCI_RUNTIME_HEALTH=FAILED"
  cat /tmp/aurelia-health.err 2>/dev/null || true
  sudo docker logs "$CONTAINER" 2>&1 | tail -100 || true
  exit 1
fi

health="$(cat /tmp/aurelia-health.json)"
printf '%s\n' "$health" | grep -q '"liveness": true'
printf '%s\n' "$health" | grep -q '"capital_can_open_new_exposure": false'

sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_AUTONOMOUS_LOOP=false'
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_VERIFY_DERIV_AUTH=false'

sudo ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
printf '%s\n' "$SHA" | sudo tee "$DATA_DIR/DEPLOYED_SOURCE_SHA" >/dev/null
printf '%s\n' "$health" | sudo tee "$DATA_DIR/LAST_HEALTH.json" >/dev/null

echo "OCI_RUNTIME_DEPLOYMENT=SUCCESS"
echo "OCI_SOURCE_COMMIT=$SHA"
echo "OCI_LIVE_EXECUTION=BLOCKED"
echo "OCI_FINAL_EXECUTION_AUTHORIZATION=false"
 "$LOCK_FILE"
    grep -Eq '^FINAL_EXECUTION_AUTHORIZATION:[[:space:]]*true[[:space:]]*
sudo docker build --pull --tag "$IMAGE" "$RELEASE_DIR"

sudo docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

sudo docker run --detach \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  --env AURELIA_AUTONOMOUS_LOOP=false \
  --env AURELIA_VERIFY_DERIV_AUTH=false \
  --env AURELIA_VERIFY_DERIV_PUBLIC=false \
  --env AURELIA_RUN_ONCE=false \
  --env FINAL_EXECUTION_AUTHORIZATION=false \
  --env LIVE_EXECUTION=BLOCKED \
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
  echo "OCI_RUNTIME_HEALTH=FAILED"
  cat /tmp/aurelia-health.err 2>/dev/null || true
  sudo docker logs "$CONTAINER" 2>&1 | tail -100 || true
  exit 1
fi

health="$(cat /tmp/aurelia-health.json)"
printf '%s\n' "$health" | grep -q '"liveness": true'
printf '%s\n' "$health" | grep -q '"capital_can_open_new_exposure": false'

sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_AUTONOMOUS_LOOP=false'
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_VERIFY_DERIV_AUTH=false'

sudo ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
printf '%s\n' "$SHA" | sudo tee "$DATA_DIR/DEPLOYED_SOURCE_SHA" >/dev/null
printf '%s\n' "$health" | sudo tee "$DATA_DIR/LAST_HEALTH.json" >/dev/null

echo "OCI_RUNTIME_DEPLOYMENT=SUCCESS"
echo "OCI_SOURCE_COMMIT=$SHA"
echo "OCI_LIVE_EXECUTION=BLOCKED"
echo "OCI_FINAL_EXECUTION_AUTHORIZATION=false"
 "$LOCK_FILE"
    grep -Eq '^LIVE_EXECUTION:[[:space:]]*ENABLED[[:space:]]*
sudo docker build --pull --tag "$IMAGE" "$RELEASE_DIR"

sudo docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

sudo docker run --detach \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  --env AURELIA_AUTONOMOUS_LOOP=false \
  --env AURELIA_VERIFY_DERIV_AUTH=false \
  --env AURELIA_VERIFY_DERIV_PUBLIC=false \
  --env AURELIA_RUN_ONCE=false \
  --env FINAL_EXECUTION_AUTHORIZATION=false \
  --env LIVE_EXECUTION=BLOCKED \
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
  echo "OCI_RUNTIME_HEALTH=FAILED"
  cat /tmp/aurelia-health.err 2>/dev/null || true
  sudo docker logs "$CONTAINER" 2>&1 | tail -100 || true
  exit 1
fi

health="$(cat /tmp/aurelia-health.json)"
printf '%s\n' "$health" | grep -q '"liveness": true'
printf '%s\n' "$health" | grep -q '"capital_can_open_new_exposure": false'

sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_AUTONOMOUS_LOOP=false'
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_VERIFY_DERIV_AUTH=false'

sudo ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
printf '%s\n' "$SHA" | sudo tee "$DATA_DIR/DEPLOYED_SOURCE_SHA" >/dev/null
printf '%s\n' "$health" | sudo tee "$DATA_DIR/LAST_HEALTH.json" >/dev/null

echo "OCI_RUNTIME_DEPLOYMENT=SUCCESS"
echo "OCI_SOURCE_COMMIT=$SHA"
echo "OCI_LIVE_EXECUTION=BLOCKED"
echo "OCI_FINAL_EXECUTION_AUTHORIZATION=false"
 "$LOCK_FILE"
    grep -Eq '^capital_plane_mode:[[:space:]]*LIVE[[:space:]]*
sudo docker build --pull --tag "$IMAGE" "$RELEASE_DIR"

sudo docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

sudo docker run --detach \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  --env AURELIA_AUTONOMOUS_LOOP=false \
  --env AURELIA_VERIFY_DERIV_AUTH=false \
  --env AURELIA_VERIFY_DERIV_PUBLIC=false \
  --env AURELIA_RUN_ONCE=false \
  --env FINAL_EXECUTION_AUTHORIZATION=false \
  --env LIVE_EXECUTION=BLOCKED \
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
  echo "OCI_RUNTIME_HEALTH=FAILED"
  cat /tmp/aurelia-health.err 2>/dev/null || true
  sudo docker logs "$CONTAINER" 2>&1 | tail -100 || true
  exit 1
fi

health="$(cat /tmp/aurelia-health.json)"
printf '%s\n' "$health" | grep -q '"liveness": true'
printf '%s\n' "$health" | grep -q '"capital_can_open_new_exposure": false'

sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_AUTONOMOUS_LOOP=false'
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_VERIFY_DERIV_AUTH=false'

sudo ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
printf '%s\n' "$SHA" | sudo tee "$DATA_DIR/DEPLOYED_SOURCE_SHA" >/dev/null
printf '%s\n' "$health" | sudo tee "$DATA_DIR/LAST_HEALTH.json" >/dev/null

echo "OCI_RUNTIME_DEPLOYMENT=SUCCESS"
echo "OCI_SOURCE_COMMIT=$SHA"
echo "OCI_LIVE_EXECUTION=BLOCKED"
echo "OCI_FINAL_EXECUTION_AUTHORIZATION=false"
 "$LOCK_FILE"
    ;;
  *)
    echo "OCI_RUNTIME_BLOCKED=INVALID_DEPLOYMENT_MODE"
    exit 2
    ;;
esac

if [ -f /tmp/aurelia-runtime.env ]; then
  sudo install -m 600 /tmp/aurelia-runtime.env "$ENV_FILE"
  rm -f /tmp/aurelia-runtime.env
elif [ ! -f "$ENV_FILE" ]; then
  sudo tee "$ENV_FILE" >/dev/null <<'EOF'
PORT=8080
AURELIA_CONTINUOUS_RUNTIME=true
AURELIA_AUTONOMOUS_LOOP=false
AURELIA_VERIFY_DERIV_PUBLIC=false
AURELIA_VERIFY_DERIV_AUTH=false
AURELIA_RUN_ONCE=false
AURELIA_JOURNAL_PATH=/tmp/aurelia/aurelia-events.ndjson
AURELIA_FEDERATION_JOURNAL_PATH=/tmp/aurelia/federation-events.ndjson
AURELIA_FEDERATION_LEASE_PATH=/tmp/aurelia/federation-leases.json
AURELIA_LEDGER_PATH=/tmp/aurelia/ledger.json
AURELIA_IDEMPOTENCY_PATH=/tmp/aurelia/idempotency.json
AURELIA_FENCE_PATH=/tmp/aurelia/executor-fence.txt
AURELIA_EXECUTION_JOURNAL_PATH=/tmp/aurelia/execution-events.ndjson
AURELIA_DEPLOYMENT_MODE=VERIFY_ONLY
EOF
  sudo chmod 600 "$ENV_FILE"
fi

sudo docker build --pull --tag "$IMAGE" "$RELEASE_DIR"

sudo docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

sudo docker run --detach \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  --env AURELIA_AUTONOMOUS_LOOP=false \
  --env AURELIA_VERIFY_DERIV_AUTH=false \
  --env AURELIA_VERIFY_DERIV_PUBLIC=false \
  --env AURELIA_RUN_ONCE=false \
  --env FINAL_EXECUTION_AUTHORIZATION=false \
  --env LIVE_EXECUTION=BLOCKED \
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
  echo "OCI_RUNTIME_HEALTH=FAILED"
  cat /tmp/aurelia-health.err 2>/dev/null || true
  sudo docker logs "$CONTAINER" 2>&1 | tail -100 || true
  exit 1
fi

health="$(cat /tmp/aurelia-health.json)"
printf '%s\n' "$health" | grep -q '"liveness": true'
printf '%s\n' "$health" | grep -q '"capital_can_open_new_exposure": false'

sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_AUTONOMOUS_LOOP=false'
sudo docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -qx 'AURELIA_VERIFY_DERIV_AUTH=false'

sudo ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
printf '%s\n' "$SHA" | sudo tee "$DATA_DIR/DEPLOYED_SOURCE_SHA" >/dev/null
printf '%s\n' "$health" | sudo tee "$DATA_DIR/LAST_HEALTH.json" >/dev/null

echo "OCI_RUNTIME_DEPLOYMENT=SUCCESS"
echo "OCI_SOURCE_COMMIT=$SHA"
echo "OCI_LIVE_EXECUTION=BLOCKED"
echo "OCI_FINAL_EXECUTION_AUTHORIZATION=false"
