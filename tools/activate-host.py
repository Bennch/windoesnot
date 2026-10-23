#!/usr/bin/env python3
"""Reload the deployed desktop and restart only its default shell/switcher."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT=Path(__file__).resolve().parent.parent
instances=json.loads(subprocess.check_output(['hyprctl','instances','-j'],text=True))
if len(instances)!=1:raise SystemExit('Expected exactly one active compositor')
signature=instances[0]['instance']

def ctl(*args):
    result=subprocess.run(['hyprctl','-i',signature,*args],capture_output=True,text=True,check=True)
    return result.stdout.strip()

before=json.loads(ctl('monitors','-j'))
if ctl('reload')!='ok':raise SystemExit('Reload did not succeed')
errors=ctl('configerrors')
if errors:raise SystemExit('Configuration errors: '+errors)
# Preserve every other Quickshell profile and all application windows.
pids=subprocess.run(['pgrep','-u',str(os.getuid()),'-x','quickshell'],capture_output=True,text=True).stdout.split()
for pid in pids:
    try:args=(Path('/proc')/pid/'cmdline').read_bytes().split(b'\0');args=[a.decode() for a in args if a]
    except OSError:continue
    if len(args)==1 or any(str(Path.home()/'.config/quickshell/default') in a for a in args[1:]):
        os.kill(int(pid),signal.SIGTERM)
command='~/.config/hypr/scripts/start-quickshell.sh'
code='return hl.dispatch(hl.dsp.exec_cmd('+json.dumps(command)+'))'
if ctl('eval',code)!='ok':raise SystemExit('Shell restart failed')
ctl('eval','return hl.dispatch(hl.dsp.exec_cmd("windoesnot-layout --watch"))')
ctl('eval','return hl.dispatch(hl.dsp.exec_cmd("pkill -u '+str(os.getuid())+' -x snappy-switcher; snappy-switcher --daemon"))')
time.sleep(2)
after=json.loads(ctl('monitors','-j'))
fields=('name','width','height','x','y','scale','transform')
monitor_unchanged=sorted([[m.get(k) for k in fields] for m in before])==sorted([[m.get(k) for k in fields] for m in after])
report={'configerrors':ctl('configerrors'),'plugins':ctl('plugin','list'),'monitor_layout_unchanged':monitor_unchanged}
log=Path(os.environ.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid())))/'start-quickshell.log'
text=log.read_text(errors='replace') if log.exists() else ''
report['shell_loaded']='Configuration Loaded' in text
report['qml_load_failed']='Failed to load configuration' in text
(ROOT/'checks/host-activation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
if report['configerrors'] or not monitor_unchanged or report['qml_load_failed'] or not report['shell_loaded']:raise SystemExit(1)
