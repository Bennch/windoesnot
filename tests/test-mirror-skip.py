#!/usr/bin/env python3
"""copy_home skips sockets, FIFOs, caches, mounts and unreadable folders and reports them instead of aborting."""
import importlib.util
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
if os.environ.get('WDN_SKIP_TEST_NS') != '1':
    if not shutil.which('unshare'):
        print('SKIP mirror skip: unshare missing')
        sys.exit(0)
    probe = subprocess.run(['unshare', '-Urm', 'true'], capture_output=True)
    if probe.returncode:
        print('SKIP mirror skip: user namespaces unavailable')
        sys.exit(0)
    sys.exit(subprocess.run(['unshare', '-Urm', sys.executable, __file__], env=dict(os.environ, WDN_SKIP_TEST_NS='1')).returncode)

spec = importlib.util.spec_from_file_location('mirror_skip', root / 'desktop/lib/windoesnot/mirror.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    src = base / 'source/home/old'
    dst = base / 'target'
    dst.mkdir()
    for d in ('.cache/app', '.local/share/Trash/files', 'Documents', 'Projects/build', 'data-disk'):
        (src / d).mkdir(parents=True)
    (src / '.cache/app/blob').write_text('cache')
    (src / '.local/share/Trash/files/old').write_text('trash')
    (src / 'Documents/a.txt').write_text('keep')
    (src / 'Projects/build/big.o').write_text('rebuildable')
    os.mkfifo(src / 'Documents/pipe')
    sock = socket.socket(socket.AF_UNIX)
    sock.bind(str(src / 'Documents/app.sock'))
    subprocess.run(['mount', '-t', 'tmpfs', 'tmpfs', str(src / 'data-disk')], check=True)
    (src / 'data-disk/inside').write_text('other filesystem')
    (src / 'locked').mkdir()
    (src / 'locked/secret').write_text('x')
    os.chmod(src / 'locked', 0)
    manifest = {'schema': 1, 'kind': 'linux', 'source_root': str(base / 'source'),
                'users': [{'name': 'old', 'home': '/home/old', 'uid': os.getuid(), 'gid': os.getgid(),
                           'exclude': ['Projects/build']}]}
    result = m.copy_home(manifest, dst)
    reasons = {item['path']: item['reason'] for item in result['skipped']}
    assert (dst / 'Documents/a.txt').read_text() == 'keep'
    assert not (dst / '.cache').exists() and not (dst / '.local/share/Trash/files').exists()
    assert not (dst / 'Projects/build').exists()
    assert not (dst / 'Documents/pipe').exists() and not (dst / 'Documents/app.sock').exists()
    assert not (dst / 'data-disk/inside').exists()
    assert reasons.get('.cache') == 'excluded' and reasons.get('Projects/build') == 'excluded'
    assert reasons.get('Documents/pipe') == 'special' and reasons.get('Documents/app.sock') == 'special'
    assert reasons.get('data-disk') == 'mount', reasons
    # Running as (namespace) root reads everything, so the unreadable case is only checked when it applies.
    if os.geteuid() != 0:
        assert reasons.get('locked') == 'unreadable', reasons
    os.chmod(src / 'locked', 0o755)
    subprocess.run(['umount', str(src / 'data-disk')], check=True)
print('PASS mirror skip')
