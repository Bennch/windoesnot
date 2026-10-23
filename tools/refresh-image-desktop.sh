#!/usr/bin/env bash
# Rebuild only project packages in a completed image; retain its distro ABI/apps.
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
resume=false
if [[ ${1:-} == --resume ]]; then resume=true; shift; fi
build_id=${1:?Usage: refresh-image-desktop.sh [--resume] BUILD_ID}
[[ $build_id =~ ^[a-zA-Z0-9_-]+$ ]] || exit 2
build="$project/build/$build_id"
image="$build/work/x86_64/airootfs"
[[ -f "$image/etc/windoesnot-image-build" && -f "$build/work/base._make_customize_airootfs" ]] || { echo 'Expected a completed project image.' >&2; exit 2; }
(( EUID != 0 )) || { echo 'Run as the regular build user; arch-chroot uses its own user namespace.' >&2; exit 2; }
if $resume; then
    [[ -d "$build/desktop-before-refresh" ]] || { echo 'No interrupted refresh to resume.' >&2; exit 2; }
else
    [[ ! -e "$build/desktop-before-refresh" ]] || { echo 'Previous refresh backup exists; inspect before continuing.' >&2; exit 2; }
fi
payload="$image/usr/share/windoesnot"
if ! $resume; then mv -- "$payload/desktop" "$build/desktop-before-refresh"; fi
python3 - "$project" "$payload" "$resume" <<'COPY'
from pathlib import Path
import shutil,sys
project,payload=map(Path,sys.argv[1:3])
resume=sys.argv[3] == "true"
for name in ['desktop','tools','iso','packaging']:
    if resume and name == 'desktop': continue
    shutil.copytree(project/name,payload/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','import-manifest.json'))
COPY
cp -a -- "$project/iso/modules/windoesnotapps/." "$payload/vendor/calamares/src/modules/windoesnotapps/"
cat > "$image/root/windoesnot-refresh-desktop.sh" <<'CHROOT'
#!/usr/bin/env bash
set -euo pipefail
[[ -f /etc/windoesnot-image-build ]] || exit 2
project=/usr/share/windoesnot
if [[ ${WINDOESNOT_SKIP_DESKTOP:-false} != true ]]; then "$project/tools/build-image-packages.sh"; fi
"$project/tools/build-installer-module.sh"
python3 "$project/iso/brand-installer.py"
install -m755 "$project/iso/windoesnot-installer" /usr/local/bin/windoesnot-installer
install -m755 "$project/iso/windoesnot-installer" /usr/local/bin/calamares-online.sh
HOME=/etc/skel XDG_CONFIG_HOME=/etc/skel/.config XDG_STATE_HOME=/etc/skel/.local/state windoesnot-initialize
cp -a /etc/skel/. /home/liveuser/
chown -R liveuser:liveuser /home/liveuser
pacman -Q > "$project/IMAGE-PACKAGES.txt"
python3 - <<'PY'
from pathlib import Path
import json,subprocess
p=Path('/usr/share/windoesnot/offline-apps/manifest.json')
data=json.loads(p.read_text())
data['base_packages']=subprocess.check_output(['pacman','-Q'],text=True).splitlines()
p.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
PY
CHROOT
chmod +x "$image/root/windoesnot-refresh-desktop.sh"
arch-chroot -N "$image" /usr/bin/env WINDOESNOT_SKIP_DESKTOP="$resume" /root/windoesnot-refresh-desktop.sh
rm -- "$image/root/windoesnot-refresh-desktop.sh"
# Keep recovery and exact source hashes outside the image.
python3 - "$project" "$build" <<'PY'
from pathlib import Path
import hashlib,json,sys
project,build=map(Path,sys.argv[1:])
p=build/'SOURCE-STATE.json'
if p.exists():p.rename(build/('SOURCE-STATE-before-desktop-refresh-'+hashlib.sha256(p.read_bytes()).hexdigest()[:12]+'.json'))
files={str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for name in ['desktop','iso','tools','packaging'] for p in (project/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(build/'SOURCE-STATE.json').write_text(json.dumps(files,indent=2,sort_keys=True)+'\n')
PY
for flag in base._make_pkglist base._cleanup_pacstrap_dir base._prepare_airootfs_image base._mkairootfs_squashfs iso._build_iso_image build._build_buildmode_iso; do
    rm -f -- "$build/work/$flag"
done
output="$project/out/$build_id"
if compgen -G "$output/*.iso" >/dev/null; then
    archive="$output/archive-before-desktop-$(date +%Y%m%d-%H%M%S)"
    mkdir -p -- "$archive"
    mv -- "$output/"*.iso "$output/"*.sha256 "$archive/"
fi
printf 'Desktop packages refreshed. Repack with: ./build-and-run.sh --build-only --build-id %q\n' "$build_id"
