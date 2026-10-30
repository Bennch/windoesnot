#!/usr/bin/env bash
# Compile the pinned native apps (GTK or Qt) against the image's own
# libraries; never copy host binaries.
set -euo pipefail
[[ -f /etc/windoesnot-image-build && $EUID == 0 ]] || { echo 'Image build only.' >&2; exit 1; }
project=/usr/share/windoesnot
work=$(mktemp -d /tmp/windoesnot-connectivity.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
# mktemp creates a root-only directory (0700). The isolated makepkg process
# runs as nobody, so it must be able to traverse the temporary build root.
chown nobody:nobody "$work"
printf '[options]\nArchitecture = auto\nSigLevel = Required DatabaseOptional\nLocalFileSigLevel = Optional\n' > "$work/local-install.conf"
for app in windoesnot-bluetooth windoesnot-network windoesnot-audio; do
    mkdir -p "$work/$app/home"
    cp -a "$project/$app-build/." "$work/$app/"
    chown -R nobody:nobody "$work/$app"
    runuser -u nobody -- env HOME="$work/$app/home" bash -c 'cd -- "$1"; makepkg --cleanbuild --noconfirm --nocolor' bash "$work/$app" 2>&1 | tee "$project/$app-BUILD.log"
    cp "$work/$app/"*.pkg.tar.zst /var/cache/pacman/pkg/
    pacman --config "$work/local-install.conf" -U --noconfirm "$work/$app/"*.pkg.tar.zst
    rm -rf -- "$project/$app-build"
done
