#!/bin/bash
# Drive the English Calamares installer (erase disk). Usage: drive-install-en.sh VM [grub|refind|limine-uefi]
cd "$(dirname "$0")/../.."; V=$1; LOADER=${2:-grub}
case "$LOADER" in
    grub|0) LY= ;; refind) LY=446 ;; limine-uefi) LY=592 ;;
    *) echo "Unsupported bootloader: $LOADER" >&2; exit 2 ;;
esac
S=${TMPDIR:-/tmp}
vm(){ python3 tools/vmctl.py --vm-name $V "$@"; }
click(){ vm hmp "mouse_set 4" >/dev/null; vm click $1 $2 1280 800 >/dev/null; sleep ${3:-3}; }
shot(){ vm exec /usr/bin/bash -c ". /tmp/guest-env.sh 2>/dev/null; U=1000; runuser -u liveuser -- env XDG_RUNTIME_DIR=/run/user/\$U WAYLAND_DISPLAY=wayland-1 grim /tmp/$1.png" >/dev/null 2>&1; vm pull /tmp/$1.png $1.png >/dev/null 2>&1; }
timeout 200 bash -c "until python3 tools/vmctl.py --vm-name $V exec /usr/bin/true >/dev/null 2>&1; do sleep 4; done"; sleep 20
click 100 75 .15; click 100 75 1
timeout 90 bash -c "until python3 tools/vmctl.py --vm-name $V exec /usr/bin/pgrep calamares >/dev/null 2>&1; do sleep 2; done"; sleep 12
for i in 1 2 3; do click 1158 721 3; done
shot boot-page
if [[ -n $LY ]]; then click 278 "$LY" 2; fi
click 1158 721 6; click 220 120 3; for i in 1 2 3; do click 1158 721 6; done
# Windows-data page may finish detection after the first Next click.
click 1158 721 6
click 310 100 .4; vm type "Max Test" >/dev/null; click 310 298 .4; vm type "Test12345" >/dev/null; click 516 298 .4; vm type "Test12345" >/dev/null; sleep 2
click 1158 721 6; shot summary
click 1155 721 3; click 729 426 1; date +%T > $S/inst-start
echo started
