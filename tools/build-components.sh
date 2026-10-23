#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output=${1:-"$project/build/components"}
mkdir -p -- "$output"
output=$(realpath -- "$output")
work=$(mktemp -d "${TMPDIR:-/tmp}/windoesnot-components.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
jobs=${BUILD_JOBS:-$(nproc)}
# CachyOS makepkg defaults include -march=native. These are redistributable
# binaries: explicitly override local CPU tuning for every component.
export CFLAGS='-march=x86-64 -mtune=generic -O2 -pipe -fno-plt -fexceptions -Wp,-D_FORTIFY_SOURCE=3 -Wformat -Werror=format-security -fstack-clash-protection -fcf-protection'
export CXXFLAGS="$CFLAGS -Wp,-D_GLIBCXX_ASSERTIONS"
printf 'CFLAGS=%s\nCXXFLAGS=%s\n' "$CFLAGS" "$CXXFLAGS" > "$output/NATIVE-FLAGS.txt"
for plugin in hyprbars hyprdrag; do
    cp -a -- "$project/desktop/plugins/$plugin" "$work/$plugin"
    make -C "$work/$plugin" -j "$jobs" CXX=g++
    install -Dm755 "$work/$plugin/$plugin.so" "$output/plugins/$plugin.so"
    python3 "$project/tools/check-plugin-symbols.py" "$output/plugins/$plugin.so"
done
cp -a -- "$project/desktop/config/quickshell/default/terminalmodule" "$work/terminalmodule"
# The QML plugin loads its sister library from its own directory; the default
# build RPATH would point at this temporary build tree instead.
cmake -S "$work/terminalmodule" -B "$work/terminal-build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON -DCMAKE_INSTALL_RPATH='$ORIGIN'
cmake --build "$work/terminal-build" -j "$jobs"
mkdir -p "$output/LocalTerminal"
cp -a "$work/widgets/terminalmodule/LocalTerminal/." "$output/LocalTerminal/"
for library in "$output/LocalTerminal/"*.so; do
    runpath=$(readelf -d "$library" | sed -n 's/.*(\(RUNPATH\|RPATH\)).*\[\(.*\)\]/\2/p')
    [[ -z $runpath || $runpath == '$ORIGIN' ]] || { echo "Unexpected RUNPATH in $library: $runpath" >&2; exit 1; }
done
cp -a -- "$project/desktop/vendor/snappy-switcher" "$work/snappy-switcher"
make -C "$work/snappy-switcher" protocols
snappy_flags="$CFLAGS -Wall -Wextra -D_POSIX_C_SOURCE=200809L $(pkg-config --cflags wayland-client cairo pango pangocairo json-c xkbcommon librsvg-2.0) -DHAVE_RSVG"
make -C "$work/snappy-switcher" -j "$jobs" CFLAGS="$snappy_flags"
install -Dm755 "$work/snappy-switcher/snappy-switcher" "$output/bin/snappy-switcher"
pacman -Q hyprland quickshell qt6-base qtermwidget gcc > "$output/BUILD-PACKAGES.txt"
sha256sum "$output/plugins/"*.so "$output/LocalTerminal/"*.so "$output/bin/snappy-switcher" > "$output/SHA256SUMS"
