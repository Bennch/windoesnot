#!/usr/bin/python3 -I
"""Install only the reviewed backup helper/policies and user-agent guard."""
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
FILES = {
 'desktop/lib/windoesnot/snapshots.py': ('/usr/lib/windoesnot/snapshots.py', 0o755),
 'desktop/bin/windoesnot-auth-guard': ('/usr/bin/windoesnot-auth-guard', 0o755),
 'desktop/share/polkit-1/actions/org.windoesnot.snapshots.policy': ('/usr/share/polkit-1/actions/org.windoesnot.snapshots.policy', 0o644),
}
if os.geteuid() != 0:
    raise SystemExit('Run through pkexec after reviewing the fixed file list')
backup = Path('/var/lib/windoesnot/backup-integration') / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup.mkdir(parents=True, mode=0o700)
manifest = {}
for relative, (destination, mode) in FILES.items():
    source, target = ROOT / relative, Path(destination)
    manifest[destination] = target.exists()
    if target.exists():
        saved = backup / destination.lstrip('/')
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, saved)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.wdn-new')
    temporary.unlink(missing_ok=True)
    with temporary.open('xb') as stream:
        stream.write(source.read_bytes())
    os.chown(temporary, 0, 0)
    os.chmod(temporary, mode)
    temporary.replace(target)
(backup / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print('System-file recovery copy: ' + str(backup), flush=True)
result = subprocess.run(['/usr/lib/windoesnot/snapshots.py', 'status'], text=True, capture_output=True)
if result.returncode:
    print(result.stderr)
    raise SystemExit(result.returncode)
data = json.loads(result.stdout)
print(json.dumps({'ready': data['ready'], 'snapshot_count': len(data.get('snapshots', [])),
                  'schedule': data.get('schedule'), 'timer_active': data.get('timerActive')}))
