#!/usr/bin/env bash
# Keep Avahi as the only mDNS responder. Config files are installed once so
# rerunning image/install finalization never overwrites local administrator edits.
set -euo pipefail

root=${1:-/}
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/config" && pwd)

install_once() {
    local source=$1 target="$root/$2"
    if [[ -e $target || -L $target ]]; then
        return
    fi
    install -D -m 0644 "$source_dir/$source" "$target"
}

install_once resolved.conf.d/90-windoesnot-mdns.conf etc/systemd/resolved.conf.d/90-windoesnot-mdns.conf
install_once NetworkManager/conf.d/90-windoesnot-mdns.conf etc/NetworkManager/conf.d/90-windoesnot-mdns.conf
