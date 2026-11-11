"""Compare synthetic VM user state after package migration and update."""
import hashlib
import json
from pathlib import Path
import subprocess

assert subprocess.run(['systemd-detect-virt','--vm','--quiet']).returncode==0
root=Path('/home/vmtest/.config')
before=json.loads(Path('/var/tmp/windoesnot-personal-before.json').read_text())
changed=[name for name,checksum in before.items() if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=checksum]
ledger=json.loads(Path('/home/vmtest/.local/state/windoesnot/desktop-files.json').read_text())
sync=json.loads(Path('/home/vmtest/.local/state/windoesnot/last-sync.json').read_text())
report={'private_files':len(before),'changed_private_files':changed,'manifest_version':ledger['version'],'managed_files':len(ledger['files']),'conflicts':sync['conflicts'],'generated_icon_map_is_unmanaged':'quickshell/default/IconMap.js' not in ledger['files']}
Path('/var/tmp/package-migration.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
assert not changed and not report['conflicts'] and report['generated_icon_map_is_unmanaged']
assert ledger['version']=='0.1.0-4' and (root/'windoesnot-release').read_text().strip()=='0.1.0-4'
