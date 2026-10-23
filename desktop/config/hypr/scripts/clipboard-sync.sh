#!/usr/bin/env bash
# Bidirectional clipboard bridge: X11 (XWayland) <-> Wayland
# Workaround for Hyprland <0.54 where the built-in bridge is broken.
# Uses polling for X11->Wayland and wl-paste --watch for Wayland->X11.

set -euo pipefail

POLL_INTERVAL=0.3
x11_hash=""
wl_hash=""
lock=""

sync_x11_to_wl() {
    local content hash
    while true; do
        content=$(xclip -selection clipboard -o 2>/dev/null) || { sleep "$POLL_INTERVAL"; continue; }
        [[ -z "$content" ]] && { sleep "$POLL_INTERVAL"; continue; }

        hash=$(printf '%s' "$content" | md5sum)
        hash=${hash%% *}

        if [[ "$hash" != "$x11_hash" && "$hash" != "$lock" ]]; then
            x11_hash=$hash
            lock=$hash
            printf '%s' "$content" | wl-copy 2>/dev/null
            wl_hash=$hash
        fi

        sleep "$POLL_INTERVAL"
    done
}

sync_wl_to_x11() {
    wl-paste --watch bash -c '
        content=$(wl-paste 2>/dev/null) || exit 0
        [[ -z "$content" ]] && exit 0
        printf "%s" "$content" | xclip -selection clipboard 2>/dev/null
    ' &
    wait
}

cleanup() { kill -- -$$ 2>/dev/null; }
trap cleanup EXIT

sync_x11_to_wl &
sync_wl_to_x11 &
wait
