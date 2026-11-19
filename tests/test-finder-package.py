#!/usr/bin/env python3
"""Transfer package: export to any folder, find it, verify, restore with modes, owners and without unselected folders."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('finder', root / 'desktop/lib/windoesnot/finder.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

def write(path, data='x', mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data)
    if mode is not None:
        os.chmod(path, mode)

with tempfile.TemporaryDirectory() as tmp:
    old = Path(tmp) / 'old'
    home = old / 'home/anna'
    write(old / 'etc/passwd', 'anna:x:%d:%d::/home/anna:/bin/bash\n' % (os.getuid(), os.getgid()))
    write(home / '.ssh/id_ed25519', 'PRIVATE', 0o600)
    os.chmod(home / '.ssh', 0o700)
    write(home / 'Documents/letter.txt', 'dear')
    os.link(home / 'Documents/letter.txt', home / 'Documents/hardlink.txt')
    os.symlink('letter.txt', home / 'Documents/link')
    write(home / 'Documents/with space ü.txt', 'u')
    write(home / '.cache/blob', 'c' * 500)
    (home / 'Projects/app').mkdir(parents=True)
    subprocess.run(['git', 'init', '-q', str(home / 'Projects/app')], check=True)
    write(home / 'Projects/app/src/main.rs', 'fn main(){}')
    write(home / 'Projects/app/node_modules/dep/index.js', 'N' * 100)
    write(old / 'opt/tool/bin', 'tool')
    manifest = f.scan(old)
    items = {i['id']: i for i in manifest['findings']}
    assert not items['cache']['selected'] and items['ssh']['selected']
    storage = Path(tmp) / 'stick'          # any folder: external disk, mounted SMB share ...
    storage.mkdir()
    result = f.export_package(manifest, storage)
    package = Path(result['package'])
    assert not result['problems'] and (package / f.PACKAGE_MARKER).is_file() and (package / 'SHA256SUMS').is_file()
    assert not any(package.rglob('*.partial')), 'marker is only written when complete'
    index = f.read_package(package)
    assert index['complete'] and 'cache' not in {e['id'] for e in index['findings']}
    found = f.find_packages([storage])
    assert len(found) == 1 and found[0]['complete'] and found[0]['user'] == 'anna' and found[0]['path'] == str(package), found
    # Restore
    new_home, new_root = Path(tmp) / 'new/home/anna', Path(tmp) / 'new'
    new_home.mkdir(parents=True)
    done = f.import_package(package, new_home, new_root, os.getuid(), os.getgid())
    assert not done['problems'] and 'ssh' in done['copied']
    assert (new_home / '.ssh/id_ed25519').read_text() == 'PRIVATE'
    assert (new_home / '.ssh').stat().st_mode & 0o777 == 0o700 and (new_home / '.ssh/id_ed25519').stat().st_mode & 0o777 == 0o600
    assert (new_home / 'Documents/with space ü.txt').read_text() == 'u' and (new_home / 'Documents/link').is_symlink()
    assert (new_home / 'Documents/hardlink.txt').stat().st_ino == (new_home / 'Documents/letter.txt').stat().st_ino
    assert (new_home / 'Projects/app/src/main.rs').exists() and not (new_home / 'Projects/app/node_modules').exists()
    assert not (new_home / '.cache').exists() and (new_root / 'opt/tool/bin').read_text() == 'tool'
    # A damaged archive is refused before anything is unpacked.
    archive = next((package / 'data').glob('dir_Documents.tar'))
    with open(archive, 'r+b') as stream:
        stream.seek(600); stream.write(b'Z')
    other = Path(tmp) / 'other'
    other.mkdir()
    try:
        f.import_package(package, other, other)
        raise AssertionError('damaged archive accepted')
    except ValueError:
        assert not any(other.iterdir())
    # An unfinished package (no marker) is not offered.
    broken = storage / 'Umzug-x'
    (broken / 'data').mkdir(parents=True)
    (broken / (f.PACKAGE_MARKER + '.partial')).write_text('{}')
    assert [p['path'] for p in f.find_packages([storage])] == [str(package)]
    # Owner remapping for another numeric account
    sample = Path(tmp) / 'owner'
    write(sample / 'a', 'x')
    f.remap_owner(sample, -12345, -12345, os.getuid(), os.getgid())   # nothing matches: must not fail
print('PASS finder package')
