#!/usr/bin/env bash
set -euo pipefail

# Takes a screenshot of the focused monitor, blurs it, and launches Hyprlock.
# Tools needed (install yourself via sudo): hyprlock, grim, imagemagick, jq.

tmp_png="${XDG_RUNTIME_DIR:-/tmp}/hyprlock-bg.png"
output=""

if command -v windoesnot-hyprctl >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
    output="$(timeout --kill-after=1 5 windoesnot-hyprctl -j monitors | jq -r '.[] | select(.focused) | .name' | head -n1 || true)"
fi

if command -v grim >/dev/null 2>&1; then
    if [ -n "$output" ]; then
        timeout --kill-after=1 8 grim -o "$output" "$tmp_png"
    else
        timeout --kill-after=1 8 grim "$tmp_png"
    fi
else
    echo "grim is required to take the lock-screen screenshot." >&2
    exit 1
fi

if command -v magick >/dev/null 2>&1; then
    magick "$tmp_png" -blur 0x18 "$tmp_png"
elif command -v convert >/dev/null 2>&1; then
    convert "$tmp_png" -blur 0x18 "$tmp_png"
else
    echo "ImageMagick (magick/convert) is required to blur the screenshot." >&2
    exit 1
fi

exec hyprlock
