#!/usr/bin/env python3
"""Create the public dotfiles source export: sanitized desktop sources, packaging
recipes, a README and a SOURCE.json with the git commit and per-file SHA256."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent.parent
version_info = json.loads((ROOT / 'packaging/version.json').read_text())
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--version', default=version_info['version'])
parser.add_argument('--release', default=version_info['release'])
parser.add_argument('--allow-dirty', action='store_true', help='export with uncommitted changes')
args = parser.parse_args()
if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+', args.version) or not re.fullmatch(r'[1-9][0-9]*', args.release):
    parser.error('Use a numeric version and positive package release')

# Same selection rules as tools/prepare-packages.py, which the export ships.
excluded = {'__pycache__', '.git', 'import-manifest.json', 'settings.txt', 'state.lua', 'host.lua', 'geometry.lua', 'calendar_notes.json', 'copilot-state.json', 'icons.json', 'icon-map.json', 'state.json', 'state.lock'}
included = ['desktop', 'LICENSE', 'THIRD-PARTY.md', 'sources.json', 'packaging/LICENSE-NOTES.md', 'packaging/version.json', 'packaging/changelog.json', 'packaging/PKGBUILD.in', 'packaging/release-key', 'tools/build-components.sh', 'tools/check-plugin-symbols.py', 'tools/prepare-packages.py']

commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
dirty = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain', '--', *included], capture_output=True, text=True, check=True).stdout.strip()
if dirty and not args.allow_dirty:
    raise SystemExit('Uncommitted changes in exported paths; commit first or use --allow-dirty:\n' + dirty)

output = args.output.resolve()
if output.exists():
    raise SystemExit('Use a new output directory to preserve earlier exports')
output.mkdir(parents=True)
name = 'windoesnot-dotfiles-%s-%s' % (args.version, args.release)
label = '%s-%s' % (args.version, args.release)
archive = output / (name + '.tar.gz')
files = {}

def add_bytes(stream, relative, data, mode=0o644):
    info = tarfile.TarInfo(name + '/' + relative)
    info.size, info.mode, info.mtime = len(data), mode, 0
    stream.addfile(info, __import__('io').BytesIO(data))

with tarfile.open(archive, 'w:gz', dereference=False) as stream:
    for entry in included:
        root = ROOT / entry
        for path in sorted(root.rglob('*')) if root.is_dir() else ([root] if root.exists() else []):
            relative = path.relative_to(ROOT)
            if not path.is_file() or path.is_symlink() or any(p in excluded or p.startswith('.') for p in relative.parts) or path.suffix in ('.so', '.o', '.pyc'):
                continue
            # Runtime QML-generated plugin metadata is built, never imported.
            if 'widgets/terminalmodule/LocalTerminal' in relative.as_posix():
                continue
            files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
            info = stream.gettarinfo(str(path), name + '/' + relative.as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mtime = 0
            info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            with path.open('rb') as source:
                stream.addfile(info, source)
    readme = (ROOT / 'packaging/DOTFILES-README.md.in').read_text().replace('@VERSION@', label)
    add_bytes(stream, 'README.md', readme.encode())
    source = {'commit': commit, 'version': label, 'files': files}
    add_bytes(stream, 'SOURCE.json', (json.dumps(source, indent=2, sort_keys=True) + '\n').encode())

data = archive.read_bytes()
(output / (archive.name + '.sha256')).write_text(hashlib.sha256(data).hexdigest() + '  ' + archive.name + '\n')
(output / (archive.name + '.md5')).write_text(hashlib.md5(data).hexdigest() + '  ' + archive.name + '\n')
print(archive)
print('Files:', len(files), 'Commit:', commit, 'Bytes:', len(data))
