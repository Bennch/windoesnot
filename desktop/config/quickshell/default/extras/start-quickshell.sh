#!/bin/bash
# Start quickshell on the primary monitor (workspace 1's monitor)

export PATH="$HOME/.local/bin:$PATH"
LOGFILE="${XDG_RUNTIME_DIR:-/tmp}/start-quickshell.log"
echo "=== $(date) ===" > "$LOGFILE"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/default"

# Finish icon generation before loading QML. A failed refresh retains the last
# complete library (or the neutral bootstrap shipped with the desktop).
if ! bash "$CONFIG_DIR/generate-icon-map.sh" >> "$LOGFILE" 2>&1; then
    echo "Icon refresh failed; using the previous complete icon map" >> "$LOGFILE"
fi

# Wait for Hyprland to be fully initialized
for i in {1..10}; do
    if windoesnot-hyprctl monitors -j &>/dev/null; then
        echo "Hyprland ready after ${i} attempts" >> "$LOGFILE"
        break
    fi
    echo "Waiting for Hyprland... attempt $i" >> "$LOGFILE"
    sleep 0.5
done

# Get the monitor that workspace 1 is assigned to
PRIMARY_MONITOR=$(windoesnot-hyprctl workspaces -j 2>/dev/null | jq -r '.[] | select(.id == 1) | .monitor')
echo "Workspace 1 monitor: $PRIMARY_MONITOR" >> "$LOGFILE"

if [ -z "$PRIMARY_MONITOR" ] || [ "$PRIMARY_MONITOR" = "null" ]; then
    echo "Warning: Could not detect primary monitor from workspace 1, falling back to first monitor" >> "$LOGFILE"
    PRIMARY_MONITOR=$(windoesnot-hyprctl monitors -j 2>/dev/null | jq -r '.[0].name')
    echo "Fallback monitor: $PRIMARY_MONITOR" >> "$LOGFILE"
fi

# Get monitor geometry (x, y, width, height)
MONITOR_INFO=$(windoesnot-hyprctl monitors -j 2>/dev/null | jq -r ".[] | select(.name == \"$PRIMARY_MONITOR\")")
MONITOR_X=$(echo "$MONITOR_INFO" | jq -r '.x')
MONITOR_Y=$(echo "$MONITOR_INFO" | jq -r '.y')
MONITOR_WIDTH=$(echo "$MONITOR_INFO" | jq -r '((if (.transform % 2) == 1 then .height else .width end) / .scale) | round')
MONITOR_HEIGHT=$(echo "$MONITOR_INFO" | jq -r '((if (.transform % 2) == 1 then .width else .height end) / .scale) | round')

echo "Monitor geometry: x=$MONITOR_X y=$MONITOR_Y w=$MONITOR_WIDTH h=$MONITOR_HEIGHT" >> "$LOGFILE"

# Calculate center of the monitor
CENTER_X=$((MONITOR_X + MONITOR_WIDTH / 2))
CENTER_Y=$((MONITOR_Y + MONITOR_HEIGHT / 2))

echo "Moving cursor to: $CENTER_X, $CENTER_Y" >> "$LOGFILE"

# Move cursor to center of primary monitor
windoesnot-hyprctl dispatch movecursor $CENTER_X $CENTER_Y 2>&1 >> "$LOGFILE"

# Small delay to ensure cursor is moved before starting quickshell
sleep 0.2

# Qt's gtk3 platform theme reads the icon theme once at startup. Settings.qml
# applies it via gsettings only after loading, so a new user's first session
# would otherwise resolve themed icons from the fallback theme.
ICON_THEME=$(sed -n 's/^iconTheme=//p' "$CONFIG_DIR/settings.txt" 2>/dev/null | tail -n 1)
ICON_THEME=${ICON_THEME:-Win11}  # default of Settings.qml iconTheme
gsettings set org.gnome.desktop.interface icon-theme "$ICON_THEME" >> "$LOGFILE" 2>&1 || true

# Native QML modules (LocalTerminal): the packaged build first, so it always
# matches the installed Qt; a per-user copy covers non-packaged installs.
for dir in "$CONFIG_DIR/widgets/terminalmodule" /usr/lib/windoesnot; do
    [ -d "$dir/LocalTerminal" ] && QML_IMPORT_PATH="$dir${QML_IMPORT_PATH:+:$QML_IMPORT_PATH}"
done
export QML_IMPORT_PATH

echo "Starting quickshell..." >> "$LOGFILE"

# Start quickshell with the same environment as before
exec env QT_QPA_PLATFORMTHEME=gtk3 quickshell --path "$CONFIG_DIR/shell.qml" >> "$LOGFILE" 2>&1
