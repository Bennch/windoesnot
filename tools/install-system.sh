#!/usr/bin/env bash
# Install the portable command names without replacing host packages/configuration.
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if (( EUID != 0 )); then echo 'Run with sudo.' >&2; exit 1; fi
for command in windoesnot-hyprctl windoesnot-settings windoesnot-session windoesnot-initialize windoesnot-first-start windoesnot-layout windoesnot-restart-shell; do
    install -Dm755 "$project/desktop/bin/$command" "/usr/local/bin/$command"
done
if [[ -x "$project/build/components/bin/snappy-switcher" ]]; then
    install -Dm755 "$project/build/components/bin/snappy-switcher" /usr/local/bin/snappy-switcher
fi

# Read-only settings queries (including battery status) use the same path as
# packaged installations. Preserve an installed package's managed helper.
helper=/usr/lib/windoesnot/system_tools.py
if ! pacman -Qo "$helper" >/dev/null 2>&1; then
    install -Dm755 "$project/desktop/lib/windoesnot/system_tools.py" "$helper"
    install -Dm644 "$project/desktop/share/polkit-1/actions/org.windoesnot.system.policy" /usr/share/polkit-1/actions/org.windoesnot.system.policy
fi

# Local source installs need the same wallpaper assets as packaged installations.
for background in "$project"/desktop/share/backgrounds/windoesnot/*.jpg; do
    target="/usr/share/backgrounds/windoesnot/$(basename -- "$background")"
    if ! pacman -Qo "$target" >/dev/null 2>&1; then
        install -Dm644 "$background" "$target"
    fi
done
