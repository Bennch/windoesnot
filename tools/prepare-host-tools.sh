#!/usr/bin/env bash
# Use a signed cached GRUB package as an unpacked build tool, without installation.
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if command -v grub-mkstandalone >/dev/null; then exit 0; fi
keyring="$project/build/signing-keyring"
[[ -s $keyring/pubring.gpg ]] || { echo 'Prepare the isolated keyring first.' >&2; exit 1; }
mapfile -d '' -t archives < <(find /var/cache/pacman/pkg "$project/build/package-cache" -maxdepth 1 -type f -name 'grub-*.pkg.tar.zst' -print0 | sort -zV)
((${#archives[@]})) || { echo 'No signed GRUB package in cache. Download it to the project cache first.' >&2; exit 1; }
archive=${archives[-1]}
[[ -f $archive.sig ]] || { echo 'GRUB package signature missing.' >&2; exit 1; }
unshare --user --map-root-user -- pacman-key --gpgdir "$keyring" --verify "$archive.sig" "$archive"
root="$project/build/host-tools"
mkdir -p "$root"
bsdtar -xf "$archive" -C "$root"
"$root/usr/bin/grub-mkstandalone" --version
# mkarchiso uses absolute SBAT paths and the executable's compiled-in module
# prefix. Redirect both to the unpacked signed package, never the host /usr.
mkdir -p "$root/libexec"
mv "$root/usr/bin/grub-mkstandalone" "$root/libexec/grub-mkstandalone"
cat > "$root/usr/bin/grub-mkstandalone" <<'PY'
#!/usr/bin/env python3
import os
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[2]
args=sys.argv[1:]
target='x86_64-efi'
for i,arg in enumerate(args):
    if arg in ['-O','--format'] and i+1<len(args):target=args[i+1]
    elif arg.startswith('--format='):target=arg.split('=',1)[1]
args=[('--sbat='+str(root/'usr/share/grub/sbat.csv')) if a=='--sbat=/usr/share/grub/sbat.csv' else a for a in args]
if args not in [['--version'],['--help']]:
    args=['--directory='+str(root/'usr/lib/grub'/target),'--locale-directory='+str(root/'usr/share/locale'),*args]
    font=root/'usr/share/grub/unicode.pf2'
    if font.is_file():args.append('boot/grub/fonts/unicode.pf2='+str(font))
os.execv(root/'libexec/grub-mkstandalone',[str(root/'libexec/grub-mkstandalone'),*args])
PY
chmod +x "$root/usr/bin/grub-mkstandalone"
