#!/usr/bin/env bash
# Ghostty's GTK4 renderer creates its own EGL context independently of
# Hyprland's own rendering; on virtio-gpu (VirGL) that context creation
# fails outright (EGL BadMatch), closing the window a moment after it
# opens, separately from the compositor-level dmabuf quirk already
# handled in desktop/config/hypr/lua/init.lua. Same virtio-vendor
# detection as there: force software rendering only then, leave real
# GPUs on their normal accelerated path.
set -euo pipefail
for vendor in /sys/class/drm/card*/device/vendor; do
    if [[ "$(cat "$vendor" 2>/dev/null)" == "0x1af4" ]]; then
        export LIBGL_ALWAYS_SOFTWARE=1
        break
    fi
done
exec /usr/bin/ghostty "$@"
