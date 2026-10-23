#!/usr/bin/env bash
# Install the portable command names without replacing host packages/configuration.
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if (( EUID != 0 )); then echo 'Run with sudo.' >&2; exit 1; fi
for command in windoesnot-hyprctl windoesnot-settings windoesnot-session windoesnot-initialize windoesnot-first-start windoesnot-layout; do
    install -Dm755 "$project/desktop/bin/$command" "/usr/local/bin/$command"
done
if [[ -x "$project/build/components/bin/snappy-switcher" ]]; then
    install -Dm755 "$project/build/components/bin/snappy-switcher" /usr/local/bin/snappy-switcher
fi
