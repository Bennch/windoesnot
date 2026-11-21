#!/usr/bin/env bash
# Build windoesnot-nautilus (Files with This PC, drives view and sidebar patches) inside the image, from the exact
# tarball and patches in packaging/nautilus, against the image's own GTK/libadwaita. It replaces the distribution's
# nautilus package; the extension interface stays with libnautilus-extension.
set -euo pipefail
[[ -f /etc/windoesnot-image-build && $EUID == 0 ]] || { echo 'Image build only.' >&2; exit 1; }
project=/usr/share/windoesnot
[[ -f $project/packaging/nautilus/PKGBUILD ]] || { echo 'Nautilus packaging missing.' >&2; exit 1; }
work=$(mktemp -d /tmp/windoesnot-nautilus.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
mkdir "$work/src" "$work/src/home"
cp -a "$project/packaging/nautilus/." "$work/src/"
# Image packages must run on every x86-64 CPU (the CachyOS makepkg.conf uses -march=native).
sed -e 's/-march=native/-march=x86-64 -mtune=generic/g' -e 's/-O3/-O2/g' /etc/makepkg.conf > "$work/makepkg-generic.conf"
chmod 755 "$work"; chmod 644 "$work/makepkg-generic.conf"
chown -R nobody:nobody "$work/src"
runuser -u nobody -- env WDN_MAKEPKG_CONF="$work/makepkg-generic.conf" HOME="$work/src/home" \
    bash -c 'cd -- "$1"; makepkg --config "$WDN_MAKEPKG_CONF" --cleanbuild --noconfirm --nocolor' bash "$work/src" 2>&1 | tee "$project/NAUTILUS-BUILD.log"
mkdir -p /var/cache/pacman/pkg
cp "$work/src/"*.pkg.tar.zst /var/cache/pacman/pkg/
printf '[options]\nArchitecture = auto\nSigLevel = Required DatabaseOptional\nLocalFileSigLevel = Optional\n' > "$work/local-install.conf"
# --ask=4 answers the "remove nautilus?" conflict question with yes (the new package provides nautilus).
pacman --config "$work/local-install.conf" -U --noconfirm --ask=4 "$work/src/"*.pkg.tar.zst
pacman -Qq windoesnot-nautilus >/dev/null
! pacman -Qq nautilus 2>/dev/null | grep -qx nautilus || { echo 'The distribution nautilus package is still installed.' >&2; exit 1; }
