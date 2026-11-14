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
    # Slow hardware (software rendering) needs well over 3 s for the layer to
    # appear; poll until the deadline instead of killing a still-starting child.
    deadline=$(( $(date +%s%N) / 1000000 + $(awk -v s="${WINDOESNOT_HYPRDESK_CHECK_DELAY:-40}" 'BEGIN{printf "%d", s*1000}') ))
    ready=0
    while [ $(( $(date +%s%N) / 1000000 )) -lt "$deadline" ]; do
        kill -0 "$child" 2>/dev/null || break
        if layer_ready; then ready=1; break; fi
        sleep 0.5
    done
    if [ "$ready" = 1 ] || layer_ready; then
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
