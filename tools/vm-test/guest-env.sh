U=1000; sig=$(ls /run/user/$U/hypr | head -1)
G() { runuser -u vmtest -- env XDG_RUNTIME_DIR=/run/user/$U WAYLAND_DISPLAY=wayland-1 HYPRLAND_INSTANCE_SIGNATURE=$sig DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$U/bus "$@"; }
