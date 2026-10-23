#!/bin/bash
STATE_FILE="/tmp/hyprdesk_hidden_windows"

if [ -f "$STATE_FILE" ]; then
    # Restore: alle Fenster zurück auf ihre ursprünglichen Workspaces
    while IFS='|' read -r address workspace; do
        windoesnot-hyprctl dispatch movetoworkspacesilent "${workspace},address:${address}"
    done < "$STATE_FILE"
    rm "$STATE_FILE"
else
    # Hide: alle sichtbaren Fenster (außer quickshell) nach special:minimized
    windoesnot-hyprctl clients -j | jq -r '.[] | select(.workspace.id > 0 and .class != "quickshell") | "\(.address)|\(.workspace.id)"' > "$STATE_FILE"
    while IFS='|' read -r address workspace; do
        windoesnot-hyprctl dispatch movetoworkspacesilent "special:minimized,address:${address}"
    done < "$STATE_FILE"
fi
