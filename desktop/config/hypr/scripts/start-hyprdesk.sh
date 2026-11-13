#!/usr/bin/env bash
# Keep the desktop icon layer alive and retry startup races (e.g. GTK layer
# surface created before Hyprland finished publishing outputs).
set -u
logfile="${XDG_RUNTIME_DIR:-/tmp}/start-hyprdesk.log"
hyprctl_bin=${WINDOESNOT_HYPRCTL:-windoesnot-hyprctl}
desk=${WINDOESNOT_HYPRDESK:-$HOME/.config/hyprdesk/hyprdesk.py}
layer_ready() {
    "$hyprctl_bin" layers -j 2>/dev/null | grep -q 'hyprdesk-desktop'
}
for attempt in 1 2 3; do
    printf 'start attempt %s: %s\n' "$attempt" "$(date)" >> "$logfile"
    LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so "$desk" >> "$logfile" 2>&1 &
    child=$!
    sleep "${WINDOESNOT_HYPRDESK_CHECK_DELAY:-3}"
    if layer_ready; then
        printf 'desktop layer found on attempt %s\n' "$attempt" >> "$logfile"
        wait "$child"
        exit $?
    fi
    printf 'desktop layer missing on attempt %s; restarting\n' "$attempt" >> "$logfile"
    kill "$child" 2>/dev/null || true
    wait "$child" 2>/dev/null || true
    sleep 1
done
printf 'desktop layer still missing after 3 attempts\n' >> "$logfile"
exit 1
