#!/usr/bin/env bash
# Build real packages inside the image; never install anything on the host.
set -euo pipefail
[[ -f /etc/windoesnot-image-build && $EUID == 0 ]] || { echo 'Image build only.' >&2; exit 1; }
project=/usr/share/windoesnot
work=$(mktemp -d /tmp/windoesnot-packages.XXXXXXXX)
cleanup() {
    status=$?
    if ((status != 0)); then
        if [[ -d $work/desktop-build-source && ! -e $project/desktop ]]; then mv "$work/desktop-build-source" "$project/desktop"; fi
        if [[ -d $work/icons-build-source && ! -e /usr/share/icons/Win11 ]]; then mv "$work/icons-build-source" /usr/share/icons/Win11; fi
    fi
    rm -rf -- "$work"
    exit "$status"
}
trap cleanup EXIT
python3 "$project/tools/prepare-packages.py" --output "$work/source"
mkdir "$work/home"
chown -R nobody:nobody "$work"
runuser -u nobody -- env HOME="$work/home" bash -c 'cd -- "$1"; makepkg --cleanbuild --noconfirm --nocolor' bash "$work/source" 2>&1 | tee "$project/PACKAGE-BUILD.log"
python3 "$project/tools/check-packages.py" "$work/source"
mkdir -p /var/cache/pacman/pkg
cp "$work/source/"*.pkg.tar.zst /var/cache/pacman/pkg/
# The profile initially stages build sources here. Pacman now owns the runtime
# tree. Keep installer/build scripts beside it, outside package-owned files.
mv "$project/desktop" "$work/desktop-build-source"
if [[ -d /usr/share/icons/Win11 ]]; then mv /usr/share/icons/Win11 "$work/icons-build-source"; fi
# All dependencies are already installed in this build root. Use a temporary
# repository-free config for these freshly built local packages: the live GPG
# keyring is initialized at boot, so validating unrelated sync databases here
# would fail. The installed /etc/pacman.conf and signature policy stay intact.
printf '[options]\nArchitecture = auto\nSigLevel = Required DatabaseOptional\nLocalFileSigLevel = Optional\n' > "$work/local-install.conf"
pacman --config "$work/local-install.conf" -U --noconfirm "$work/source/"*.pkg.tar.zst
# The store has its own version and pinned, vendored sources (staged by
# prepare-profile.py). Build it offline against this image's GTK/libadwaita,
# then remove exactly the build-only toolchain again. A desktop refresh of a
# finished image has no staged store and keeps the installed one.
if [[ -f $project/store/PKGBUILD ]]; then
    mkdir "$work/store" "$work/cargo"
    cp -a "$project/store/." "$work/store/"
    chown -R nobody:nobody "$work/store" "$work/cargo"
    runuser -u nobody -- env HOME="$work/home" CARGO_HOME="$work/cargo" CARGO_NET_OFFLINE=true \
        bash -c 'cd -- "$1"; makepkg --cleanbuild --noconfirm --nocolor' bash "$work/store" 2>&1 | tee "$project/STORE-BUILD.log"
    python3 "$project/tools/check-packages.py" --store "$work/store"
    cp "$work/store/"*.pkg.tar.zst /var/cache/pacman/pkg/
    pacman --config "$work/local-install.conf" -U --noconfirm "$work/store/"*.pkg.tar.zst
    rm -rf -- "$project/store"
    mapfile -t build_only < <(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$project/iso/packages-build-only.txt")
    pacman -Qq | sort > "$work/before-toolchain-removal"
    pacman -Rns --noconfirm "${build_only[@]}"
    pacman -Qq | sort | comm -23 "$work/before-toolchain-removal" - > "$project/STORE-BUILD-REMOVED.txt"
fi
