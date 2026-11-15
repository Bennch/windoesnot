#!/usr/bin/env python3
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp); (root / 'etc').mkdir(); (root / 'etc/windoesnot-image-build').touch()
    values = {'rootMountPoint': str(root), 'username': 'ada', 'windoesnotMigrateManifest': json.dumps({'kind': 'linux', 'system': 'CachyOS'}), 'windoesnotMigrateSecret': 'fake'}
    progress = []
    fake = SimpleNamespace(globalstorage=SimpleNamespace(value=values.get, insert=values.__setitem__), utils=SimpleNamespace(warning=lambda x: None), job=SimpleNamespace(setprogress=progress.append))
    class Process:
        def __init__(self, args, **kwargs):
            assert args[1] == '/usr/lib/windoesnot/mirror.py' and '--target-root' in args
            self.stdin = io.StringIO(); self.stdout = iter(['{"event":"file","copied_bytes":1,"total_bytes":2}\n', '{"errors":[]}\n']); self.returncode = 0
        def wait(self): return 0
    with patch.dict(sys.modules, {'libcalamares': fake, 'migrate': SimpleNamespace()}):
        spec = importlib.util.spec_from_file_location('mirror_install', ROOT / 'iso/modules/windoesnotmigrate_install/main.py')
        job = importlib.util.module_from_spec(spec); spec.loader.exec_module(job)
        with patch.object(job.subprocess, 'Popen', Process): assert job.run() is None
    assert values['windoesnotMigrateCompleted'] and values['windoesnotMigrateSystem'] == 'CachyOS'
    assert values['windoesnotMigrateSecret'] == '' and progress == [0.5]
    assert (root / 'etc/systemd/system/multi-user.target.wants/windoesnot-mirror-packages.service').is_symlink()
print('PASS mirror install')
