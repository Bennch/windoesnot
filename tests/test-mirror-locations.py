#!/usr/bin/env python3
"""Docker (also with a custom data-root), VMs and /opt are found and copied to the same path; Docker is not preselected."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mirror_locations', root / 'desktop/lib/windoesnot/mirror.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    src, dst = base / 'src', base / 'dst'
    dst.mkdir()
    (src / 'opt/app').mkdir(parents=True)
    (src / 'opt/app/bin').write_text('x' * 100)
    os.mkfifo(src / 'opt/app/fifo')
    (src / 'etc/docker').mkdir(parents=True)
    (src / 'etc/docker/daemon.json').write_text(json.dumps({'data-root': '/mnt/dock'}))
    (src / 'mnt/dock/volumes/v/_data').mkdir(parents=True)
    (src / 'mnt/dock/volumes/v/_data/f').write_text('volume')
    (src / 'var/lib/libvirt/images').mkdir(parents=True)
    (src / 'var/lib/libvirt/images/a.qcow2').write_text('q')
    (src / 'srv').mkdir()  # empty folders are not offered
    found = {item['id']: item for item in m.scan_locations(src)}
    assert set(found) == {'docker', 'opt', 'libvirt'}, found
    assert found['docker']['path'] == '/mnt/dock' and found['docker']['selected'] is False
    assert found['opt']['selected'] and found['opt']['bytes'] == 100
    manifest = {'source_root': str(src), 'locations': [dict(item, selected=True) for item in found.values()]}
    done = m.copy_locations(manifest, dst)
    assert {item['id'] for item in done} == {'docker', 'opt', 'libvirt'}
    assert (dst / 'mnt/dock/volumes/v/_data/f').read_text() == 'volume'
    assert (dst / 'opt/app/bin').stat().st_size == 100 and not (dst / 'opt/app/fifo').exists()
    # Unselected or unknown ids are ignored, a forged path in the manifest is never used.
    other = base / 'dst2'
    other.mkdir()
    forged = {'source_root': str(src), 'locations': [{'id': 'opt', 'path': '/etc', 'selected': False},
                                                     {'id': 'evil', 'path': '/etc', 'selected': True}]}
    assert m.copy_locations(forged, other) == [] and not any(other.iterdir())
# Big top-level home folders are reported one by one so they can be left out.
with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / 'src'
    (src / 'home/old/Big').mkdir(parents=True)
    (src / 'home/old/Small').mkdir()
    (src / 'home/old/Big/f').write_bytes(b'x' * 500)
    (src / 'home/old/Small/f').write_bytes(b'x' * 5)
    (src / 'home/old/r').write_bytes(b'y' * 7)
    (src / 'etc').mkdir()
    (src / 'etc/passwd').write_text('old:x:1000:1000::/home/old:/bin/sh\n')
    m.BIG_FOLDER = 100
    user = m.scan_tree(src)['users'][0]
    assert user['bytes'] == 512 and user['exclude'] == []
    assert user['folders'] == [{'name': 'Big', 'bytes': 500}], user['folders']
print('PASS mirror locations')
