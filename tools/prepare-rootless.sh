#!/usr/bin/env bash
# Prepare only project-owned cache/keyring directories, retaining signature checks.
set -euo pipefail
profile=$(realpath -e -- "${1:?Missing profile}")
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ $profile == "$project"/build/* ]] || { echo 'Profile must be in the project build directory.' >&2; exit 2; }
(( EUID != 0 )) || { echo 'Rootless mode must run as a regular user.' >&2; exit 2; }
unshare --user --map-root-user --mount true
cache="$project/build/package-cache"
keyring="$project/build/signing-keyring"
mkdir -p "$cache" "$keyring"
chmod 700 "$keyring"
if [[ ! -s $keyring/pubring.gpg ]]; then
    unshare --user --map-root-user -- pacman-key --gpgdir "$keyring" --init
    unshare --user --map-root-user -- pacman-key --gpgdir "$keyring" --populate archlinux cachyos
fi
python3 - "$profile/pacman.conf" "$cache" "$keyring" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);text=p.read_text()
text='\n'.join(line for line in text.splitlines() if not line.lstrip().startswith(('CacheDir =','GPGDir =')))+'\n'
text=text.replace('[options]','[options]\nCacheDir = '+sys.argv[2]+'\nGPGDir = '+sys.argv[3],1)
p.write_text(text)
PY
