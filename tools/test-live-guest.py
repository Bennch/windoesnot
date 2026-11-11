#!/usr/bin/env python3
"""Run inside our disposable live/installed VM, never on the host."""
import argparse
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import time

parser=argparse.ArgumentParser()
parser.add_argument('--user',default='liveuser')
args=parser.parse_args()
is_image=Path('/etc/windoesnot-image-build').exists() or Path('/usr/share/windoesnot/IMAGE-PACKAGES.txt').exists()
is_vm=subprocess.run(['systemd-detect-virt','--vm','--quiet']).returncode==0
if not is_image or not is_vm:
    raise SystemExit('Refusing: this is not a WinDoesNot test VM')
user=args.user;uid=pwd.getpwnam(user).pw_uid;home=Path(pwd.getpwnam(user).pw_dir)
runtime=Path('/run/user')/str(uid)
instances=list((runtime/'hypr').glob('*/.socket.sock'))
if len(instances)!=1:raise SystemExit('Expected one guest compositor')
signature=instances[0].parent.name
base=['runuser','-u',user,'--','env',f'XDG_RUNTIME_DIR={runtime}',f'HYPRLAND_INSTANCE_SIGNATURE={signature}','WAYLAND_DISPLAY=wayland-1']

def call(*args):
    r=subprocess.run([*base,*args],text=True,capture_output=True,timeout=15)
    if r.returncode:raise RuntimeError(r.stderr or r.stdout)
    return r.stdout.strip()

def ctl(*args):return call('/usr/bin/hyprctl',*args)

def screenshot(name):call('/usr/bin/grim','/tmp/'+name+'.png')

report={'configerrors':ctl('configerrors'),'plugins':ctl('plugin','list'),'tests':[]}
if report['configerrors']:raise SystemExit(report['configerrors'])
if 'hyprbars' not in report['plugins'] or 'hyprdrag' not in report['plugins']:raise SystemExit('Missing custom plugin')
state=home/'.config/hypr/lua/state.lua';original=state.read_bytes()
try:
    modes=[('720p',1280,720,1,0),('1080p',1920,1080,1,0),('125pct',2560,1440,1.25,0),('portrait',1920,1080,1,1)]
    for label,width,height,scale,transform in modes:
        monitor=json.loads(ctl('monitors','-j'))[0]
        spec={'name':monitor['name'],'width':width,'height':height,'refreshRate':60,'scale':scale,'x':0,'y':0,'transform':transform}
        payload={'monitors':{'monitors':[spec],'primary':monitor['name']}}
        call('windoesnot-settings',json.dumps(payload))
        time.sleep(1.2)
        ctl('eval','return hl.dispatch(hl.dsp.global("quickshell:show-settings"))')
        time.sleep(.4)
        current=json.loads(ctl('monitors','-j'))[0]
        clients=json.loads(ctl('clients','-j'))
        window=next((w for w in clients if w['title']=='quickshell-settings'),None)
        if window is None:raise RuntimeError('Settings window did not open')
        logical_w=round((current['height'] if current.get('transform',0)%2 else current['width'])/current['scale'])
        logical_h=round((current['width'] if current.get('transform',0)%2 else current['height'])/current['scale'])
        x,y=window['at'];w,h=window['size']
        if not (x>=0 and y>=0 and x+w<=logical_w+2 and y+h<=logical_h-43):
            raise RuntimeError(f'{label}: settings outside work area: {window["at"]}, {window["size"]}, {logical_w}x{logical_h}')
        screenshot('settings-'+label)
        report['tests'].append({'mode':label,'physical':[current['width'],current['height']],'scale':current['scale'],'transform':current.get('transform',0),'logical':[logical_w,logical_h],'settings_at':window['at'],'settings_size':window['size'],'configerrors':ctl('configerrors')})
finally:
    state.write_bytes(original);os.chown(state,uid,pwd.getpwnam(user).pw_gid)
    ctl('reload');time.sleep(1)
    current=json.loads(ctl('monitors','-j'))[0]
    windows=[w for w in json.loads(ctl('clients','-j')) if w['title']=='quickshell-settings']
    for w in windows:
        if w['at'][0]<0 or w['at'][1]<0 or w['at'][0]+w['size'][0]>current['width']/current['scale']+2 or w['at'][1]+w['size'][1]>current['height']/current['scale']-43:
            raise RuntimeError('Already-open settings did not fit after restoring original mode')
Path('/tmp/windoesnot-live-test.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
