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
# Image packages must run on every x86-64 CPU. The CachyOS makepkg.conf uses
# -march=native, which bakes the build machine's instructions into C objects
# (SIGILL on older CPUs). Build with a generic x86-64 configuration instead.
sed -e 's/-march=native/-march=x86-64 -mtune=generic/g' -e 's/-O3/-O2/g' /etc/makepkg.conf > "$work/makepkg-generic.conf"
chmod 755 "$work"; chmod 644 "$work/makepkg-generic.conf"
chown -R nobody:nobody "$work"
runuser -u nobody -- env WDN_MAKEPKG_CONF="$work/makepkg-generic.conf" HOME="$work/home" bash -c 'cd -- "$1"; makepkg --config "$WDN_MAKEPKG_CONF" --cleanbuild --noconfirm --nocolor' bash "$work" 2>&1 | tee "$project/DEVICE-MANAGER-BUILD.log"
mkdir -p /var/cache/pacman/pkg
cp "$work/"*.pkg.tar.zst /var/cache/pacman/pkg/
printf '[options]\nArchitecture = auto\nSigLevel = Required DatabaseOptional\nLocalFileSigLevel = Optional\n' > "$work/local-install.conf"
pacman --config "$work/local-install.conf" -U --noconfirm "$work/"*.pkg.tar.zst
rm -rf -- "$project/device-manager-build"
