#!/usr/bin/env bash
# Build and install the separate language package only in the image chroot.
set -euo pipefail
[[ -f /etc/windoesnot-image-build && $EUID == 0 ]] || { echo 'Image build only.' >&2; exit 1; }
project=/usr/share/windoesnot
work=$(mktemp -d /tmp/windoesnot-boot-language.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
cp -a "$project/boot-language-build/." "$work/"
mkdir "$work/home"
chown -R nobody:nobody "$work"
runuser -u nobody -- env HOME="$work/home" bash -c 'cd -- "$1"; makepkg --cleanbuild --noconfirm --nocolor' bash "$work" 2>&1 | tee "$project/BOOT-LANGUAGE-BUILD.log"
mapfile -t packages < <(find "$work" -maxdepth 1 -name 'windoesnot-boot-language-*.pkg.tar.zst' -type f)
((${#packages[@]} == 1)) || { echo 'Expected one boot language package.' >&2; exit 1; }
cp "${packages[0]}" /var/cache/pacman/pkg/
printf '[options]\nArchitecture = auto\nSigLevel = Required DatabaseOptional\nLocalFileSigLevel = Optional\n' > "$work/local-install.conf"
pacman --config "$work/local-install.conf" -U --noconfirm "${packages[0]}"
rm -rf -- "$project/boot-language-build"
