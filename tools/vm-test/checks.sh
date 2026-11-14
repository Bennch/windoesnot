#!/bin/bash
U=$(ls /home | head -1); N=$(id -u $U); sig=$(ls /run/user/$N/hypr | head -1)
H(){ runuser -u $U -- env XDG_RUNTIME_DIR=/run/user/$N WAYLAND_DISPLAY=wayland-1 HYPRLAND_INSTANCE_SIGNATURE=$sig DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$N/bus "$@"; }
echo "== user $U"; echo "== versions"; pacman -Q 2>/dev/null | grep -E "^windoesnot-(desktop|tools|plugins|components) |^swaybg|^foot |^hyprland |^hyprpaper"
echo "== failed units"; systemctl --failed --no-legend; echo "old-gpu unit: $(systemctl is-enabled windoesnot-old-gpu.service 2>&1)"
echo "== bootloader"; bootctl status 2>/dev/null | grep -E "Product" | head -1; ls /boot/grub 2>/dev/null | head -1
echo "== hyprland"; echo "configerrors: [$(H hyprctl configerrors)]"; echo "plugins: $(H hyprctl plugin list | grep -c Plugin)"; H hyprctl layers | grep -E "namespace" | sed 's/.*namespace: //;s/,.*//' | sort | uniq -c | tr '\n' ' '; echo
echo "== wallpaper"; pgrep -a swaybg | cut -c1-90; tail -2 /home/$U/.cache/windoesnot/swaybg.log 2>/dev/null; echo "hyprpaper running: $(pgrep -c hyprpaper)"
echo "== hwcheck"; timeout 20 python3 /usr/lib/windoesnot/hwcheck.py 2>&1 | head -c 900; echo
echo "== pacnew"; timeout 20 python3 /usr/lib/windoesnot/pacnew.py 2>&1 | head -c 300; echo
echo "== admin"; ls /home/$U/.local/share/nautilus-python/extensions/ 2>&1 | tr '\n' ' '; echo; windoesnot-run-as-admin --help 2>&1 | head -2
echo "== startmenu apps"; H windoesnot-list-apps 2>&1 | head -c 200; echo; H windoesnot-list-apps 2>/dev/null | grep -ci "cmake"
echo "== lite flag"; ls /etc/windoesnot/lite-mode 2>&1
echo "== idle load"; cut -d' ' -f1-3 /proc/loadavg
