#!/usr/bin/env bash
set -euo pipefail

# Governed source acquisition only. This script never executes external source.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${ROOT}/.aurelia/external-tools/agent-eyes"
mkdir -p "${DEST}"

clone_pinned() {
  local name="$1"
  local url="$2"
  local commit="$3"
  local target="${DEST}/${name}"

  rm -rf "${target}"
  git init -q "${target}"
  git -C "${target}" remote add origin "${url}"
  git -C "${target}" fetch --depth 1 origin "${commit}"
  git -C "${target}" checkout --detach -q "${commit}"
  printf '%s %s\n' "${name}" "$(git -C "${target}" rev-parse HEAD)"
}

clone_pinned "16-eyes" "https://github.com/kigiela/16-eyes.git" "261d2b381b3ff6e819456d4c9aa40b9dff56b7d3"
clone_pinned "visual-eyes" "https://github.com/DeHor-Labs/visual-eyes.git" "c2ff5067353c6dbbcd09a4f0630147a042ba51e7"
clone_pinned "Touchpoint" "https://github.com/Touchpoint-Labs/Touchpoint.git" "f512227621c3e0f4e5675e4e7dbed7aaebdcc76b"

echo "Pinned external sources acquired under ${DEST}."
echo "No external code was executed by this script."
