#!/usr/bin/env python3
"""Deploy shared desktop code atomically, retaining host settings and overrides."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'desktop/config/hypr/lua/bin'))
from hypr_state import read_state, encode
from hypr_bridge import lua


def export_lua(path):
    # Read the exact current baseline, instead of relying on a stale migration copy.
    code=r'''
local function json(v)
    local ty=type(v)
    if ty=='nil' then return 'null' end
    if ty=='boolean' or ty=='number' then return tostring(v) end
    if ty=='string' then return '"' .. v:gsub('[%z\1-\31\\"]', function(c) return string.format('\\u%04x',string.byte(c)) end) .. '"' end
    local parts={}
    if #v>0 then
        for _,x in ipairs(v) do parts[#parts+1]=json(x) end
        return '['..table.concat(parts,',')..']'
    end
    for k,x in pairs(v) do parts[#parts+1]=json(k)..':'..json(x) end
    return '{'..table.concat(parts,',')..'}'
end
print(json(dofile(arg[1])))
'''
    result=subprocess.run(['lua','-',str(path)],input=code,text=True,capture_output=True,check=True)
    return json.loads(result.stdout)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    home=Path.home(); config=Path(os.environ.get('XDG_CONFIG_HOME',home/'.config'))
    current=config/'hypr/lua'
    if not (current/'state.lua').exists():raise SystemExit('Use windoesnot-initialize for a new installation')
    baseline=export_lua(current/'reference.lua')
    personal_path=current/'host.lua'
    # On repeat deploy, retain the saved personal baseline unchanged.
    if personal_path.exists():
        personal=export_lua(personal_path)
    else:
        personal={'options':baseline['options'],'env':baseline['env'],'devices':baseline['devices'],'rules':{},'autostart':[x for x in baseline['autostart'] if 'nvidia-settings' in x or 'clipboard-sync.sh' in x]}
        for rule in baseline['rules']:
            fields={k:v for k,v in rule.items() if k in ['move','monitor']}
            if fields:
                if 'move' in fields:fields['center']=False
                personal['rules'][rule['name']]=fields
    state=read_state(current)
    for button in state['buttons']:
        button['action']=button['action'].replace(str(current/'bin/hypr-bridge'),'windoesnot-hyprctl')
    changes=[]
    for source in (ROOT/'desktop/config').rglob('*'):
        if not source.is_file() or any(x.startswith('.') or x=='__pycache__' for x in source.relative_to(ROOT/'desktop/config').parts):continue
        relative=source.relative_to(ROOT/'desktop/config')
        if str(relative)=='hypr/scripts/start-quickshell.sh' and (config/relative).is_symlink():continue
        # User-adjusted application overrides and styles remain personal on the host.
        if relative.parts[0] in ['swaync','snappy-switcher'] or source.name=='replace.qml':continue
        changes.append((config/relative,source.read_bytes(),source.stat().st_mode & 0o777))
    changes.append((personal_path,('-- Host-only overrides preserved during release portability migration.\nreturn '+lua(personal)+'\n').encode(),0o644))
    changes.append((current/'state.lua',encode(state).encode(),0o644))
    # Helpers are part of the same backed-up deployment as QML/Lua. Include
    # them in dry-run, atomic writes and the recovery manifest as well.
    for command in (ROOT/'desktop/bin').iterdir():
        if command.is_file():
            changes.append((home/'.local/bin'/command.name,command.read_bytes(),command.stat().st_mode & 0o777))
    # Rebuilt local terminal is deployed with the same source revision as the ISO.
    for source in (ROOT/'build/components/LocalTerminal').glob('*'):
        if source.is_file():changes.append((config/'quickshell/default/widgets/terminalmodule/LocalTerminal'/source.name,source.read_bytes(),source.stat().st_mode & 0o777))
    switcher=ROOT/'build/components/bin/snappy-switcher'
    if switcher.is_file():
        changes.append((home/'.local/bin/snappy-switcher',switcher.read_bytes(),0o755))
    changes=[c for c in changes if not c[0].exists() or c[0].read_bytes()!=c[1]]
    with tempfile.TemporaryDirectory(prefix='windoesnot-host-check-') as temporary:
        candidate=Path(temporary)/'.config/hypr'
        shutil.copytree(ROOT/'desktop/config/hypr',candidate)
        (candidate/'lua/host.lua').write_text('return '+lua(personal)+'\n')
        (candidate/'lua/state.lua').write_text(encode(state))
        runtime=Path(temporary)/'run';runtime.mkdir(mode=0o700)
        env={**os.environ,'HOME':temporary,'XDG_CONFIG_HOME':str(Path(temporary)/'.config'),'XDG_RUNTIME_DIR':str(runtime),'BENNI_LUA_VERIFY':'1'}
        result=subprocess.run(['Hyprland','--verify-config','-c',str(candidate/'hyprland.lua')],env=env,capture_output=True,text=True,timeout=25)
        (ROOT/'checks/host-candidate-lua.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise SystemExit('Host candidate Lua failed verification; live files untouched')
    print(f'{len(changes)} changed/new files; host-specific Lua candidate verified; personal settings and monitor modes retained')
    if not args.apply:return
    for command in ['windoesnot-hyprctl','windoesnot-settings','windoesnot-layout']:
        if not Path('/usr/local/bin',command).is_file():raise SystemExit('Run sudo tools/install-system.sh before deploying shared commands')
    backup=home/'Backups/windoesnot-release'/time.strftime('%Y%m%d-%H%M%S-deploy')
    backup.mkdir(parents=True)
    manifest=[]
    # Stage every file before touching live QML; newly referenced types/assets first.
    for target,data,mode in changes:
        exists=target.exists(); link=os.readlink(target) if target.is_symlink() else None
        if exists:
            saved=backup/target.relative_to(home);saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,saved)
        manifest.append({'target':str(target),'existed':exists,'symlink':link,'sha256':hashlib.sha256(data).hexdigest()})
    (backup/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    changes.sort(key=lambda c:(c[0].suffix=='.qml',c[0].name=='shell.qml'))
    for target,data,mode in changes:
        target.parent.mkdir(parents=True,exist_ok=True)
        # Follow known existing symlink launchers; do not replace their link layout.
        target=target.resolve() if target.is_symlink() else target
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as stream:
            stream.write(data);temporary=Path(stream.name)
        temporary.chmod(mode);os.replace(temporary,target)
    alias=home/'.local/share/windoesnot';alias.parent.mkdir(parents=True,exist_ok=True)
    if not alias.exists():alias.symlink_to(ROOT,target_is_directory=True)
    (ROOT/'checks/host-deploy.json').write_text(json.dumps({'backup':str(backup),'files':len(changes)},indent=2)+'\n')
    print('Deployed; recovery manifest:',backup/'manifest.json')

if __name__=='__main__':main()
