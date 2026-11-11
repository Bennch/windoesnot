#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
profile=${1:?Usage: resolve-packages.sh generated-profile}
profile=$(realpath -e -- "$profile")
resolver="$profile/resolver"
mkdir -p "$resolver/db/local" "$resolver/cache" "$resolver/hooks" "$resolver/root"
common=(--config "$profile/pacman.conf" --root "$resolver/root" --dbpath "$resolver/db" --cachedir "$resolver/cache" --logfile "$resolver/pacman.log" --hookdir "$resolver/hooks" --gpgdir /etc/pacman.d/gnupg --color never)
fakeroot pacman "${common[@]}" -Sy --noconfirm
mapfile -t packages < "$profile/packages.x86_64"
fakeroot pacman "${common[@]}" -Sp --noconfirm --print-format '%n %v %r' "${packages[@]}" > "$resolver/package-plan.txt"
printf 'Resolved %s packages, isolated DB: %s\n' "$(wc -l < "$resolver/package-plan.txt")" "$resolver"
