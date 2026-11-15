#!/usr/bin/env python3
"""Exercise migration with temporary, synthetic homes only."""
import importlib.util
import os
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mirror_copy', root / 'desktop/lib/windoesnot/mirror.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    src = base / 'source/home/old'
    dst = base / 'target'
    (src / '.config/hypr').mkdir(parents=True)
    (src / '.ssh').mkdir()
    (src / '.local/share/flatpak').mkdir(parents=True)
    dst.mkdir()
    (src / '.config/hypr/config').write_text('old config')
    (src / '.ssh/key').write_text('private')
    (src / 'space ü').write_text('data')
    os.link(src / 'space ü', src / 'hardlink')
    os.symlink('space ü', src / 'link')
    (dst / '.config/hypr').mkdir(parents=True)
    (dst / '.config/hypr/config').write_text('new config')
    manifest = {'schema': 1, 'kind': 'linux', 'source_root': str(base / 'source'),
                'users': [{'name': 'old', 'home': '/home/old', 'uid': os.getuid(), 'gid': os.getgid()}]}
    m.copy_home(manifest, dst)
    m.copy_home(manifest, dst)
    assert (dst / '.ssh/key').read_text() == 'private'
    assert (dst / '.config/hypr/config').read_text() == 'new config'
    assert (dst / 'Umzug-old/original/.config/hypr/config').read_text() == 'old config'
    assert (dst / 'link').is_symlink()
    assert (dst / 'hardlink').stat().st_ino == (dst / 'space ü').stat().st_ino
    (src / 'trap').mkdir()
    os.symlink(base, dst / 'trap')
    (src / 'trap/evil').write_text('bad')
    try:
        m.copy_home(manifest, dst)
        raise AssertionError('symlink traversal accepted')
    except ValueError:
        pass
print('PASS mirror copy')

from unittest import mock
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    src = base / 'source/etc/NetworkManager/system-connections'
    dst = base / 'connections'
    state = base / 'state'
    src.mkdir(parents=True); dst.mkdir(); state.mkdir()
    (src / 'wifi.nmconnection').write_text('[connection]\nuuid=12345678-1234-1234-1234-123456789abc\n[wifi]\nssid=test\n')
    (src / 'wired.nmconnection').write_text('[connection]\nuuid=aaaaaaaa-1234-1234-1234-123456789abc\n[ethernet]\n')
    with mock.patch.object(m.os, 'fchown'):
        assert m.archive_etc_and_wifi(base / 'source', state, dst) == 1
        assert m.archive_etc_and_wifi(base / 'source', state, dst) == 0
    assert (dst / 'wifi.nmconnection').stat().st_mode & 0o777 == 0o600
    assert not (dst / 'wired.nmconnection').exists()
    assert (state / 'etc-alt/NetworkManager/system-connections/wired.nmconnection').exists()
print('PASS mirror wifi fixture')
