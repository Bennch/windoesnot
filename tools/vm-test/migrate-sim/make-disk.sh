#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 2 ]]; then
    echo "Usage: $0 FIXTURE_ROOT OUTPUT.qcow2" >&2
    exit 2
fi
fixture=$(realpath -e -- "$1")
out=$(realpath -m -- "$2")
[[ -d "$fixture" && ! -e "$out" && "$out" != "$fixture"/* ]] || { echo 'Invalid fixture or output already exists/inside fixture' >&2; exit 1; }
for tool in mkfs.ext4 qemu-img truncate; do command -v "$tool" >/dev/null; done
raw="${out}.raw-$$"
[[ ! -e "$raw" ]] || exit 1
trap 'rm -f -- "$raw"' EXIT
# mkfs -d populates without mounting; the sparse fixture needs room for its logical size.
truncate -s 4G "$raw"
mkfs.ext4 -q -F -d "$fixture" "$raw"
qemu-img convert -f raw -O qcow2 "$raw" "$out"
qemu-img check "$out"
printf 'Created %s\n' "$out"
