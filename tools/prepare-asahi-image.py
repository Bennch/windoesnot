#!/usr/bin/env python3
"""Prepare a pinned Asahi image workspace; never clone the running installation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

PROJECT = Path(__file__).resolve().parents[1]
BUILDER = '58cc158c7fda3ef6aeae36606f84a63b4b0867e7'
URL = 'https://github.com/asahi-alarm/asahi-alarm-builder.git'
REQUIRED_PACKAGES = {'windoesnot-desktop', 'windoesnot-tools', 'windoesnot-plugins',
                     'windoesnot-components', 'windoesnot-device-manager',
                     'windoesnot-bluetooth', 'windoesnot-network', 'ghostty', 'localsend'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package_info(path):
    text = subprocess.check_output(['bsdtar', '-xOf', str(path), '.PKGINFO'], text=True)
    fields = dict(line.split(' = ', 1) for line in text.splitlines() if ' = ' in line)
    if fields.get('arch') not in ('aarch64', 'any'):
        raise ValueError(f'Not an ARM package: {path}')
    return {'name': fields['pkgname'], 'version': fields['pkgver'],
            'arch': fields['arch'], 'sha256': digest(path), 'file': path.name}


def prepare(output, upstream, packages=None, base=None, base_sha=None):
    output = output.resolve()
    allowed = PROJECT / 'build'
    if allowed not in output.parents or output == allowed or output.exists():
        raise ValueError('Use a new workspace strictly below this project’s build directory')
    upstream = upstream.resolve()
    actual = subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != BUILDER or subprocess.check_output(['git', '-C', str(upstream), 'status', '--porcelain'], text=True):
        raise ValueError('The Asahi builder checkout must be clean and match the recorded pin')
    if base and (not base_sha or digest(base) != base_sha):
        raise ValueError('The seed archive needs an explicitly supplied matching SHA-256')
    output.mkdir(parents=True)
    # Export only pinned git objects, including the MIT license.
    archive = subprocess.check_output(['git', '-C', str(upstream), 'archive', BUILDER])
    import io
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(output, filter='data')
    # These workflows publish upstream artifacts; never carry them downstream.
    shutil.rmtree(output / '.github', ignore_errors=True)
    source = output / 'files/windoesnot-image'
    for name in ('tools/brand-asahi.py', 'iso/boot_splash.py', 'iso/boot-splash',
                 'iso/branding/dark.qss', 'iso/branding/check.svg',
                 'desktop/config/quickshell/default/img/brand', 'desktop/share/grub/themes/windoesnot'):
        p, target = PROJECT / name, source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if p.is_dir():
            shutil.copytree(p, target, ignore=shutil.ignore_patterns('__pycache__'))
        else:
            shutil.copy2(p, target)
    shutil.copytree(PROJECT / 'installer/asahi/firstboot', source / 'firstboot',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(PROJECT / 'installer/asahi/image-configure.py', source / 'configure.py')
    package_dir = output / 'files/packages'
    package_dir.mkdir()
    inventory = []
    if packages:
        for package in sorted(packages.glob('*.pkg.tar.*')):
            if package.name.endswith('.sig'):
                continue
            inventory.append(package_info(package))
            shutil.copy2(package, package_dir / package.name)
    if len({p['name'] for p in inventory}) != len(inventory):
        raise ValueError('Supply exactly one version of each native package')
    core = [p['version'] for p in inventory if p['name'] in
            {'windoesnot-desktop', 'windoesnot-tools', 'windoesnot-components', 'windoesnot-plugins'}]
    if len(set(core)) > 1:
        raise ValueError('The four desktop packages must have the same version/release')
    missing = sorted(REQUIRED_PACKAGES - {v['name'] for v in inventory})
    # Use only the base script group. Our desktop is preinstalled, not downloaded
    # piecemeal by a desktop selector during first boot.
    shutil.rmtree(output / 'scripts/desktop')
    (output / 'scripts/desktop').mkdir()
    (output / 'scripts/desktop/10-windoesnot.sh').write_text('''#!/bin/bash
set -euo pipefail
touch /etc/windoesnot-image-build
pacman -S --needed --noconfirm plymouth sddm cage calamares qt6-wayland python python-yaml
pacman -U --noconfirm /files/packages/*.pkg.tar.*
python /files/windoesnot-image/configure.py
pacman -Q > /etc/windoesnot-image-packages.txt
''')
    path = output / 'build.sh'
    text = path.read_text()
    text = text.replace('ROOT_UUID=725346d2-f127-47bc-b464-9dd46155e8d6',
                        'ROOT_UUID=7774b740-8b7e-458a-9208-77d40d4e4d41')
    text = text.replace('EFI_UUID=2ABF-9F91', 'EFI_UUID=5744-4E4D')
    text = text.replace('FSTYPE=ext4', 'FSTYPE=btrfs')
    text = text.replace('-L "asahi-root"', '-L "windoesnotmac"')
    text = text[:text.index('# ext4 variants')] + '''# WinDoesNotMac: only our complete BTRFS desktop image.
init
run_scripts base
run_scripts desktop
make_image "windoesnotmac-btrfs"
'''
    # No mutable "latest" download; the wrapper verifies the supplied seed.
    start = text.index('\tif [ ! -e "$DL/$BASE_IMAGE" ]; then')
    end = text.index('\n\tfi', start) + len('\n\tfi')
    text = text[:start] + '\ttest -s "$DL/$BASE_IMAGE"' + text[end:]
    # Preserve a blank machine-id in the payload rather than the upstream exclusion.
    text = text.replace('\n\t\t--exclude /etc/machine-id \\', '')
    path.write_text(text)
    (output / 'dl').mkdir()
    if base:
        shutil.copy2(base, output / 'dl/ArchLinuxARM-aarch64-latest.tar.gz')
    manifest = {'builder_url': URL, 'builder_commit': BUILDER, 'packages': inventory,
                'missing_packages': missing, 'base_sha256': base_sha if base else None,
                'root_uuid': '7774b740-8b7e-458a-9208-77d40d4e4d41', 'efi_volume_id': '0x57444e4d',
                'filesystem': 'btrfs', 'status': 'prepared; not built or boot tested'}
    # Record every input copied from our source tree as well as the generated scripts.
    manifest['input_sha256'] = {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob('*'))
                               if p.is_file() and 'dl' not in p.relative_to(output).parts}
    (output / 'build-inputs.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'build-image.sh').write_text('''#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
[[ $(uname -m) == aarch64 && $EUID == 0 ]] || { echo 'Run in a dedicated ARM64 Linux builder as root.' >&2; exit 1; }
for tool in arch-chroot pacstrap mkfs.btrfs rsync zip grub-mkimage; do command -v "$tool" >/dev/null; done
python - <<'CHECK'
import hashlib,json
from pathlib import Path
m=json.loads(Path('build-inputs.json').read_text())
if m['missing_packages']: raise SystemExit('Missing native packages: '+', '.join(m['missing_packages']))
if not m['base_sha256']: raise SystemExit('Supply a verified ARM seed archive when preparing the workspace.')
def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
if sha('dl/ArchLinuxARM-aarch64-latest.tar.gz') != m['base_sha256']: raise SystemExit('Seed archive checksum mismatch')
for p,h in m['input_sha256'].items():
    if sha(p)!=h: raise SystemExit('Build input changed: '+p)
CHECK
exec nice -n 10 bash ./build.sh
''')
    (output / 'build-image.sh').chmod(0o755)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--builder-source', required=True, type=Path,
                        help=f'Clean checkout of {URL} at {BUILDER}')
    parser.add_argument('--packages-dir', type=Path)
    parser.add_argument('--base-archive', type=Path)
    parser.add_argument('--base-sha256')
    args = parser.parse_args()
    result = prepare(args.output, args.builder_source, args.packages_dir, args.base_archive, args.base_sha256)
    print(json.dumps(result, indent=2))
