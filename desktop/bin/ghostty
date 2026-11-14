#!/usr/bin/env bash
# Route every Ghostty launch through Foot on systems that opted into Lite Mode.
set -euo pipefail
if [[ -e /etc/windoesnot/lite-mode && -x /usr/bin/foot ]]; then
    # Foot does not know Ghostty's options: the desktop entry passes --gtk-single-instance=false, which made
    # Foot exit at once (taskbar launcher dead on a 2010 laptop, 2026-11-14). Translate what has an
    # equivalent and drop the rest. The window keeps Ghostty's app id so it groups with the pinned icon.
    app_id=com.mitchellh.ghostty
    args=()
    for argument in "$@"; do
        case $argument in
            --class=*) app_id=${argument#--class=};;
            --gtk-*|--wait-after-command*|--font-size=*|--window-*|--quit-after-last-window-closed*) ;;
            *) args+=("$argument");;
        esac
    done
    exec /usr/bin/foot --app-id="$app_id" "${args[@]}"
fi
for vendor in /sys/class/drm/card*/device/vendor; do
    if [[ "$(cat "$vendor" 2>/dev/null)" == "0x1af4" ]]; then
        export LIBGL_ALWAYS_SOFTWARE=1
        break
    fi
done
exec /usr/bin/ghostty "$@"
