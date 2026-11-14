#!/bin/bash
# usage: capture-scenes.sh VM USER OUTDIR   (installed system, GL headless VM, logged in)
cd "$(dirname "$0")/../.."; V=$1; USR=$2; OUT=$3; mkdir -p $OUT
vm(){ python3 tools/vmctl.py --vm-name $V "$@"; }
click(){ vm hmp "mouse_set 4" >/dev/null; vm click $1 $2 1920 1080 >/dev/null; sleep ${3:-2.5}; }
G(){ vm exec /usr/bin/bash -c "U=\$(id -u $USR); sig=\$(ls /run/user/\$U/hypr | head -1); runuser -u $USR -- env XDG_RUNTIME_DIR=/run/user/\$U WAYLAND_DISPLAY=wayland-1 HYPRLAND_INSTANCE_SIGNATURE=\$sig DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/\$U/bus $*" >/dev/null 2>&1; }
K(){ vm exec /usr/bin/bash -c "pkill -u $USR -f '$1'; true" >/dev/null 2>&1; sleep 2; }
shot(){ G "grim /tmp/$1.png"; vm pull /tmp/$1.png $1.png >/dev/null; cp vm/$V/$1.png $OUT/$1.png; }
K SetupWelcome; K nautilus; K gnome-system-monitor; K windoesnot-store; sleep 2
G "hyprctl eval 'hl.monitor({output=\"Virtual-1\", mode=\"1920x1080@60\", position=\"0x0\", scale=1})'"; sleep 4
click 831 1058 5; click 286 325; click 754 305; click 521 590 6; shot s5; click 831 1058 2
click 782 1058 3; shot scene-start; click 782 1058 2
G "setsid nautilus"; sleep 7; shot scene-files; K nautilus; sleep 2
G "setsid gnome-system-monitor"; sleep 7; shot scene-taskmgr; K gnome-system-monitor; sleep 2
G "setsid windoesnot-store"; sleep 9; shot scene-store; K windoesnot-store; sleep 3
shot scene-desktop; echo captured
