#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import tempfile
from contextlib import contextmanager
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mirror_flow', ROOT / 'desktop/lib/windoesnot/mirror.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp); source = base / 'source'; target = base / 'target'; home = target / 'home/bob'
    (source / 'etc').mkdir(parents=True); (source / 'home/alice').mkdir(parents=True)
    (source / 'etc/os-release').write_text('PRETTY_NAME="CachyOS"\n')
    (source / 'etc/passwd').write_text('alice:x:1000:1000::/home/alice:/bin/bash\n')
    (source / 'home/alice/document').write_text('synthetic')
    home.mkdir(parents=True)
    @contextmanager
    def mounted(device, secret=None):
        assert device == '/dev/fixture'
        yield source, 'ext4', []
    calls = []
    def fake_copy(plan, destination, progress):
        calls.append('home'); assert plan['source_root'] == str(source)
        raise OSError('synthetic home failure')
    def fake_archive(root, state, connections, **kwargs):
        calls.append('wifi' if kwargs.get('archive_etc') is False else 'etc')
        return 0
    with patch.object(m, 'block_id', return_value='8:1'), patch.object(m, 'mounted_source', mounted), patch.object(m, 'copy_home', fake_copy), patch.object(m, 'archive_etc_and_wifi', fake_archive):
        plan = m.scan_device('/dev/fixture')
        assert plan['system'] == 'CachyOS' and plan['users'][0]['bytes'] == 9
        plan['source_root'] = '/untrusted'; plan['wlan_selected'] = True
        plan['package_selection'] = {'arch_explicit': True}
        plan['packages']['arch_explicit'] = ['valid']; plan['services'] = ['test.service']
        result = m.copy_manifest(plan, home, str(target))
        assert calls == ['home', 'wifi', 'etc'] and result['errors'][0]['path'] == 'home'
        state = next((target / 'var/lib/windoesnot/mirror').iterdir())
        data = json.loads((state / 'packages.json').read_text())
        assert data['home'] == '/home/bob' and data['arch_explicit'] == ['valid'] and data['flatpak'] == []
        assert json.loads((state / 'services.json').read_text()) == ['test.service']
        plan['block_identity'] = '8:2'
        try: m.copy_manifest(plan, home, str(target))
        except ValueError: pass
        else: raise AssertionError('changed identity accepted')
print('PASS mirror flow')
