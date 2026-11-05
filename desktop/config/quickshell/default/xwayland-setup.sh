#!/bin/bash
# XWayland cursor fix for Hyprland
# XWayland apps read cursor size from xrdb, not from environment variables

XRESOURCES="$HOME/.Xresources"
CURSOR_SIZE=24

# Create .Xresources if it doesn't exist or doesn't contain Xcursor.size
if [ ! -f "$XRESOURCES" ] || ! grep -q "Xcursor.size" "$XRESOURCES"; then
    echo "Xcursor.size: $CURSOR_SIZE" >> "$XRESOURCES"
fi

# Load into X resources database
xrdb -merge "$XRESOURCES"

# XWayland shows its bare "X" root cursor over the empty desktop unless a real
# default cursor is set.
command -v xsetroot >/dev/null 2>&1 && xsetroot -cursor_name left_ptr
