#!/usr/bin/env bash
set -euo pipefail
if [[ -e /etc/windoesnot/lite-mode ]]; then exec /usr/bin/foot "$@"; fi
for vendor in /sys/class/drm/card*/device/vendor; do
    if [[ "$(cat "$vendor" 2>/dev/null)" == "0x1af4" ]]; then
        export LIBGL_ALWAYS_SOFTWARE=1
        break
    fi
done
exec /usr/bin/ghostty "$@"
