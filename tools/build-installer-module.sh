#!/usr/bin/env bash
# Rebuild our module against the exact installed image SDK, never host Calamares.
set -euo pipefail
[[ -f /etc/windoesnot-image-build && $EUID == 0 ]] || { echo 'Image build only.' >&2; exit 2; }
project=/usr/share/windoesnot
work=$(mktemp -d /tmp/windoesnot-installer-module.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
cp -a "$project/iso/modules/windoesnotapps" "$work/windoesnotapps"
cp -a "$project/iso/modules/windoesnotboot" "$work/windoesnotboot"
cat > "$work/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.22)
project(WinDoesNotInstallerModule LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
include(GNUInstallDirs)
find_package(KF6CoreAddons REQUIRED)
find_package(Calamares REQUIRED)
set(CALAMARES_APPLICATION_NAME calamares)
set(INSTALL_CONFIG OFF)
set(BUILD_TESTING OFF)
calamares_add_module_subdirectory(windoesnotapps)
calamares_add_module_subdirectory(windoesnotboot)
CMAKE
cmake -S "$work" -B "$work/build" -G Ninja -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/build" -j "${BUILD_JOBS:-4}"
cmake --install "$work/build"
# Our Python jobs have no compiled target; refresh them alongside the views.
for name in windoesnotprepare windoesnotapps_install windoesnotfinish; do
    install -d "/usr/lib/calamares/modules/$name"
    install -m644 "$project/iso/modules/$name/main.py" "$project/iso/modules/$name/module.desc" "/usr/lib/calamares/modules/$name/"
done
if ldd /usr/lib/calamares/modules/windoesnotapps/libcalamares_viewmodule_windoesnotapps.so | grep -q 'not found'; then exit 1; fi
if ldd /usr/lib/calamares/modules/windoesnotboot/libcalamares_viewmodule_windoesnotboot.so | grep -q 'not found'; then exit 1; fi
