#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${ROOT}/.aurelia/external-tools/gstack-federation"
mkdir -p "${DEST}"

clone_pinned() {
  local name="$1" url="$2" commit="$3" target="${DEST}/${name}"
  rm -rf "${target}"
  git init -q "${target}"
  git -C "${target}" remote add origin "${url}"
  git -C "${target}" fetch --depth 1 origin "${commit}"
  git -C "${target}" checkout --detach -q "${commit}"
  printf '%-35s %s\n' "${name}" "$(git -C "${target}" rev-parse HEAD)"
}

clone_pinned "gstack" "https://github.com/garrytan/gstack.git" "10315cf44d1ea13e3ae4821841873afbf7807935"
clone_pinned "flow-kit" "https://github.com/rihebty/flow-kit.git" "9b5dda7206ae841230f118348d660ad8d0ae2830"
clone_pinned "gstack-windows-port" "https://github.com/thanh-abaii/gstack-windows-port.git" "26937232ba2141c6bcf6ffdd8e0822163b475d63"
clone_pinned "gstack-ko" "https://github.com/lucas-flatwhite/gstack-ko.git" "18bacc475cb5f7bf57647f4fbb647415c65c2303"
clone_pinned "ostack-saas" "https://github.com/mr-daedalium/ostack-saas.git" "a67256db4451f2d085370cfc36ebe091211b8e7b"
clone_pinned "Ahacad-gstack" "https://github.com/Ahacad/gstack.git" "f873a4d051b16a6652a3463cd1cd060dde86a24b"
clone_pinned "gstack-auto" "https://github.com/loperanger7/gstack-auto.git" "17bf2a025c175b899e7d30be1ab4e658fd4ae04f"

echo "Pinned gstack workflow sources acquired."
echo "No external source is executed by this installer."
