#!/usr/bin/env bash

set -euo pipefail

pictures_dir="$(xdg-user-dir PICTURES)"
mkdir -p -- "$pictures_dir"

window_json="$(windoesnot-hyprctl -j activewindow)"
geometry="$(jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"' <<<"$window_json")"
output_file="$pictures_dir/$(date +'%Y-%m-%d-%H%M%S-%N')_window.png"

grim -g "$geometry" "$output_file"
wl-copy --type image/png <"$output_file"
notify-send -a Screenshot -i "$output_file" "Screenshot gespeichert" "$output_file"
