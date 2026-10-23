#!/usr/bin/env python3
"""Deploy only the Store preview and AUR updater UI; no package operations."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('host_sync', ROOT/'tools/sync-host-desktop.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)
home = Path.home()
host = home/'.config/quickshell/default'
source = ROOT/'desktop/config/quickshell/default'
preview = home/'.local/bin/windoesnot-store'
changes = [(preview,(ROOT/'store/target/release/windoesnot-store').read_bytes(),0o755),
           (host/'settings/UpdateCategory.qml',(source/'settings/UpdateCategory.qml').read_bytes(),0o600)]
for language in ('de','en'):
    target=host/'i18n'/f'{language}.js'
    text=target.read_text()
    additions=[]
    for line in (source/'i18n'/f'{language}.js').read_text().splitlines():
        if re.match(r'\s*"updates\.aur',line):
            key=line.split('"')[1]
            pattern=r'^\s*"'+re.escape(key)+r'":.*$'
            if re.search(pattern,text,re.M): text=re.sub(pattern,line,text,flags=re.M)
            else: additions.append(line)
    if additions:text=text.replace('var strings = {','var strings = {\n'+'\n'.join(additions),1)
    changes.append((target,text.encode(),0o600))
for target,_,_ in changes:
    if target.is_symlink():raise SystemExit('Refusing to replace symlink '+str(target))
backup=home/'.local/state/windoesnot/aur-updater'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup.mkdir(parents=True,mode=0o700)
manifest=[]
for target,_,_ in changes:
    existed=target.exists()
    manifest.append({'target':str(target),'existed':existed})
    if existed:
        saved=backup/'files'/target.relative_to(home)
        saved.parent.mkdir(parents=True,exist_ok=True)
        import shutil
        shutil.copy2(target,saved)
(backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
private=[host/name for name in ('settings.txt','pinned.txt','taskbar.txt','calendar_notes.json','settings/copilot-state.json')]
private.append(home/'.config/windoesnot-store/settings.json')
def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in private if p.is_file()}
before=hashes()
(backup/'personal-hashes.json').write_text(json.dumps(before,indent=2))
print('Backup: '+str(backup),flush=True)
sync.stop_shell()
try:
    for target,data,mode in changes:sync.write(target,data,mode)
    sync.start_shell()
    sync.wait_for_agent()
    if before!=hashes():raise RuntimeError('Personal files changed unexpectedly')
except Exception:
    sync.stop_shell();sync.restore(backup,manifest);sync.start_shell()
    raise
report={'backup':str(backup),'files':len(changes),'personal_files_unchanged':True,'agent_registered':True}
(ROOT/'checks/aur-updater-host.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
