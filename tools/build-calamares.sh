#!/usr/bin/env bash
# Build in the target image so installer and Python/Boost share the same ABI.
set -euo pipefail
[[ -f /etc/windoesnot-image-build ]] || { echo 'Image marker missing; refusing system install.' >&2; exit 1; }
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source="$project/vendor/calamares"
[[ -f "$source/CMakeLists.txt" ]] || { echo 'Pinned Calamares sources missing.' >&2; exit 1; }
work=$(mktemp -d /tmp/windoesnot-calamares.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
cmake -S "$source" -B "$work/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_INSTALL_LIBDIR=lib \
    -DWITH_QT6=ON -DWITH_PYTHON=ON -DWITH_PYBIND11=OFF \
    -DBUILD_TESTING=OFF -DBUILD_SCHEMA_TESTING=OFF -DBUILD_CRASH_REPORTING=OFF \
    -DINSTALL_CONFIG=OFF -DINSTALL_POLKIT=ON \
    -DSKIP_MODULES='tracking;webview;license;interactiveterminal;notesqml;netinstall;packagechooser;packagechooserc'
cmake --build "$work/build" -j "${BUILD_JOBS:-4}"
# Do not leave plugins from the previously installed ABI under the rebuilt core.
# The image marker above prevents this cleanup on the developer's system.
rm -rf -- /usr/lib/calamares/modules
cmake --install "$work/build"
# Python modules are staged at configure time by Calamares. Install our own
# canonical jobs explicitly too, so a resumed build cannot retain an older copy.
for name in windoesnotprepare windoesnotsystem windoesnotapps_install windoesnotfinish windoesnotbootreuse; do
    install -d "/usr/lib/calamares/modules/$name"
    install -m644 "$project/iso/modules/$name/main.py" "$project/iso/modules/$name/module.desc" "/usr/lib/calamares/modules/$name/"
done
python3 "$project/iso/brand-installer.py"
ldconfig
if ldd /usr/bin/calamares | grep -q 'not found'; then echo 'Unresolved installer library' >&2; exit 1; fi
# Do not inherit the host's GTK platform theme or display in the build chroot.
QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME=basic QT_STYLE_OVERRIDE=Fusion \
    DISPLAY= WAYLAND_DISPLAY= /usr/bin/calamares --version --help >/dev/null
pacman -Q python boost-libs qt6-base kpmcore > "$project/CALAMARES-BUILD-PACKAGES.txt"
sha256sum /usr/bin/calamares /usr/lib/libcalamares*.so* > "$project/CALAMARES-SHA256SUMS"
