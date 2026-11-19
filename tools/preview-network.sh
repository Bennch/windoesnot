#!/bin/bash
# Build the Network app from network/ and swap it into the host preview (network-preview/), so the
# `windoesnot-network` wrapper on the host starts the current source. Debug build by default (--release for release).
# The running binary is replaced via copy + mv -f (a running file is busy). Never touches packages or the host firewall.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
profile=debug; flags=()
[[ "${1:-}" == --release ]] && { profile=release; flags=(--release); }
cd "$root/network"
cargo build --offline "${flags[@]}"
install -d "$root/network-preview"
tmp=$(mktemp "$root/network-preview/.windoesnot-network.XXXXXX")
cp "target/$profile/windoesnot-network" "$tmp"
chmod 755 "$tmp"
mv -f "$tmp" "$root/network-preview/windoesnot-network"
echo "network-preview updated ($profile) from $(git -C "$root/network" rev-parse --short HEAD)$(git -C "$root/network" diff --quiet || echo '+uncommitted')"
echo "Start: RUST_LOG=debug windoesnot-network   (log: ~/.cache/windoesnot-network-debug.log via tools/preview-network.sh run)"
if [[ "${1:-}" == run || "${2:-}" == run ]]; then
  mkdir -p ~/.cache
  RUST_LOG=${RUST_LOG:-debug} exec "$root/network-preview/windoesnot-network" 2>>~/.cache/windoesnot-network-debug.log
fi
