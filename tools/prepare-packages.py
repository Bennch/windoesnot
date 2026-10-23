#!/usr/bin/env python3
"""Create a sanitized, checksummed source bundle and a split PKGBUILD."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parent.parent
version_info = json.loads((ROOT / 'packaging/version.json').read_text())
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--version', default=version_info['version'])
parser.add_argument('--release', default=version_info['release'])
args = parser.parse_args()
if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+', args.version) or not re.fullmatch(r'[1-9][0-9]*', args.release):
    parser.error('Use a numeric version and positive package release')
output = args.output.resolve()
if output.exists():
    raise SystemExit('Use a new output directory to preserve earlier builds')
output.mkdir(parents=True)
prefix = 'windoesnot-' + args.version
archive = output / (prefix + '.tar.gz')
excluded = {'__pycache__', '.git', 'import-manifest.json', 'settings.txt', 'state.lua', 'host.lua', 'geometry.lua', 'calendar_notes.json', 'copilot-state.json', 'icons.json', 'icon-map.json', 'state.json', 'state.lock'}
included = ['desktop', 'packaging/LICENSE-NOTES.md', 'packaging/version.json', 'tools/build-components.sh', 'tools/check-plugin-symbols.py']
files = {}
with tarfile.open(archive, 'w:gz', dereference=False) as stream:
    for name in included:
        root = ROOT / name
        for path in sorted(root.rglob('*')) if root.is_dir() else [root]:
            relative = path.relative_to(ROOT)
            if not path.is_file() or path.is_symlink() or any(p in excluded or p.startswith('.') for p in relative.parts) or path.suffix in ('.so', '.o', '.pyc'):
                continue
            # Runtime QML-generated plugin metadata is built, never imported.
            if 'widgets/terminalmodule/LocalTerminal' in relative.as_posix():
                continue
            files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
            info = stream.gettarinfo(str(path), prefix + '/' + relative.as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mtime = 0
            # Local deployment writes some source files as 0600. Packaged code
            # belongs to root and must remain readable by every desktop user.
            info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            with path.open('rb') as source:
                stream.addfile(info, source)
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
template = (ROOT / 'packaging/PKGBUILD.in').read_text()
(output / 'PKGBUILD').write_text(template.replace('@VERSION@', args.version).replace('@RELEASE@', args.release).replace('@SHA256@', checksum))
(output / 'SOURCE-MANIFEST.json').write_text(json.dumps({'version': args.version, 'release': args.release, 'source_sha256': checksum, 'files': files}, indent=2, sort_keys=True) + '\n')
(output / (archive.name + '.sha256')).write_text(checksum + '  ' + archive.name + '\n')
print(output)
print('Source files:', len(files), 'SHA256:', checksum)
print('Build as an unprivileged user in the target environment: makepkg --cleanbuild --noconfirm')
