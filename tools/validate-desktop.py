#!/usr/bin/env python3
"""Check actual monitor geometry, clean-user initialization and Lua configuration."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT / 'desktop/config/hypr/lua/bin'))
from display_geometry import window_rules, logical_bounds
from hypr_bridge import lua

cases = [
    ('720p',1280,720,1,0,(1280,720)),
    ('1080p',1920,1080,1,0,(1920,1080)),
    ('1440p',2560,1440,1,0,(2560,1440)),
    ('4k-200',3840,2160,2,0,(1920,1080)),
    ('1440p-125',2560,1440,1.25,0,(2048,1152)),
    ('portrait',1920,1080,1,1,(1080,1920)),
    ('portrait-flipped',2560,1440,1.5,7,(960,1707)),
    ('small-vm',1024,600,1,0,(1024,600)),
]
for name,w,h,scale,transform,expected in cases:
    monitor = dict(name='Virtual-9',width=w,height=h,scale=scale,transform=transform,x=-3000,y=400,reserved=[5,25,7,45])
    assert logical_bounds(monitor)==expected, name
    for alignment in ['left','center']:
        for sidebar in ['left','hidden']:
            layout=window_rules(monitor,dict(taskbarAlignment=alignment,startMenuSidebarPosition=sidebar))
            for rule in layout['rules'].values():
                x,y=rule['move'];rw,rh=rule['size']
                assert x>=5 and y>=25, (name,rule)
                assert x+rw<=expected[0]-7 and y+rh<=expected[1]-45, (name,rule)
                assert rw>0 and rh>0
assert window_rules(dict(name='A',width=3840,height=2160,scale=2),{})['rules']['settings-config']['size']==[900,700]
print(f'PASS: {len(cases)*4} layout scenarios, including scaling, rotations and negative desktop origins')

for p in (ROOT/'desktop/config').rglob('*.py'): ast.parse(p.read_text(),filename=str(p))
for p in (ROOT/'desktop/bin').iterdir():
    if p.is_file() and p.read_text().startswith('#!/usr/bin/env python3'):ast.parse(p.read_text(),filename=str(p))
for p in (ROOT/'desktop/config/quickshell/default/img/project').glob('*.svg'):ET.parse(p)
print('PASS: Python syntax and SVG XML')
from system_defaults import system_defaults
with tempfile.TemporaryDirectory(prefix='windoesnot-system-fixture-') as tmp:
    fixture=Path(tmp);(fixture/'etc/default').mkdir(parents=True)
    (fixture/'etc/default/keyboard').write_text('XKBLAYOUT="us"\nXKBMODEL="pc105"\n')
    (fixture/'etc/locale.conf').write_text('LANG="en_US.UTF-8"\n')
    (fixture/'etc/localtime').symlink_to('/usr/share/zoneinfo/America/Toronto')
    defaults=system_defaults(fixture)
    assert defaults['options']['input.kb_layout']=='us'
    assert defaults['settings']=={'keyboardLayout':'us','uiLanguage':'en','systemLocale':'en_US.UTF-8','timeZone':'America/Toronto'}
    (fixture/'etc/default/keyboard').write_text('XKBLAYOUT="de,us"\nXKBVARIANT="nodeadkeys,"\n')
    assert system_defaults(fixture)['options']['input.kb_layout']=='de,us'
print('PASS: installer keyboard/locale/timezone are adopted without German/Berlin assumptions')

with tempfile.TemporaryDirectory(prefix='windoesnot-validate-') as tmp:
    home=Path(tmp);config=home/'.config';runtime=home/'runtime';runtime.mkdir(mode=0o700)
    env={**os.environ,'HOME':str(home),'XDG_CONFIG_HOME':str(config),'XDG_RUNTIME_DIR':str(runtime),'WINDOESNOT_SOURCE':str(ROOT),'BENNI_LUA_VERIFY':'1'}
    # Existing user settings must survive initialization and repeat initialization.
    private=config/'quickshell/default/settings.txt';private.parent.mkdir(parents=True);private.write_text('personal-settings-sentinel\n')
    subprocess.run([ROOT/'desktop/bin/windoesnot-initialize'],env=env,check=True)
    state=config/'hypr/lua/state.lua';before=state.read_bytes()
    subprocess.run([ROOT/'desktop/bin/windoesnot-initialize'],env=env,check=True)
    assert state.read_bytes()==before and private.read_text()=='personal-settings-sentinel\n'
    print('PASS: new user initialized; repeated initialization preserves state and personal settings')
    geometry=window_rules(dict(name='Virtual-9',width=1280,height=720,scale=1,reserved=[0,0,0,45]),{})
    (config/'hypr/lua/geometry.lua').write_text('return '+lua(geometry)+'\n')
    for p in (config/'hypr').rglob('*.lua'):subprocess.run(['luac','-p',p],check=True)
    result=subprocess.run(['Hyprland','--verify-config','-c',str(config/'hypr/hyprland.lua')],env=env,capture_output=True,text=True,timeout=25)
    (ROOT/'checks/lua-verify.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise SystemExit('Hyprland verification failed; see checks/lua-verify.log')
    print('PASS: Hyprland verifies clean-user Lua with generated 720p geometry; no plugins loaded')
