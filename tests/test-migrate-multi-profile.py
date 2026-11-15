#!/usr/bin/env python3
"""Importer fixes from the Windows 7 VM run: several accounts never collide, hibernation hint only for a saved session."""
import importlib.util
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('migrate', ROOT / 'desktop/lib/windoesnot/migrate.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

assert m.profile_folder_name('..') == 'Windows'
assert m.profile_folder_name('a/b:c') == 'a_b_c'
assert m.profile_folder_name('Adä Müller') == 'Adä Müller'

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / 'windows'; home = Path(tmp) / 'home'
    for user, text in (('Ada', b'ada'), ('Bob', b'bob'), ('Cy', b'cyc')):
        (root / 'Users' / user / 'Documents').mkdir(parents=True)
        (root / 'Users' / user / 'Documents/hello.txt').write_bytes(text)
        (root / 'Users' / user / 'Documents' / ('only-' + user.lower() + '.txt')).write_bytes(text)
    home.mkdir()
    manifest = m.scan_tree(root, '/dev/test', locale='de_DE.UTF-8')
    names = [p['name'] for p in manifest['profiles']]
    assert len(names) == 3, names
    result = m.copy_manifest(manifest, home, source_root=root)
    assert not result['errors'], result['errors']
    # Windows 7 legacy junction with a localised name: no error, nothing lost.
    (root / 'Users/Ada/Pictures').mkdir()
    (root / 'Users/Ada/Pictures/p.txt').write_bytes(b'pic')
    (root / 'Users/Ada/Documents/Eigene Bilder').symlink_to('./../../../Users/Ada/Pictures')
    again = m.scan_tree(root, '/dev/test', locale='de_DE.UTF-8')
    assert not [w for p in again['profiles'] for w in p['warnings'] if 'reparse' in w], again['profiles']
    assert not m.copy_manifest(again, home, source_root=root)['errors']
    assert (home / 'Bilder/p.txt').read_bytes() == b'pic'
    first, *others = names
    assert (home / 'Dokumente/hello.txt').read_bytes() == (root / 'Users' / first / 'Documents/hello.txt').read_bytes()
    for name in others:
        assert (home / 'Dokumente' / name / 'hello.txt').read_bytes() == (root / 'Users' / name / 'Documents/hello.txt').read_bytes()
    # A retry reuses identical data and reports no error.
    assert not m.copy_manifest(manifest, home, source_root=root)['errors']
    for name, data, pending in (('hibr', b'hibr', True), ('HIBR', b'HIBR' + bytes(100), True), ('wake', b'wake' + bytes(100), False),
                                ('zero', bytes(100), False), ('empty', b'', True), ('RSTR', b'RSTR', True)):
        f = Path(tmp) / ('hiberfil-' + name); f.write_bytes(data)
        assert m.hibernation_pending(f) == pending, name
    assert m.hibernation_pending(Path(tmp) / 'missing') is False
print('multi-profile migration OK')
