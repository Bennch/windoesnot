#!/usr/bin/env python3
"""Exercise the live desktop's settings IPC inside a disposable WinDoesNot VM."""
from pathlib import Path
import argparse
import json
import os
import signal
import subprocess
import time

parser=argparse.ArgumentParser();parser.add_argument('--restart',action='store_true');parser.add_argument('--state',action='store_true');parser.add_argument('--language',choices=['de','en']);parser.add_argument('--appearance',choices=['dark','light']);args=parser.parse_args()
if not Path('/etc/windoesnot-image-build').is_file() or subprocess.run(['systemd-detect-virt','--vm','--quiet']).returncode:
    raise SystemExit('Disposable live VM only')
home=Path('/home/liveuser');target=str(home/'.config/quickshell/default/shell.qml')
sig=next(Path('/run/user/1000/hypr').iterdir()).name
base=['runuser','-u','liveuser','--','env','XDG_RUNTIME_DIR=/run/user/1000','WAYLAND_DISPLAY=wayland-1','HYPRLAND_INSTANCE_SIGNATURE='+sig]
if args.restart:
    for p in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            command=[x.decode() for x in p.read_bytes().split(b'\0') if x]
            if command and Path(command[0]).name=='quickshell' and target in command:os.kill(int(p.parent.name),signal.SIGTERM)
        except (OSError,UnicodeError):pass
    log=open('/tmp/wdn-shell-restart.log','a')
    subprocess.Popen([*base,'bash',str(home/'.config/quickshell/default/extras/start-quickshell.sh')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
def ipc(*command):
    return subprocess.run([*base,'quickshell','ipc','--path',target,'call','windoesnot-settings',*command],text=True,capture_output=True,timeout=5)
for attempt in range(60):
    result=ipc('state')
    if result.returncode==0:
        state=json.loads(result.stdout)
        if not state['loading']:break
    time.sleep(.2)
else:raise SystemExit('Settings IPC not ready: '+result.stderr)
if args.language:
    result=ipc('setLanguage',args.language);assert result.returncode==0,result.stderr;time.sleep(.5)
if args.appearance:
    result=ipc('setDarkMode','true' if args.appearance=='dark' else 'false');assert result.returncode==0,result.stderr;time.sleep(.5)
state=json.loads(ipc('state').stdout)
assert not state['loading']
if args.language:assert state['language']==args.language
if args.appearance:assert state['dark']==(args.appearance=='dark')
log=Path('/run/user/1000/start-quickshell.log').read_text()
errors=[line for line in log.splitlines() if any(x in line for x in ['ReferenceError','TypeError','Failed to load configuration','Cannot assign'])]
assert not errors,errors
print(json.dumps(state,sort_keys=True))
