#!/usr/bin/env bash
# Build the runtime-free Recovery frontend on macOS.
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ $(uname -s) == Darwin ]] || { echo 'The Recovery app needs the macOS SDK; build it on macOS.' >&2; exit 1; }
[[ $# == 1 ]] || { echo 'Usage: tools/build-recovery-app.sh /path/to/Finish Installation.app' >&2; exit 2; }
target=$1/Contents/MacOS/WinDoesNotRecovery
mkdir -p -- "$(dirname -- "$target")"
xcrun clang -arch arm64 -mmacosx-version-min=11.0 -fobjc-arc -fblocks \
    -Wall -Wextra -framework Cocoa \
    "$project/installer/asahi/native/RecoveryApp.m" -o "$target"
codesign --force --sign - "$target"
python3 "$project/tools/build-mac-icon.py" "$1/Contents/Resources/windoesnot.icns"
codesign --force --deep --sign - "$1"
echo "Built: $target"
