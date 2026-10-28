#!/usr/bin/env bash
# Build the pinned Python/GTK fork inside the image, with no network sources.
set -euo pipefail
[[ -f /etc/windoesnot-image-build && $EUID == 0 ]] || { echo 'Image build only.' >&2; exit 1; }
project=/usr/share/windoesnot
[[ -f $project/device-manager-build/PKGBUILD ]] || { echo 'Device Manager source missing.' >&2; exit 1; }
work=$(mktemp -d /tmp/windoesnot-device-manager.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
cp -a "$project/device-manager-build/." "$work/"
mkdir "$work/home"
chown -R nobody:nobody "$work"
runuser -u nobody -- env HOME="$work/home" bash -c 'cd -- "$1"; makepkg --cleanbuild --noconfirm --nocolor' bash "$work" 2>&1 | tee "$project/DEVICE-MANAGER-BUILD.log"
mkdir -p /var/cache/pacman/pkg
cp "$work/"*.pkg.tar.zst /var/cache/pacman/pkg/
printf '[options]\nArchitecture = auto\nSigLevel = Required DatabaseOptional\nLocalFileSigLevel = Optional\n' > "$work/local-install.conf"
pacman --config "$work/local-install.conf" -U --noconfirm "$work/"*.pkg.tar.zst
rm -rf -- "$project/device-manager-build"
