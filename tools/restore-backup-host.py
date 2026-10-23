#!/usr/bin/env python3
"""Restore one explicitly selected backup/auth deployment, keeping user state."""
import importlib.util
import json
from pathlib import Path
import sys

source = Path(__file__).with_name('install-backup-host.py')
spec = importlib.util.spec_from_file_location('deploy_backup', source)
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)
if len(sys.argv) != 2:
    raise SystemExit('Usage: restore-backup-host.py ~/.local/state/windoesnot/backup-integration/TIMESTAMP')
backup = Path(sys.argv[1]).expanduser().resolve()
root = (Path.home() / '.local/state/windoesnot/backup-integration').resolve()
if backup.parent != root:
    raise SystemExit('Select a direct backup directory under ' + str(root))
manifest = json.loads((backup / 'manifest.json').read_text())
if set(manifest) != set(deploy.FILES):
    raise SystemExit('Unexpected backup manifest')
deploy.stop_shell()
for name, existed in manifest.items():
    if existed:
        deploy.atomic_copy(backup / name, deploy.HOST / name)
    else:
        (deploy.HOST / name).unlink(missing_ok=True)
deploy.start_shell()
print('Previous desktop code restored. Snapshot helper and policies remain installed.')
